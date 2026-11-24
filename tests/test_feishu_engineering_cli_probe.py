"""Offline CLI runtime capability probe: only --version and --help."""
from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.__main__ import main
from tools.codex_assets.feishu_engineering_agent.sessions import probe_local_cli


class EngineeringAgentCLITest(unittest.TestCase):
    def test_runtime_probe_does_not_launch_model(self):
        stdout = io.StringIO()
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.probe_local_cli",
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
            "tools.codex_assets.feishu_engineering_agent.sessions.probe_local_cli",
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

    def test_probe_only_runs_native_cli_help_without_credentials(self):
        fake = mock.Mock(returncode=0, stdout="fixture help", stderr="")
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.subprocess.run",
            return_value=fake,
        ) as called, mock.patch.dict("os.environ", {
            "FEISHU_APP_SECRET": "fixture-secret",
            "OPENAI_API_KEY": "fixture-personal-key",
            "FEISHU_AGENT_OPENAI_API_KEY": "fixture-agent-key",
        }):
            result = probe_local_cli()
        self.assertTrue(result["available"])
        self.assertFalse(result["qualified_for_model_calls"])
        self.assertEqual([
            ["codex", "--version"], ["codex", "exec", "--help"],
            ["codex", "exec", "resume", "--help"],
        ], [call.args[0] for call in called.call_args_list])
        for call in called.call_args_list:
            self.assertNotIn("OPENAI_API_KEY", call.kwargs["env"])
            self.assertNotIn("FEISHU_AGENT_OPENAI_API_KEY", call.kwargs["env"])
            self.assertNotIn("FEISHU_APP_SECRET", call.kwargs["env"])

    def test_probe_failure_stops_without_attempting_any_turn(self):
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.subprocess.run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="fixture"),
        ) as called:
            result = probe_local_cli()
        self.assertFalse(result["available"])
        self.assertEqual("version", result["failed_step"])
        self.assertEqual(1, called.call_count)


if __name__ == "__main__":
    unittest.main()
