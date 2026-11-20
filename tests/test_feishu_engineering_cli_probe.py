"""Offline CLI runtime capability probe: only --version and --help."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.__main__ import main


class EngineeringAgentCLITest(unittest.TestCase):
    def test_runtime_probe_does_not_launch_model(self):
        stdout = io.StringIO()
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.probe_local_app_server",
            return_value={"available": True, "qualified_for_model_calls": False},
        ) as probe:
            with contextlib.redirect_stdout(stdout):
                result = main(["--probe-runtime"])
        self.assertEqual(0, result)
        self.assertFalse(json.loads(stdout.getvalue())["qualified_for_model_calls"])
        probe.assert_called_once_with("codex")

    def test_unavailable_host_runtime_fails_closed(self):
        stdout = io.StringIO()
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.probe_local_app_server",
            return_value={"available": False, "failed_step": "version"},
        ):
            with contextlib.redirect_stdout(stdout):
                result = main(["--probe-runtime", "--codex-bin", "codex"])
        self.assertEqual(3, result)
        self.assertFalse(json.loads(stdout.getvalue())["available"])

    def test_probe_must_not_mix_with_text_or_repo_args(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main(["--probe-runtime", "--text", "修复代码"])
        self.assertEqual(2, raised.exception.code)

    def test_dry_run_still_requires_message(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                main(["--dry-run", "--allow-repo", "codex"])
        self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
