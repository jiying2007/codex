import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_assets.cli import cmd_apply
from tools.codex_assets.context_maintenance import parse_config
from tools.codex_assets.core import CodexAssetError, build_repo, collect_managed, plan_apply, validate_apply_plan
from tools.codex_assets.local_config import load_config, merge_config
from tools.codex_assets.local_exec_rules import verified_inputs
import test_context_maintenance as fixtures


class LocalConfigTests(unittest.TestCase):
    def write_input(self, path, overrides, profile="default"):
        path.write_text(json.dumps({"schema_version": 1, "profile": profile,
                                   "target": "config.toml", "overrides": overrides}))
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_only_selected_preferences_override_fresh_source_and_mcp(self):
        source = 'model = "new-default"\napproval_policy = "on-request"\n[tui]\nanimations = false\n'
        source += '[mcp_servers.new]\nurl = "https://example.invalid/mcp"\n'
        overrides = {"model_provider": "relay", "tui": {"resume_cwd": "current"},
                     "projects": {"/private/project": {"trust_level": "trusted"}}}
        result = parse_config(merge_config(source, overrides))
        self.assertEqual(result["model"], "new-default")
        self.assertEqual(result["approval_policy"], "on-request")
        self.assertFalse(result["tui"]["animations"])
        self.assertEqual(result["tui"]["resume_cwd"], "current")
        self.assertIn("new", result["mcp_servers"])
        self.assertEqual(parse_config(merge_config(source.replace("new-default", "next-default"), overrides))["model"], "next-default")

    def test_quoted_paths_apps_and_multiline_values_round_trip(self):
        overrides = {"projects": {"/some/中文 path": {"trust_level": "trusted"}},
                     "apps": {"connector": {"tools": {"github.create_blob": {"approval_mode": "approve"}}}}}
        parsed = parse_config(merge_config('developer_instructions = """first\nsecond"""\n', overrides))
        self.assertEqual(parsed["developer_instructions"], "first\nsecond")
        self.assertEqual(parsed["apps"], overrides["apps"])
        self.assertEqual(parsed["projects"], overrides["projects"])

    def test_permissions_secrets_mcp_and_unbounded_tui_are_not_override_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "local.json"
            for key, value in (("sandbox_mode", "danger-full-access"), ("approval_policy", "never"),
                               ("shell_environment_policy", {"set": {"KEY": "private"}}),
                               ("model_providers", {}), ("mcp_servers", {}),
                               ("tui", {"notifications": []})):
                with self.subTest(key=key):
                    sha = self.write_input(path, {key: value})
                    with self.assertRaises(ValueError):
                        load_config(path, sha, "default")

    def test_hash_profile_and_machine_identity_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / "local.json"
            sha = self.write_input(path, {"tui": {"resume_cwd": "current"}})
            _, identity = load_config(path, sha, "default")
            self.assertEqual(verified_inputs({"config_overrides": identity}, root, "default")["config_overrides"], identity)
            for expected, profile in (("0" * 64, "default"), (sha, "team-collab")):
                with self.assertRaises(ValueError):
                    load_config(path, expected, profile)
            path.write_text("{}")
            with self.assertRaises(ValueError):
                verified_inputs({"config_overrides": identity}, root, "default")

    def test_nested_unknown_secrets_and_wrong_app_notice_types_are_rejected(self):
        cases = [
            {"apps": {"example": {"api_key": "dummy"}}},
            {"notice": {"unexpected": {"password": "dummy"}}},
            {"notice": {"hide_full_access_warning": "true"}},
            {"notice": {"model_migrations": []}},
            {"apps": {"example": {"tools": {"tool": {"env": {"KEY": "dummy"}}}}}},
            {"apps": {"example": {"tools": []}}},
            {"apps": {"example": {"enabled": "true"}}},
            {"apps": {"example": {"tools": {"tool": {"approval_mode": "unknown"}}}}},
            {"tui": {"resume_cwd": {}}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "local.json"
            for value in cases:
                with self.subTest(value=value):
                    sha = self.write_input(path, value)
                    with self.assertRaises(ValueError):
                        load_config(path, sha, "default")

    def test_reuse_and_implicit_apply_preserve_partial_input_and_new_template(self):
        helper = fixtures.ImplicitRebuildTests()
        with tempfile.TemporaryDirectory() as directory:
            root, _ = helper.fixture(directory)
            path = root / "local-preferences.json"
            sha = self.write_input(path, {"model_provider": "relay"})
            build = build_repo(root, "default", local_config_arg=str(path), local_config_sha256=sha)
            template = root / "src/codex-home/config/base.toml"
            template.write_text(template.read_text() + '\n[notice]\nhide_full_access_warning = true\n')
            build_repo(root, "default", reuse_context_input=True, reuse_machine_inputs=True)
            self.assertTrue(parse_config((build / "config.toml").read_text())["notice"]["hide_full_access_warning"])
            self.assertEqual(parse_config((build / "config.toml").read_text())["model_provider"], "relay")
            with patch("tools.codex_assets.cli.plan_apply", side_effect=RuntimeError("before-write")):
                with self.assertRaisesRegex(RuntimeError, "before-write"):
                    cmd_apply(helper.args(root))
            state = json.loads((build / "control/state/managed-files.json").read_text())
            self.assertIsNone(state["context_config_input_path"])
            self.assertIn("config_overrides", state["machine_inputs"])
            self.assertFalse((root / "target").exists())

    def test_changed_input_invalidates_plan_and_does_not_replace_existing_build(self):
        helper = fixtures.ImplicitRebuildTests()
        with tempfile.TemporaryDirectory() as directory:
            root, _ = helper.fixture(directory)
            path = root / "local-preferences.json"
            sha = self.write_input(path, {"model_provider": "relay"})
            build = build_repo(root, "default", local_config_arg=str(path), local_config_sha256=sha)
            plan = plan_apply(root, build, root / "target", root / "backup", False, False)
            before = (build / "control/state/managed-files.json").read_bytes()
            path.write_text("{}")
            with self.assertRaises(CodexAssetError):
                validate_apply_plan(plan)
            with self.assertRaises(CodexAssetError):
                build_repo(root, "default", reuse_machine_inputs=True)
            self.assertEqual(before, (build / "control/state/managed-files.json").read_bytes())

    def test_full_snapshot_and_partial_preferences_cannot_be_combined(self):
        helper = fixtures.ImplicitRebuildTests()
        with tempfile.TemporaryDirectory() as directory:
            root, snapshot = helper.fixture(directory)
            path = root / "local-preferences.json"
            sha = self.write_input(path, {"model_provider": "relay"})
            with self.assertRaisesRegex(CodexAssetError, "cannot be combined"):
                build_repo(root, "default", context_config_from=str(snapshot),
                           local_config_arg=str(path), local_config_sha256=sha)

    def test_mid_build_input_change_preserves_previous_build(self):
        helper = fixtures.ImplicitRebuildTests()
        with tempfile.TemporaryDirectory() as directory:
            root, _ = helper.fixture(directory)
            path = root / "local-preferences.json"
            sha = self.write_input(path, {"model_provider": "relay"})
            build = build_repo(root, "default", local_config_arg=str(path), local_config_sha256=sha)
            before = (build / "control/state/managed-files.json").read_bytes()

            def change_after_render(*args):
                value = collect_managed(*args)
                path.write_text("{}")
                return value

            with patch("tools.codex_assets.core.collect_managed", side_effect=change_after_render):
                with self.assertRaisesRegex(CodexAssetError, "changed during build"):
                    build_repo(root, "default", local_config_arg=str(path), local_config_sha256=sha)
            self.assertEqual(before, (build / "control/state/managed-files.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
