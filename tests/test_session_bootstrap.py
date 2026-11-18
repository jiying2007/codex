from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.session_bootstrap import (
    BootstrapError, build_envelope, configure_parser, main, resolve_mode,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SessionBootstrapTests(unittest.TestCase):
    def parse(self, *flags: str):
        return configure_parser().parse_args(["--root", str(ROOT), *flags])

    def test_only_daily_modes_and_governed_precedence(self):
        self.assertEqual(resolve_mode("auto", governed=False), "L0")
        self.assertEqual(resolve_mode("auto", governed=True), "L1")
        self.assertEqual(resolve_mode("L1", governed=False), "L1")
        with self.assertRaisesRegex(BootstrapError, "conflicts"):
            resolve_mode("L0", governed=True)
        with self.assertRaisesRegex(BootstrapError, "only L0/L1"):
            resolve_mode("L2", governed=False)

    def test_formal_flags_and_mode_are_not_accepted(self):
        parser = configure_parser()
        for flags in (["--mode", "L2"], ["--formal"], ["--engineering-task-package", "e.json"],
                      ["--digital-worker-root", "/tmp/source"], ["--escalate-from-l1"]):
            with self.subTest(flags=flags), self.assertRaises(SystemExit) as caught:
                parser.parse_args(flags)
            self.assertEqual(caught.exception.code, 2)

    def test_l0_degrades_without_provider_without_faking_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_envelope(self.parse("--cwd", tmp, "--mode", "L0",
                                               "--knowledge-root", tmp + "/missing"))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], "L0")
        self.assertIn("knowledge_provider_unavailable", result["degraded_reasons"])
        self.assertEqual(result["runtime_binding"]["readiness"], "SOURCE_SET_BOUND")
        self.assertTrue(result["session_bootstrap_identity"].startswith("sha256:"))
        for forbidden in ("digital_worker", "execution_source_set", "work_identity", "governance_escalation"):
            self.assertNotIn(forbidden, result)

    def test_l1_requires_real_knowledge_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_envelope(self.parse("--cwd", tmp, "--governed",
                                               "--knowledge-root", tmp + "/missing"))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked_reasons"], ["knowledge_provider_unavailable"])

    def test_l1_ready_is_provider_preflight_not_approval(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch(
            "tools.codex_assets.knowledge_provider_adapter.verify_source",
            return_value={"provider_commit": "a" * 40, "source_manifest_sha256": "b" * 64}
        ):
            result = build_envelope(self.parse("--cwd", tmp, "--governed", "--knowledge-root", tmp))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], "L1")
        self.assertTrue(result["knowledge"]["execution_identity_verified"])
        self.assertEqual(result["agent_assets"]["provider_repository"], "jiying2007/agent-dev-kit")
        self.assertTrue(result["claims"]["project_acceptance_owned_by_project"])
        self.assertNotIn("digital_worker", json.dumps(result))
        self.assertNotIn("release_ready", json.dumps(result))

    def test_invalid_runtime_profile_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BootstrapError, "unsupported runtime profile"):
                build_envelope(self.parse("--cwd", tmp, "--runtime-profile", "unapproved"))


if __name__ == "__main__":
    unittest.main()
