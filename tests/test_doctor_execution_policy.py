"""Doctor and runtime share source validation; disposable homes are not live certification."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.test_governance import make_repo, write_json
from tools.codex_assets.core import CodexAssetError, Repo, apply_plan, build_repo, plan_apply, rollback_plan
from tools.codex_assets.execution_policy_adapter import ExecutionPolicyAdapterError, load_runtime_config
from tools.codex_assets.governance import governance_errors, governance_report
from tools.codex_assets.validate import validate_repo

ROOT = Path(__file__).resolve().parents[1]


class DoctorPolicyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = make_repo(self)
        self.path = self.root / "manifests/execution_policy.json"
        self.original = self.path.read_bytes()

    def assert_rejected(self) -> None:
        with self.assertRaises(ExecutionPolicyAdapterError):
            load_runtime_config(self.root)
        self.assertTrue(governance_errors(Repo.from_path(self.root)))
        try:
            errors = validate_repo(self.root)
        except CodexAssetError:
            return  # CLI translates unreadable JSON to its existing fatal exit.
        self.assertTrue(errors)

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tools.codex_assets", *args, "--root", str(self.root)],
            cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(ROOT), "HOME": str(self.root / "empty-home")},
            text=True, capture_output=True, check=False, timeout=15,
        )

    def test_valid_config_passes_without_state_or_digital_worker(self) -> None:
        with patch("sqlite3.connect", side_effect=AssertionError("doctor must not read sessions")):
            self.assertEqual([], validate_repo(self.root))
            self.assertEqual([], governance_errors(Repo.from_path(self.root)))
            report = governance_report(self.root)
        self.assertEqual(2, report["schema_version"])
        self.assertNotIn("runtime_control", report)
        self.assertEqual("runtime_control.policy/v2", report["execution_policy"]["policy_schema"])
        self.assertFalse((self.root / "empty-home").exists())

    def test_missing_active_manifest_fails(self) -> None:
        self.path.unlink()
        self.assert_rejected()

    def test_old_manifest_never_substitutes_for_active_manifest(self) -> None:
        self.path.unlink()
        write_json(self.root / "manifests/runtime_control.json", {})
        self.assert_rejected()

    def test_old_manifest_alongside_valid_config_is_rejected(self) -> None:
        write_json(self.root / "manifests/runtime_control.json", {})
        self.assert_rejected()

    def test_malformed_nonobject_or_legacy_config_fails(self) -> None:
        legacy = json.loads(self.original)
        legacy["schema_version"] = 1
        for value in ("{", "null", "42", "[]", json.dumps(legacy)):
            with self.subTest(value=value[:30]):
                self.path.write_text(value, encoding="utf-8")
                self.assert_rejected()

    def test_policy_v1_and_weakened_gate_or_retention_fail(self) -> None:
        for mutation in ("v1", "artifact-floor", "raw-retention"):
            value = json.loads(self.original)
            if mutation == "v1":
                value["policy"]["schema_version"] = "runtime_control.policy/v1"
            elif mutation == "artifact-floor":
                value["policy"]["artifact_applicability"]["implementation"]["apply"] = []
            else:
                value["policy"]["retention"]["raw_content_stored"] = True
            with self.subTest(mutation=mutation):
                write_json(self.path, value)
                self.assert_rejected()

    def test_bad_sources_fail_without_path_resolution(self) -> None:
        for sources in (None, [], {}, {"state_db": 42, "sessions_root": "", "journal_dir": ""},
                        {"state_db": "secret\x00path", "sessions_root": "", "journal_dir": ""}):
            value = json.loads(self.original)
            value["sources"] = sources
            with self.subTest(sources=sources):
                write_json(self.path, value)
                self.assert_rejected()

    def test_provider_identity_drift_and_absence_fail(self) -> None:
        path = self.root / "manifests/provider-locks/agent-dev-kit.json"
        value = json.loads(path.read_text())
        value["provider_commit"] = "0" * 40
        write_json(path, value)
        self.assert_rejected()
        path.unlink()
        self.assert_rejected()

    def test_each_source_blob_drift_or_absence_fails(self) -> None:
        for filename in ("__init__.py", "contracts.py", "decision.py", "reducer.py"):
            path = self.root / "tools/codex_assets/execution_policy" / filename
            original = path.read_bytes()
            with self.subTest(filename=filename):
                path.write_bytes(original + b"\n# changed\n")
                self.assert_rejected()
                path.unlink()
                self.assert_rejected()
                path.write_bytes(original)

    def test_rejected_governance_report_does_not_print_pass(self) -> None:
        self.path.write_text("{}", encoding="utf-8")
        result = self.cli("governance-report", "--summary-json")
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('"status": "pass"', result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_config_repo_cli_fails_without_traceback(self) -> None:
        self.path.write_text("null", encoding="utf-8")
        result = self.cli("doctor", "--scope", "repo")
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)


class DisposableDoctorLifecycleTests(unittest.TestCase):
    def test_all_doctor_scopes_install_noop_and_rollback(self) -> None:
        for profile in ("default", "team-collab"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root = base / "source"
                shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(
                    ".git", "build", "__pycache__", ".adk-upgrade-source"))
                home = base / "home"
                target = home / ".codex"
                protected = {"auth.json": b"test-credential-placeholder", "sessions/keep": b"test-session", "skills/.system/keep": b"test-system"}
                for relative, data in protected.items():
                    path = target / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(root), "CODEX_OFFLINE_HERMETIC": "1"}

                def doctor(scope: str) -> None:
                    result = subprocess.run(
                        [sys.executable, "-m", "tools.codex_assets", "doctor", "--root", str(root),
                         "--scope", scope, "--target", str(target)],
                        cwd=base, env=env, text=True, capture_output=True, check=False, timeout=20,
                    )
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)

                doctor("repo")
                doctor("governance")
                build = build_repo(root, profile)
                doctor("build")
                plan = plan_apply(root, build, target, base / "backup", overwrite=False, prune_stale=True)
                apply_plan(plan, dry_run=True)
                self.assertFalse((target / "control/state/managed-files.json").exists())
                apply_plan(plan, dry_run=False)
                doctor("live")
                doctor("all")
                self.assertEqual(0, plan_apply(root, build, target, base / "noop", False, True)["content_changes"])
                plan_path = base / "plan.json"
                write_json(plan_path, plan)
                with contextlib.redirect_stdout(io.StringIO()):
                    result = rollback_plan(plan_path)
                self.assertEqual(0, result["skipped"])
                self.assertFalse((target / "skills/adk-runtime-router").exists())
                for relative, data in protected.items():
                    self.assertEqual(data, (target / relative).read_bytes())


if __name__ == "__main__":
    unittest.main()
