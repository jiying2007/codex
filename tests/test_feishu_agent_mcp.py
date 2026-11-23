"""Offline local MCP intake tests; never call a model or Feishu network."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_agent_mcp, feishu_codex_bot
from tools.codex_assets.feishu_engineering_agent.manual_items import ManualWorkItemService
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent


class FeishuAgentMCPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="feishu-agent-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        (self.tmp / ".git").mkdir()
        self.agent_home = self.tmp.parent / (self.tmp.name + "-agent-codex-home")
        self.agent_home.mkdir(mode=0o700)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.agent_home, ignore_errors=True))
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
            "FEISHU_AGENT_CODEX_HOME": str(self.agent_home),
            "FEISHU_AGENT_BILLING_SOURCE": "external_api_key",
            "OPENAI_API_KEY": "sk-test-agent-key",
        }
        self.write_policy()

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_path.chmod(0o600)

    def intake(self) -> feishu_agent_mcp.AgentTaskIntake:
        config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        return feishu_agent_mcp.AgentTaskIntake(config)

    def workitem_attempt(self):
        self.policy["manual_workitems_enabled"] = True
        self.policy["repositories"]["codex"]["agent_allowed_modes"] = [
            "explain", "review", "edit",
        ]
        self.write_policy()
        intake = self.intake()
        manual_db = self.tmp / "feishu-engineering-agent.sqlite3"
        manual = ManualWorkItemService(manual_db)
        source_event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_source",
            "/wi add tapd 缺陷 space1 bug123 repo=codex | 修复缺陷并补充回归验收",
        )
        source_reply = manual.handle(source_event, "codex", {"codex"})
        source_run = source_reply.split("AgentRun：", 1)[1].split("\n", 1)[0]
        scope = "先完成根因分析、SDD、隔离修改和回归验证；验收：缺陷不再复现。"
        attempt_event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_attempt",
            "/wi attempt " + source_run + " edit | " + scope,
        )
        attempt_reply = manual.handle(attempt_event, "codex", {"codex"})
        run_id = attempt_reply.split("新Run：", 1)[1].split("\n", 1)[0]
        return intake, manual, run_id, scope

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
        self.assertFalse((intake.spool.root / f"{queued['id']}.json").exists())
        self.assertFalse(intake.store.mark_queued_unknown(queued["id"], "StalePoll"))
        self.assertEqual("canceled", intake.get_task(queued["id"])["status"])
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

    def test_workitem_run_queues_through_existing_bot_and_tracks_ci_gate(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            submitted = intake.submit_workitem_task(run_id, scope)
            popen.assert_not_called()
        self.assertTrue(submitted["created"])
        self.assertEqual("queued", submitted["status"])
        self.assertEqual(run_id, submitted["agent_run_id"])
        link = intake.store.agent_run_link_for_run(run_id)
        self.assertIsNotNone(link)
        self.assertEqual(submitted["id"], link["task_id"])
        queued = intake.get_workitem_task(run_id)
        self.assertEqual("queued", queued["run_status"])
        self.assertEqual("queued", queued["task"]["status"])

        bot = feishu_codex_bot.FeishuCodexBot(
            intake.config, mock.Mock(), mock.Mock(),
            feishu_codex_bot.StateStore(intake.config.state_db),
        )
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        self.assertEqual("edit", job.mode)
        self.assertEqual(scope, job.task)
        bot._transition_agent_run(job.task_id, "running", strict=True)
        result = feishu_codex_bot.ExecutionResult(
            "本地修改完成", "codex/agent-run", "a" * 40, self.tmp,
        )
        bot._finish_agent_run(job, result)
        final = intake.get_workitem_task(run_id)
        self.assertEqual("waiting_ci", final["run_status"])
        with sqlite3.connect(str(manual.store.path)) as db:
            evidence = db.execute(
                "SELECT evidence_type,reference,verified FROM fea_evidence WHERE run_id=?",
                (run_id,),
            ).fetchone()
        self.assertEqual(("commit", "a" * 40, 0), evidence)

    def test_workitem_task_rejects_scope_drift_and_shared_billing(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        with self.assertRaisesRegex(ValueError, "scope"):
            intake.submit_workitem_task(run_id, scope + " 改动")
        self.assertEqual("proposed", manual.store.get_run(run_id)["status"])
        connection = intake.store._connect()
        try:
            task_count = connection.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(0, task_count)
        shared = feishu_agent_mcp.AgentTaskIntake(
            intake.config, billing_source="codex_shared",
        )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "独立非共享计费身份"):
            shared.submit_workitem_task(run_id, scope)

    def test_workitem_task_requires_billing_and_repo_policy_to_remain_current(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        self.policy["repositories"]["codex"]["agent_allowed_modes"] = ["explain", "review"]
        self.write_policy()
        revoked_config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        bot = feishu_codex_bot.FeishuCodexBot(
            revoked_config, mock.Mock(), mock.Mock(),
            feishu_codex_bot.StateStore(revoked_config.state_db),
        )
        bot.refill_pending(startup=True)
        self.assertEqual("unknown", manual.store.get_run(run_id)["status"])
        self.assertEqual("unknown", intake.get_task(submitted["id"])["status"])

    def test_workitem_task_cancel_updates_agent_run(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        canceled = intake.cancel_queued_task(submitted["id"])
        self.assertTrue(canceled["queued_cancelled"])
        self.assertEqual("canceled", manual.store.get_run(run_id)["status"])

    def test_jsonrpc_initialize_list_call_and_notifications(self) -> None:
        intake = self.intake()
        def invoke(message: object) -> dict | None:
            return feishu_agent_mcp.handle_request(message, intake)
        hello = invoke({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual("2025-06-18", hello["result"]["protocolVersion"])
        listing = invoke({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(
            {"submit_task", "submit_workitem_task", "get_workitem_task",
             "get_task", "cancel_queued_task"},
            {tool["name"] for tool in listing["result"]["tools"]},
        )
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
