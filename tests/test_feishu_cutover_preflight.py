"""No-model, no-database safety tests for the host cutover preflight."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "feishu-cutover-preflight.py"
SPEC = importlib.util.spec_from_file_location("feishu_cutover_preflight", str(SCRIPT))
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class CutoverPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="feishu-cutover-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = self.root / "private.env"
        self.policy = self.root / "policy.json"
        self.db = self.root / "state.sqlite3"
        self.lock = self.root / "bot.lock"
        self.write_policy()
        self.write_env()

    def write_policy(self, policy_path=None):
        payload = {
            "schema_version": 1,
            "engineering_enabled": True,
            "agent_intake_enabled": False,
            "repositories": {"app": {"path": str(self.root / "repo")}},
            "state_db": str(self.db),
            "lock_file": str(self.lock),
        }
        path = policy_path or self.policy
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)

    def write_env(self, policy_path=None):
        values = {
            "FEISHU_APP_ID": "cli_fixture",
            "FEISHU_APP_SECRET": "secret-must-not-appear",
            "FEISHU_TARGET_CHAT_ID": "oc_fixture",
            "FEISHU_BOT_CONFIG": str(policy_path or self.policy),
            "FEISHU_STATE_DB": str(self.db),
            "FEISHU_LOCK_FILE": str(self.lock),
            "FEISHU_AGENT_BILLING_SOURCE": "external_gateway",
            "FEISHU_AGENT_OPENAI_API_KEY": "dedicated-key-must-not-appear",
            "FEISHU_AGENT_OPENAI_BASE_URL": "https://gateway.example/v1",
            "FEISHU_AGENT_BUDGET_BACKEND": "litellm",
            "FEISHU_AGENT_BUDGET_KEY_ALIAS": "fixture-alias",
            "FEISHU_AGENT_BUDGET_MAX_USD": "10",
            "FEISHU_AGENT_CODEX_HOME": "/srv/feishu-agent/codex-home",
            "FEISHU_AGENT_MODEL": "fixture-model",
            "FEISHU_AGENT_GITHUB_WRITE_TOKEN": "github-token-must-not-appear",
        }
        self.env.write_text(
            "".join(key + "=" + value + "\n" for key, value in values.items()),
            encoding="utf-8",
        )
        self.env.chmod(0o600)

    def observe(self, expected_sha=None, service=None):
        sha = "a" * 40
        service = service or {
            "ActiveState": "inactive", "SubState": "dead", "MainPID": "0",
            "WorkingDirectory": str(self.root), "UMask": "0077",
            "NoNewPrivileges": "yes", "PrivateTmp": "yes",
        }
        with mock.patch.object(PREFLIGHT, "service_observation", side_effect=[service, service]), \
                mock.patch.object(PREFLIGHT, "command", side_effect=[sha, ""]):
            return PREFLIGHT.probe(self.root, self.env, expected_sha=expected_sha)

    def test_probe_is_read_only_redacted_and_compares_exact_sha(self):
        sha = "a" * 40
        result = self.observe(sha)
        encoded = json.dumps(result, sort_keys=True)
        self.assertTrue(result["checkout"]["matches_expected_sha"])
        self.assertFalse(result["checkout"]["dirty"])
        self.assertTrue(result["config"]["env_parsed"])
        self.assertTrue(result["config"]["policy_parsed"])
        self.assertTrue(result["config"]["required_feishu_fields_present"])
        self.assertTrue(result["config"]["dedicated_model_fields_present"])
        self.assertEqual("external_gateway", result["config"]["billing_source"])
        self.assertEqual("litellm", result["config"]["budget_backend"])
        self.assertTrue(result["config"]["agent_modes_all_empty"])
        self.assertEqual(
            {
                "schema_version_1": True,
                "repositories_valid": True,
                "edit_strategies_all_worktree": True,
                "worktree_roots_ready_for_edit": True,
                "worktree_roots_outside_repositories": True,
                "agent_intake_disabled": True,
                "agent_modes_all_empty": True,
                "legacy_env_fields_absent": True,
                "legacy_policy_fields_absent": True,
            },
            result["config"]["policy_contract"],
        )
        self.assertTrue(result["state"]["paths_explicit_in_policy"])
        self.assertEqual("private_directory", result["state"]["state_parent_metadata"])
        self.assertEqual(
            {"umask_0077": True, "no_new_privileges": True, "private_tmp": True},
            result["service"]["security"],
        )
        self.assertTrue(result["service"]["working_directory_matches_checkout"])
        self.assertNotIn("systemd_umask_not_0077", result["blockers_observed"])
        self.assertFalse(result["service_changed"])
        self.assertFalse(result["model_called"])
        self.assertFalse(result["database_opened"])
        self.assertFalse(result["cutover_proven"])
        self.assertEqual("not_observed_no_sqlite_access", result["state"]["task_status"])
        self.assertFalse(self.db.exists())
        for secret in (
            "secret-must-not-appear", "dedicated-key-must-not-appear",
            "github-token-must-not-appear",
        ):
            self.assertNotIn(secret, encoded)

    def test_weak_systemd_unit_properties_are_explicit_blockers(self):
        service = {
            "ActiveState": "inactive", "SubState": "dead", "MainPID": "0",
            "WorkingDirectory": str(self.root / "wrong"),
            "UMask": "0002", "NoNewPrivileges": "no", "PrivateTmp": "no",
        }
        result = self.observe(service=service)
        blockers = set(result["blockers_observed"])
        self.assertIn("systemd_umask_not_0077", blockers)
        self.assertIn("systemd_no_new_privileges_not_enabled", blockers)
        self.assertIn("systemd_private_tmp_not_enabled", blockers)
        self.assertIn("systemd_working_directory_differs_from_checkout", blockers)
        self.assertEqual(
            {"umask_0077": False, "no_new_privileges": False, "private_tmp": False},
            result["service"]["security"],
        )

    def test_legacy_in_place_strategy_is_a_cutover_blocker(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"].update(
            allowed_modes=["explain", "review"], edit_strategy="in_place",
        )
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["config"]["policy_contract"]["edit_strategies_all_worktree"])
        self.assertIn("repository_edit_strategy_not_worktree", result["blockers_observed"])

    def test_edit_mode_requires_an_external_worktree_root(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"]["allowed_modes"] = ["explain", "review", "edit"]
        payload["repositories"]["app"]["edit_strategy"] = "worktree"
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["config"]["policy_contract"]["worktree_roots_ready_for_edit"])
        self.assertFalse(result["config"]["policy_contract"]["worktree_roots_outside_repositories"])
        self.assertIn("repository_worktree_root_missing_for_edit", result["blockers_observed"])
        self.assertIn("repository_worktree_root_not_external", result["blockers_observed"])

    def test_worktree_root_inside_source_repository_is_rejected(self):
        repo = self.root / "repo"
        repo.mkdir()
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"].update(
            path=str(repo), allowed_modes=["explain", "review", "edit"],
            edit_strategy="worktree", worktree_root=str(repo / "worktrees"),
        )
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["config"]["policy_contract"]["worktree_roots_outside_repositories"])
        self.assertIn("repository_worktree_root_not_external", result["blockers_observed"])

    def test_external_worktree_root_is_accepted(self):
        repo = self.root / "repo"
        repo.mkdir()
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"].update(
            path=str(repo), allowed_modes=["explain", "review", "edit"],
            edit_strategy="worktree", worktree_root=str(self.root / "worktrees"),
        )
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertTrue(result["config"]["policy_contract"]["worktree_roots_ready_for_edit"])
        self.assertTrue(result["config"]["policy_contract"]["worktree_roots_outside_repositories"])

    def test_repository_without_source_path_is_rejected(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"].pop("path")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["config"]["policy_contract"]["repositories_valid"])
        self.assertIn("private_policy_repositories_invalid", result["blockers_observed"])

    def test_malformed_allowed_modes_fail_closed_without_crashing(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["repositories"]["app"]["allowed_modes"] = None
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["config"]["policy_contract"]["repositories_valid"])
        self.assertFalse(result["config"]["policy_contract"]["worktree_roots_ready_for_edit"])
        self.assertIn("private_policy_repositories_invalid", result["blockers_observed"])

    def test_model_intake_and_retired_policy_environment_fields_block(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["agent_intake_enabled"] = True
        payload["manual_workitems_enabled"] = False
        payload["engineering_cards_enabled"] = False
        payload["repositories"]["app"]["agent_allowed_modes"] = ["explain"]
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        with self.env.open("a", encoding="utf-8") as stream:
            stream.write("FEISHU_CODEX_WORKDIR=/tmp/legacy-workdir\n")
            stream.write("FEISHU_ALLOWED_OPEN_IDS=legacy-id\n")
        self.env.chmod(0o600)
        result = self.observe()
        blockers = set(result["blockers_observed"])
        self.assertIn("agent_intake_not_disabled", blockers)
        self.assertIn("agent_modes_not_empty", blockers)
        self.assertIn("legacy_environment_fields_present", blockers)
        self.assertIn("legacy_policy_fields_present", blockers)

    def test_dirty_submodule_is_not_suppressed(self):
        sha = "a" * 40
        service = {
            "ActiveState": "inactive", "SubState": "dead", "MainPID": "0",
            "WorkingDirectory": str(self.root), "UMask": "0077",
            "NoNewPrivileges": "yes", "PrivateTmp": "yes",
        }
        with mock.patch.object(PREFLIGHT, "service_observation", side_effect=[service, service]), \
                mock.patch.object(PREFLIGHT, "command", side_effect=[sha, " m submodule"]) as run:
            result = PREFLIGHT.probe(self.root, self.env, expected_sha=sha)
        self.assertTrue(result["checkout"]["dirty"])
        status_args = run.call_args_list[1].args[0]
        self.assertNotIn("--ignore-submodules=all", status_args)
        self.assertIn("--untracked-files=all", status_args)

    def test_expected_sha_mismatch_is_an_explicit_blocker(self):
        result = self.observe("b" * 40)
        self.assertFalse(result["checkout"]["matches_expected_sha"])
        self.assertIn("checkout_does_not_match_expected_sha", result["blockers_observed"])

    def test_invalid_expected_sha_is_rejected_before_observation(self):
        with mock.patch.object(PREFLIGHT, "service_observation") as service:
            with self.assertRaisesRegex(ValueError, "40-character"):
                PREFLIGHT.probe(self.root, self.env, expected_sha="not-a-sha")
        service.assert_not_called()

    def test_symlinked_private_policy_is_not_followed(self):
        target = self.root / "policy-target.json"
        self.write_policy(target)
        link = self.root / "policy-link.json"
        link.symlink_to(target)
        self.write_env(link)
        result = self.observe()
        self.assertEqual("unsafe_symlink_component", result["config"]["policy_file"])
        self.assertFalse(result["config"]["policy_parsed"])
        self.assertIn("explicit_private_policy_unreadable_or_absent", result["blockers_observed"])

    def test_policy_state_and_lock_must_be_explicit_and_match(self):
        payload = json.loads(self.policy.read_text(encoding="utf-8"))
        payload["state_db"] = "relative-state.sqlite3"
        payload["lock_file"] = str(self.root / "different.lock")
        self.policy.write_text(json.dumps(payload), encoding="utf-8")
        self.policy.chmod(0o600)
        result = self.observe()
        self.assertFalse(result["state"]["policy_state_explicit_and_matches"])
        self.assertFalse(result["state"]["policy_lock_explicit_and_matches"])
        self.assertFalse(result["state"]["paths_explicit_in_policy"])

    def test_private_reader_rejects_symlinks_and_fifo_without_blocking(self):
        target = self.root / "target.env"
        target.write_text("FEISHU_APP_SECRET=do-not-read\n", encoding="utf-8")
        target.chmod(0o600)
        link = self.root / "link.env"
        link.symlink_to(target)
        self.assertEqual("unsafe_symlink_component", PREFLIGHT.info(link))
        with self.assertRaises(ValueError):
            PREFLIGHT.read_private(link)
        fifo = self.root / "private.fifo"
        os.mkfifo(str(fifo), 0o600)
        self.assertEqual("unsafe_type", PREFLIGHT.info(fifo))
        with self.assertRaises((OSError, ValueError)):
            PREFLIGHT.read_private(fifo)

    def test_parent_chain_permissions_match_migration_gate(self):
        shared = self.root / "shared-parent"
        shared.mkdir(mode=0o700)
        private = shared / "private"
        private.mkdir(mode=0o700)
        policy = private / "policy.json"
        policy.write_text("{}", encoding="utf-8")
        policy.chmod(0o600)
        shared.chmod(0o777)
        self.assertEqual("unsafe_parent_unsafe_permissions", PREFLIGHT.info(policy))
        with self.assertRaisesRegex(ValueError, "unsafe parent"):
            PREFLIGHT.read_private(policy)

    def test_private_environment_parser_exposes_only_presence_to_report(self):
        values = PREFLIGHT.read_env(self.env)
        self.assertEqual("secret-must-not-appear", values["FEISHU_APP_SECRET"])
        result = self.observe()
        fields = result["config"]["environment_fields_present"]
        self.assertTrue(fields["FEISHU_APP_SECRET"])
        self.assertTrue(fields["FEISHU_AGENT_OPENAI_API_KEY"])
        self.assertTrue(fields["FEISHU_AGENT_GITHUB_WRITE_TOKEN"])
        self.assertNotIn("secret-must-not-appear", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
