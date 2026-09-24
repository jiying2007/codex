from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agent_rules_validator", ROOT / "scripts/validate-agent-rules.py")
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class AgentRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.original = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.write_rules(self.original)
        for name in ("assets.json", "profiles.json"):
            target = self.root / "manifests" / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes((ROOT / "manifests" / name).read_bytes())

    def write_rules(self, text: str) -> None:
        for relative in ("AGENTS.md", "src/codex-home/AGENTS.md"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_current_rules_pass_within_original_budget(self) -> None:
        self.assertLessEqual(VALIDATOR.validate_rules(self.root), 4500)

    def test_source_drift_is_rejected(self) -> None:
        (self.root / "src/codex-home/AGENTS.md").write_text("drift", encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "SSOT drift"):
            VALIDATOR.validate_rules(self.root)

    def test_each_retired_surface_is_rejected(self) -> None:
        for token in VALIDATOR.FORBIDDEN:
            self.write_rules(self.original + "\n" + token)
            with self.subTest(token=token), self.assertRaisesRegex(AssertionError, "retired runtime"):
                VALIDATOR.validate_rules(self.root)

    def test_each_required_surface_is_enforced(self) -> None:
        for token in VALIDATOR.REQUIRED:
            self.write_rules(self.original.replace(token, ""))
            with self.subTest(token=token), self.assertRaisesRegex(AssertionError, "required terminal"):
                VALIDATOR.validate_rules(self.root)

    def test_context_budget_is_not_relaxed(self) -> None:
        self.write_rules(self.original + "x" * 4501)
        with self.assertRaisesRegex(AssertionError, "byte budget"):
            VALIDATOR.validate_rules(self.root)

    def test_unknown_skill_search_profile_is_rejected(self) -> None:
        self.write_rules(self.original.replace("--profile default", "--profile nonexistent"))
        with self.assertRaisesRegex(AssertionError, "undeclared profile"):
            VALIDATOR.validate_rules(self.root)

    def test_unknown_descriptive_profile_is_rejected(self) -> None:
        self.write_rules(self.original.replace("`default/team-collab`", "`nonexistent/team-collab`"))
        with self.assertRaisesRegex(AssertionError, "undeclared profile"):
            VALIDATOR.validate_rules(self.root)

    def test_default_profile_must_follow_manifest(self) -> None:
        path = self.root / "manifests/assets.json"
        assets = json.loads(path.read_text(encoding="utf-8"))
        assets["default_profile"] = "team-collab"
        path.write_text(json.dumps(assets), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "differs from manifest"):
            VALIDATOR.validate_rules(self.root)

    def test_default_must_be_declared(self) -> None:
        path = self.root / "manifests/profiles.json"
        profiles = json.loads(path.read_text(encoding="utf-8"))
        profiles["profiles"] = [item for item in profiles["profiles"] if item["name"] != "default"]
        path.write_text(json.dumps(profiles), encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "not declared"):
            VALIDATOR.validate_rules(self.root)

    def test_final_command_requires_current_thread_before_invoking_tools(self) -> None:
        command = re.search(r"`(\(cd ~/codex && .*?\))`", self.original)
        self.assertIsNotNone(command)
        home = self.root / "home"
        (home / "codex").mkdir(parents=True)
        env = {**os.environ, "HOME": str(home)}
        env.pop("CODEX_THREAD_ID", None)
        result = subprocess.run(["bash", "-c", command.group(1)], env=env, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("current thread id required", result.stderr)
        self.assertNotIn("command not found", result.stderr)
        self.assertFalse((home / ".codex").exists())


if __name__ == "__main__":
    unittest.main()
