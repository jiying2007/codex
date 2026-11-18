from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.codex_assets.session_bootstrap import BootstrapError, build_envelope, configure_parser, main

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = (
    "manifests/session_bootstrap.json",
    "manifests/provider-locks/agent-dev-kit.json",
    "scripts/knowledge-provider.sh",
)


class DailyBootstrapIndependenceTests(unittest.TestCase):
    """Actual local provider-source verification; no model or retired repository."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / "runtime"
        self.knowledge = pathlib.Path(self.temp.name) / "knowledge-hub"
        self.knowledge.mkdir()
        for relative in CORE[:2]:
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, dest)
        adapter = self.root / CORE[2]
        adapter.parent.mkdir(parents=True)
        adapter.write_text("# Test-only provider adapter is not executed.\n", encoding="utf-8")
        (self.knowledge / "registry").mkdir()
        source = self.knowledge / "fixture-source.txt"
        source.write_text("exact fixture source")
        (self.knowledge / "tools").mkdir()
        manifest = self.knowledge / "registry/provider-runtime-files.json"
        manifest.write_text(json.dumps({
            "schema_version": 1, "inventory_roots": ["tools"],
            "files": {"fixture-source.txt": hashlib.sha256(source.read_bytes()).hexdigest()},
        }))
        provider = self.root / "manifests/provider-locks/knowledge-hub.json"
        provider.write_text(json.dumps({
            "repository": "jiying2007/knowledge-hub", "protocol_version": 4,
            "provider_commit": "a" * 40,
            "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }))

    def argv(self, mode, *extra):
        return ["--root", str(self.root), "--cwd", self.temp.name,
                "--mode", mode, "--knowledge-root", str(self.knowledge), *extra]

    def envelope(self, mode, *extra):
        return build_envelope(configure_parser().parse_args(self.argv(mode, *extra)))

    def assert_daily(self, result, mode):
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], mode)
        self.assertTrue(result["claims"]["runtime_local_only"])
        self.assertTrue(result["claims"]["project_acceptance_owned_by_project"])
        for forbidden in ("digital_worker", "governance_escalation", "work_identity", "execution_source_set"):
            self.assertNotIn(forbidden, result)
        self.assertEqual(result["runtime_binding"]["readiness"], "SOURCE_SET_BOUND")

    def test_modes_work_without_retired_repository(self):
        for mode in ("L0", "L1"):
            with self.subTest(mode=mode):
                self.assert_daily(self.envelope(mode), mode)

    def test_invalid_adk_lock_fails_for_both_modes(self):
        path = self.root / CORE[1]
        lock = json.loads(path.read_text())
        lock["binding_status"] = "unverified"
        path.write_text(json.dumps(lock))
        for mode in ("L0", "L1"):
            with self.subTest(mode=mode), self.assertRaisesRegex(BootstrapError, "ADK provider lock"):
                self.envelope(mode)

    def test_missing_provider_degrades_l0_and_blocks_l1(self):
        self.knowledge = self.knowledge / "nonexistent"
        self.assertIn("knowledge_provider_unavailable", self.envelope("L0")["degraded_reasons"])
        self.assertEqual(self.envelope("L1")["blocked_reasons"], ["knowledge_provider_unavailable"])

    def test_source_drift_is_not_ready(self):
        (self.knowledge / "fixture-source.txt").write_text("unreviewed drift")
        a, b = self.envelope("L0"), self.envelope("L1")
        self.assertIn("knowledge_provider_source_drift", a["degraded_reasons"])
        self.assertEqual(b["status"], "blocked")
        self.assertIn("knowledge_provider_source_drift", b["blocked_reasons"])

    def test_required_assets_are_checked(self):
        for relative in CORE:
            path = self.root / relative
            raw = path.read_bytes()
            path.unlink()
            with self.subTest(relative=relative), self.assertRaisesRegex(BootstrapError, "required Runtime Binding asset"):
                self.envelope("L1")
            path.write_bytes(raw)

    def test_external_cwd_and_empty_home_does_not_create_retired_checkout(self):
        home = pathlib.Path(self.temp.name) / "empty-home"
        home.mkdir()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/codex_assets/session_bootstrap.py"),
             *self.argv("L1", "--summary-json")],
            cwd=self.temp.name, env={**os.environ, "HOME": str(home)},
            text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_daily(json.loads(proc.stdout), "L1")
        self.assertEqual(list(home.iterdir()), [])

    def test_formal_request_is_rejected_not_downgraded(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), self.assertRaises(SystemExit) as exc:
            main(self.argv("L1", "--formal"))
        self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
