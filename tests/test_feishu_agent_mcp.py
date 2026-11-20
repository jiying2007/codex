"""Offline local MCP intake tests; never call a model or Feishu network."""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_agent_mcp, feishu_codex_bot


class FeishuAgentMCPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="feishu-agent-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        (self.tmp / ".git").mkdir()
        self.policy_path = self.tmp / "agent-config.json"
        self.policy = {
            "schema_version": 1,
            "default_repo": "codex",
            "allowed_open_ids": ["ou_owner"],
            "repositories": {
                "codex": {
                    "path": str(self.tmp),
                    "allowed_modes": ["explain", "review", "edit"],
                    "agent_allowed_modes": ["explain", "review"],
                    "edit_strategy": "worktree",
                    "worktree_root": str(self.tmp.parent / (self.tmp.name + "-worktrees")),
                },
            },
            "agent_intake_enabled": True,
            "queue_size": 4,
            "state_db": str(self.tmp / "state.sqlite3"),
            "lock_file": str(self.tmp / "instance.lock"),
        }
        self.values = {
            "FEISHU_APP_ID": "cli_testing",
            "FEISHU_APP_SECRET": "not-used",
            "FEISHU_TARGET_CHAT_ID": "oc_test",
            "FEISHU_BOT_CONFIG": str(self.policy_path),
        }
        self.write_policy()

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_path.chmod(0o600)

    def intake(self) -> feishu_agent_mcp.AgentTaskIntake:
        config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        return feishu_agent_mcp.AgentTaskIntake(config)

    def test_disabled_and_write_permission_fail_closed(self) -> None:
        self.policy.pop("agent_intake_enabled")
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未获允许"):
            self.intake().submit_task("codex", "review", "只读分析", "case-000001")
        self.policy["agent_intake_enabled"] = True
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未获允许"):
            self.intake().submit_task("codex", "edit", "修改", "case-000002")
        self.policy["repositories"]["codex"]["agent_allowed_modes"].append("edit")
        self.policy["repositories"]["codex"]["edit_strategy"] = "in_place"
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "必须使用隔离"):
            self.intake()

    def test_idempotent_submit_and_existing_bot_recovers_it(self) -> None:
        first = self.intake().submit_task("codex", "review", "检查代码", "case-000003")
        self.assertEqual("queued", first["status"])
        self.assertTrue(first["created"])
        again = self.intake().submit_task("codex", "review", "检查代码", "case-000003")
        self.assertFalse(again["created"])
        self.assertEqual(first["id"], again["id"])
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "内容不同"):
            self.intake().submit_task("codex", "review", "别的代码", "case-000003")
        config = self.intake().config
        bot = feishu_codex_bot.FeishuCodexBot(
            config, mock.Mock(), mock.Mock(), feishu_codex_bot.StateStore(config.state_db),
        )
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        self.assertEqual("检查代码", job.task)
        self.assertTrue(job.sender_open_id.startswith("agent:"))
        self.assertEqual(first["id"], job.task_id)
        self.assertEqual("queued", self.intake().get_task(first["id"])["status"])

    def test_cancel_only_queued_not_running_or_foreign_user(self) -> None:
        intake = self.intake()
        queued = intake.submit_task("codex", "explain", "解释", "case-000004")
        self.assertTrue(intake.cancel_queued_task(queued["id"])["queued_cancelled"])
        self.assertEqual("canceled", intake.get_task(queued["id"])["status"])
        self.assertFalse(intake.cancel_queued_task(queued["id"])["queued_cancelled"])
        running = intake.submit_task("codex", "review", "分析", "case-000005")
        self.assertTrue(intake.store.claim_queued(running["id"]))
        stopped = intake.cancel_queued_task(running["id"])
        self.assertFalse(stopped["queued_cancelled"])
        self.assertTrue(stopped["running_cancel_requires_feishu"])
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "不属于"):
            intake.get_task(999999)

    def test_queue_limit_and_no_implicit_model_process(self) -> None:
        self.policy["queue_size"] = 1
        self.write_policy()
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            intake = self.intake()
            intake.submit_task("codex", "review", "第一次", "case-000006")
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "队列已满"):
                intake.submit_task("codex", "review", "第二次", "case-000007")
            popen.assert_not_called()

    def test_jsonrpc_initialize_list_call_and_notifications(self) -> None:
        intake = self.intake()
        def invoke(message: object) -> dict | None:
            return feishu_agent_mcp.handle_request(message, intake)
        hello = invoke({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual("2025-06-18", hello["result"]["protocolVersion"])
        listing = invoke({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual({"submit_task", "get_task", "cancel_queued_task"},
                         {tool["name"] for tool in listing["result"]["tools"]})
        output = invoke({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "submit_task", "arguments": {
                "repo": "codex", "mode": "review", "task": "分析",
                "idempotency_key": "case-000008",
            }},
        })
        self.assertFalse(output["result"]["isError"])
        self.assertEqual("queued", json.loads(output["result"]["content"][0]["text"])["status"])
        self.assertIsNone(invoke({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        invalid = invoke({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                          "params": {"name": "submit_task", "arguments": {"repo": "codex"}}})
        self.assertTrue(invalid["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
