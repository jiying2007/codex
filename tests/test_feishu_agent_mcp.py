"""Offline local MCP intake tests; never call a model or Feishu network."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_agent_mcp, feishu_codex_bot
from tools.codex_assets.feishu_engineering_agent.manual_items import ManualWorkItemService
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent, IntakeRejected
from tools.codex_assets.feishu_engineering_agent.sessions import parse_exec_turn

THREAD_ID = "01979c6c-0354-7000-8000-000000000001"


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
            "OPENAI_API_KEY": "fixture-agent-api-key",
        }
        self.write_policy()

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_path.chmod(0o600)

    def intake(self) -> feishu_agent_mcp.AgentTaskIntake:
        config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        return feishu_agent_mcp.AgentTaskIntake(config)

    def workitem_attempt(self, mode: str = "edit"):
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
            "/wi attempt " + source_run + " " + mode + " | " + scope,
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

    def test_native_exec_receipt_requires_exact_thread_and_terminal_turn(self) -> None:
        frames = [
            {"type": "thread.started", "thread_id": THREAD_ID},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "private log"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "分析完成"}},
            {"type": "turn.completed", "usage": {}},
        ]
        def jsonl(events):
            return "\n".join(json.dumps(event) for event in events)
        self.assertEqual((THREAD_ID, "分析完成"), parse_exec_turn(jsonl(frames)))
        for invalid in (
            frames[:-1],
            frames[1:],
            frames[:2] + [{"type": "turn.failed"}],
            frames[:1] + frames,
            frames + [{"type": "error"}],
            [{"type": "thread.started", "thread_id": "not-a-uuid"}] + frames[1:],
        ):
            with self.assertRaises(IntakeRejected):
                parse_exec_turn(jsonl(invalid))
        with self.assertRaises(IntakeRejected):
            parse_exec_turn("not JSONL")

    def test_native_workitem_exec_uses_persistent_jsonl_without_model(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt("read")
        submitted = intake.submit_workitem_task(run_id, scope)
        bot = feishu_codex_bot.FeishuCodexBot(
            intake.config, mock.Mock(), mock.Mock(), intake.store,
        )
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        runner = feishu_codex_bot.CodexRunner(intake.config)
        frames = [
            {"type": "thread.started", "thread_id": THREAD_ID},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "完成"}},
            {"type": "turn.completed", "usage": {}},
        ]
        process = mock.Mock()
        process.returncode = 0
        process.communicate.return_value = ("\n".join(json.dumps(f) for f in frames), "")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            result = runner.run(job, "", persistent_session=True)
        arguments = popen.call_args.args[0]
        self.assertIn("--json", arguments)
        self.assertNotIn("--ephemeral", arguments)
        self.assertIn("read-only", arguments)
        self.assertEqual(THREAD_ID, result.thread_id)
        self.assertEqual(self.tmp, result.thread_cwd)
        self.assertEqual("完成", result.text)
        self.assertIsNone(result.worktree_path)
        process.communicate.return_value = ('{"type":"thread.started"}', "")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process):
            with self.assertRaises(feishu_codex_bot.CodexOutcomeUnknown):
                runner.run(job, "", persistent_session=True)

    def test_agent_codex_identity_isolated_from_personal_home_and_auth(self) -> None:
        config = self.intake().config
        runner = feishu_codex_bot.CodexRunner(config)
        job = feishu_codex_bot.BotJob(
            91, "agent:test", "oc_test", f"agent:{__import__('os').getuid()}",
            "task", "codex", "review", "只读检查",
        )
        with mock.patch.dict("os.environ", {
            "PATH": "/usr/bin", "HOME": "/home/service",
            "CODEX_HOME": "/home/service/.codex",
            "OPENAI_API_KEY": "fixture-personal-api-key",
            "FEISHU_APP_SECRET": "must-not-leak",
            "FEISHU_AGENT_BILLING_SOURCE": "must-not-leak",
        }, clear=True):
            environment = runner._execution_environment(job)
        self.assertEqual(str(self.agent_home), environment["HOME"])
        self.assertEqual(str(self.agent_home), environment["CODEX_HOME"])
        self.assertEqual("fixture-agent-api-key", environment["OPENAI_API_KEY"])
        self.assertNotIn("/home/service/.codex", environment.values())
        self.assertNotIn("FEISHU_APP_SECRET", environment)
        self.assertNotIn("FEISHU_AGENT_BILLING_SOURCE", environment)

    def test_agent_codex_home_rejects_account_auth_file_and_missing_api_key(self) -> None:
        auth = self.agent_home / "auth.json"
        auth.write_text('{"tokens":"not-a-real-token"}', encoding="utf-8")
        auth.chmod(0o600)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "auth.json"):
            feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        auth.unlink()
        values = dict(self.values)
        values.pop("OPENAI_API_KEY")
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "OPENAI_API_KEY"):
            feishu_codex_bot.BotConfig.from_values(values, self.tmp)

    def test_orphaned_legacy_task_is_unknown_and_never_rebound_to_workitem(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        idempotency_key = "workitem-" + run_id
        message_id = "agent:" + hashlib.sha256(
            (intake.sender + "\0" + idempotency_key).encode("utf-8")
        ).hexdigest()
        digest = hashlib.sha256(json.dumps(
            {"repo": "codex", "mode": "edit", "task": scope},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        task_id, created = intake.store.create_agent_task(
            message_id, intake.sender, "codex", "edit", digest,
            intake.config.queue_size,
        )
        self.assertTrue(created)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "marked UNKNOWN"):
            intake.submit_workitem_task(run_id, scope)
        self.assertEqual("unknown", intake.get_task(task_id)["status"])
        self.assertEqual("unknown", manual.store.get_run(run_id)["status"])
        self.assertIsNone(intake.store.agent_run_link_for_task(task_id))

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
        expected = intake.config.repository("codex").worktree_root / f"task-{job.task_id}"
        result = feishu_codex_bot.ExecutionResult(
            "本地修改完成", "codex/agent-run", "a" * 40, expected,
            thread_id=THREAD_ID, thread_cwd=expected,
        )
        bot.runner.run.return_value = result
        bot.transport.resolve_sources.return_value = ""
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        bot.runner.run.assert_called_once_with(job, "", persistent_session=True)
        final = intake.get_workitem_task(run_id)
        self.assertEqual("waiting_ci", final["run_status"])
        self.assertEqual("completed", final["task"]["status"])
        self.assertEqual(THREAD_ID, final["session"]["thread_id"])
        self.assertEqual(str(expected), final["session"]["repo_path"])
        self.assertEqual(str(self.agent_home), final["session"]["codex_home"])
        with sqlite3.connect(str(manual.store.path)) as db:
            evidence = db.execute(
                "SELECT evidence_type,reference,verified FROM fea_evidence WHERE run_id=?",
                (run_id,),
            ).fetchone()
        self.assertEqual(("commit", "a" * 40, 0), evidence)

    def test_restart_reconciles_persisted_agent_run_receipt(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        bot = feishu_codex_bot.FeishuCodexBot(
            intake.config, mock.Mock(), mock.Mock(),
            feishu_codex_bot.StateStore(intake.config.state_db),
        )
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        self.assertTrue(bot.store.claim_queued(job.task_id))
        bot._transition_agent_run(job.task_id, "running", strict=True)
        commit = "b" * 40
        expected = intake.config.repository("codex").worktree_root / f"task-{job.task_id}"
        bot.store.record_result(job.task_id, "codex/agent-run", commit, expected)
        bot._finish_agent_run(
            job,
            feishu_codex_bot.ExecutionResult(
                "本地修改完成", "codex/agent-run", commit, expected,
                thread_id=THREAD_ID, thread_cwd=expected,
            ),
        )
        self.assertEqual("running", intake.get_task(submitted["id"])["status"])
        self.assertEqual("waiting_ci", manual.store.get_run(run_id)["status"])

        # Simulate a crash after the AgentRun receipt was persisted but before
        # the legacy task status was updated to completed.
        bot.recover_pending()
        self.assertEqual("completed", intake.get_task(submitted["id"])["status"])
        self.assertEqual("waiting_ci", manual.store.get_run(run_id)["status"])

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
        self.policy["repositories"]["codex"]["verification_commands"] = [
            ["git", "diff", "--check"],
            ["git", "status", "--short"],
        ]
        self.write_policy()
        revoked_config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        bot = feishu_codex_bot.FeishuCodexBot(
            revoked_config, mock.Mock(), mock.Mock(),
            feishu_codex_bot.StateStore(revoked_config.state_db),
        )
        bot.refill_pending(startup=True)
        self.assertEqual("unknown", manual.store.get_run(run_id)["status"])
        self.assertEqual("unknown", intake.get_task(submitted["id"])["status"])

    def test_read_workitem_attempt_maps_to_existing_explain_mode(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt("read")
        submitted = intake.submit_workitem_task(run_id, scope)
        self.assertEqual("explain", submitted["mode"])
        self.assertEqual("queued", submitted["status"])
        run = manual.store.get_run(run_id)
        self.assertEqual("queued", run["status"])
        self.assertEqual("read", run["mode"])

    def test_workitem_policy_fingerprint_binds_api_credential_rotation(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        self.values["OPENAI_API_KEY"] = "fixture-rotated-api-key"
        rotated_config = feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)
        bot = feishu_codex_bot.FeishuCodexBot(
            rotated_config, mock.Mock(), mock.Mock(),
            feishu_codex_bot.StateStore(rotated_config.state_db),
        )
        bot.refill_pending(startup=True)
        self.assertEqual("unknown", intake.get_task(submitted["id"])["status"])
        self.assertEqual("unknown", manual.store.get_run(run_id)["status"])

    def test_gateway_url_rejects_embedded_credentials_and_query(self) -> None:
        values = dict(self.values)
        values["FEISHU_AGENT_BILLING_SOURCE"] = "external_gateway"
        values["OPENAI_BASE_URL"] = "https://user:password@gateway.example/v1?token=secret"
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "不含凭据"):
            feishu_codex_bot.BotConfig.from_values(values, self.tmp)

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
