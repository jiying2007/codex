"""Offline local MCP intake tests; never call a model or Feishu network."""
from __future__ import annotations

import concurrent.futures
import dataclasses
import os
import hashlib
import threading
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_agent_mcp, feishu_codex_bot
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
            "FEISHU_AGENT_BILLING_SOURCE": "external_gateway",
            "FEISHU_AGENT_OPENAI_API_KEY": "fixture-agent-api-key",
            "FEISHU_AGENT_OPENAI_BASE_URL": "https://gateway.example/v1",
            "FEISHU_AGENT_BUDGET_BACKEND": "litellm",
            "FEISHU_AGENT_BUDGET_MAX_USD": "10",
            "FEISHU_AGENT_BUDGET_KEY_ALIAS": "fixture-agent",
            "FEISHU_AGENT_MODEL": "fixture-model",
        }
        self.write_policy()
        # All runner tests use a deterministic provider response; no network.
        budget_patch = mock.patch("tools.codex_assets.feishu_engineering_agent.budget.read_key_info",
                                  return_value={"key": hashlib.sha256(b"fixture-agent-api-key").hexdigest(),
                                      "info": {"key_alias": "fixture-agent", "max_budget": 10, "spend": 1,
                                               "blocked": False, "budget_duration": None,
                                               "models": ["fixture-model"]}})
        budget_patch.start()
        self.addCleanup(budget_patch.stop)

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
        self.assertFalse((intake.spool.root / f"{queued['id']}.json").exists())
        self.assertFalse(intake.store.mark_queued_unknown(queued["id"], "StalePoll"))
        self.assertEqual("canceled", intake.get_task(queued["id"])["status"])
        running = intake.submit_task("codex", "review", "分析", "case-000005")
        self.assertTrue(intake.store.claim_queued(running["id"]))
        stopped = intake.cancel_queued_task(running["id"])
        self.assertFalse(stopped["queued_cancelled"])
        self.assertTrue(stopped["running_cancel_requires_operator"])
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

    def test_native_exec_uses_persistent_jsonl_without_model(self) -> None:
        intake = self.intake()
        intake.submit_task("codex", "explain", "只读分析", "native-fixture-001")
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
        self.assertIn('model_provider="feishu_agent_gateway"', arguments)
        with sqlite3.connect(str(intake.config.state_db)) as db:
            receipts = db.execute("SELECT phase, receipt_json FROM engineering_budget_receipts WHERE task_id=?", (job.task_id,)).fetchall()
        self.assertEqual({"before", "after"}, {row[0] for row in receipts})
        self.assertNotIn("fixture-agent-api-key", str(receipts))
        # Use a distinct synthetic task ID: each paid launch is effect-once.
        import dataclasses
        job = dataclasses.replace(job, task_id=job.task_id + 1000)
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
        values.pop("FEISHU_AGENT_OPENAI_API_KEY")
        values["OPENAI_API_KEY"] = "fixture-personal-key"
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "OPENAI_API_KEY"):
            feishu_codex_bot.BotConfig.from_values(values, self.tmp)


    def test_gateway_url_rejects_embedded_credentials_and_query(self) -> None:
        values = dict(self.values)
        values["FEISHU_AGENT_BILLING_SOURCE"] = "external_gateway"
        values["FEISHU_AGENT_OPENAI_BASE_URL"] = "https://user:password@gateway.example/v1?token=secret"
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "不含凭据"):
            feishu_codex_bot.BotConfig.from_values(values, self.tmp)


    def test_generic_agent_spool_digest_rejects_changed_prompt(self) -> None:
        intake = self.intake()
        submitted = intake.submit_task("codex", "review", "原任务", "fixture-tamper-001")
        payload = intake.spool.get(submitted["id"])
        intake.spool.discard(submitted["id"])
        payload["task"] = "替换任务"
        intake.spool.put(submitted["id"], payload)
        runner = mock.Mock()
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, mock.Mock(), runner, intake.store)
        bot.refill_pending(startup=True)
        self.assertEqual("unknown", intake.get_task(submitted["id"])["status"])
        self.assertEqual(0, bot.jobs.qsize())
        runner.run.assert_not_called()


    def test_jsonrpc_initialize_list_call_and_notifications(self) -> None:
        intake = self.intake()
        def invoke(message: object) -> dict | None:
            return feishu_agent_mcp.handle_request(message, intake)
        hello = invoke({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual("2025-06-18", hello["result"]["protocolVersion"])
        listing = invoke({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(
            {"submit_task", "get_task", "cancel_queued_task"},
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


    def queued_job(self, key="runner-fixture-001"):
        intake = self.intake()
        detail = intake.submit_task("codex", "review", "只读分析", key)
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, mock.Mock(), mock.Mock(), intake.store)
        bot.recover_pending()
        return intake, bot.jobs.get_nowait()

    def test_generic_submission_serializes_payload_before_visibility(self):
        intake = self.intake()
        entered, release = threading.Event(), threading.Event()
        original = intake.spool.put
        def delayed(task_id, payload):
            entered.set()
            self.assertTrue(release.wait(3))
            original(task_id, payload)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool, \
                mock.patch.object(intake.spool, "put", side_effect=delayed):
            first = pool.submit(intake.submit_task, "codex", "review", "同一任务", "concurrent-fixture-1")
            self.assertTrue(entered.wait(3))
            second = pool.submit(intake.submit_task, "codex", "review", "同一任务", "concurrent-fixture-1")
            release.set()
            results = [first.result(), second.result()]
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(1, sum(item["created"] for item in results))
        self.assertEqual(1, len(intake.store.pending()))
        self.assertEqual("同一任务", intake.spool.get(results[0]["id"])["task"])

    def test_failed_spool_publication_is_unknown_and_not_replayed(self):
        intake = self.intake()
        with mock.patch.object(intake.spool, "put", side_effect=OSError("fixture")):
            with self.assertRaises(feishu_codex_bot.AgentInputPersistError):
                intake.submit_task("codex", "review", "只读分析", "failed-spool-001")
        again = intake.submit_task("codex", "review", "只读分析", "failed-spool-001")
        self.assertFalse(again["created"])
        self.assertEqual("unknown", again["status"])
        self.assertEqual([], intake.store.pending())

    def test_reused_queued_task_with_missing_payload_is_not_recreated(self):
        intake, job = self.queued_job()
        intake.spool.discard(job.task_id)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "UNKNOWN"):
            intake.submit_task("codex", "review", "只读分析", "runner-fixture-001")
        self.assertEqual("unknown", intake.get_task(job.task_id)["status"])
        self.assertFalse((intake.spool.root / f"{job.task_id}.json").exists())

    def test_retired_workitem_tools_and_namespace_never_enqueue(self):
        intake = self.intake()
        for name in ("submit_workitem_task", "get_workitem_task", "verify_workitem_delivery", "accept_workitem_qa"):
            result = feishu_agent_mcp.handle_request({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": {}}}, intake)
            self.assertTrue(result["result"]["isError"])
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "workitem-"):
            intake.submit_task("codex", "review", "只读分析", "workitem-retired-001")
        self.assertEqual([], intake.store.pending())

    def test_policy_fingerprint_binds_credential_and_budget_rotation(self):
        for field, value in (("FEISHU_AGENT_OPENAI_API_KEY", "fixture-rotated-key"),
                             ("FEISHU_AGENT_MODEL", "fixture-new-model"),
                             ("FEISHU_AGENT_BUDGET_MAX_USD", "9")):
            with self.subTest(field=field):
                intake = self.intake()
                detail = intake.submit_task("codex", "review", "只读分析", "rotation-" + field)
                values = dict(self.values, **{field: value})
                config = feishu_codex_bot.BotConfig.from_values(values, self.tmp)
                bot = feishu_codex_bot.FeishuCodexBot(config, mock.Mock(), mock.Mock(), intake.store)
                bot.refill_pending(startup=True)
                self.assertEqual("unknown", intake.get_task(detail["id"])["status"])
                self.assertTrue(bot.jobs.empty())

    def test_dispatch_rechecks_policy_payload_and_runtime_identity(self):
        for change in ("policy", "payload", "identity"):
            with self.subTest(change=change):
                intake, job = self.queued_job("dispatch-" + change)
                transport, runner = mock.Mock(), mock.Mock()
                bot = feishu_codex_bot.FeishuCodexBot(intake.config, transport, runner, intake.store)
                if change == "policy":
                    with intake.store._connect() as db:
                        db.execute("DELETE FROM task_sources WHERE task_id=? AND kind='agent-policy-sha256'", (job.task_id,))
                elif change == "payload":
                    payload = intake.spool.get(job.task_id)
                    intake.spool.discard(job.task_id)
                    payload["task"] += "未授权变更"
                    intake.spool.put(job.task_id, payload)
                else:
                    (self.agent_home / "auth.json").write_text("{}")
                try:
                    with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                            mock.patch.object(bot.jobs, "task_done"):
                        with self.assertRaises(SystemExit):
                            bot.worker()
                    self.assertEqual("unknown", intake.get_task(job.task_id)["status"])
                    runner.run.assert_not_called()
                    transport.resolve_sources.assert_not_called()
                finally:
                    auth = self.agent_home / "auth.json"
                    if auth.exists():
                        auth.unlink()

    def test_budget_observation_follows_all_local_preflight(self):
        intake, job = self.queued_job()
        runner = feishu_codex_bot.CodexRunner(intake.config)
        with mock.patch.object(runner, "_isolated_command", side_effect=feishu_codex_bot.FeishuCodexError("local fixture")), \
                mock.patch("tools.codex_assets.feishu_engineering_agent.budget.read_key_info") as budget_read, \
                mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            with self.assertRaises(feishu_codex_bot.FeishuCodexError):
                runner.run(job)
            budget_read.assert_not_called()
            popen.assert_not_called()
        with intake.store._connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='engineering_budget_receipts'").fetchone())

    def test_missing_or_exhausted_budget_never_launches_and_duplicate_does_not_relaunch(self):
        intake, job = self.queued_job()
        runner = feishu_codex_bot.CodexRunner(intake.config)
        from tools.codex_assets.feishu_engineering_agent.budget import BudgetError
        with mock.patch("tools.codex_assets.feishu_engineering_agent.budget.observe_budget",
                        side_effect=BudgetError("exhausted")), \
                mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            with self.assertRaises(feishu_codex_bot.FeishuCodexError):
                runner.run(job)
            popen.assert_not_called()
        process = mock.Mock(returncode=0)
        process.communicate.return_value = ("done", "")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            runner.run(job)
            self.assertEqual(1, popen.call_count)
            with self.assertRaises(feishu_codex_bot.FeishuCodexError):
                runner.run(job)
            self.assertEqual(1, popen.call_count)

    def test_after_budget_state_permission_error_is_unknown(self):
        intake, job = self.queued_job()
        runner = feishu_codex_bot.CodexRunner(intake.config)
        process = mock.Mock(returncode=0)
        process.communicate.return_value = ("done", "")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process), \
                mock.patch.object(feishu_codex_bot, "StateStore",
                                  side_effect=[intake.store, intake.store, feishu_codex_bot.FeishuCodexError("private DB drift")]):
            with self.assertRaises(feishu_codex_bot.CodexOutcomeUnknown):
                runner.run(job)

    def test_ephemeral_cli_nonzero_exit_is_unknown(self):
        intake, job = self.queued_job()
        process = mock.Mock(returncode=1)
        process.communicate.return_value = ("partial output", "fixture failure")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process):
            with self.assertRaises(feishu_codex_bot.CodexOutcomeUnknown):
                feishu_codex_bot.CodexRunner(intake.config).run(job)

    def test_successful_execution_with_failed_completion_receipt_stays_unknown(self):
        intake, job = self.queued_job()
        transport = mock.Mock()
        transport.resolve_sources.return_value = ""
        runner = mock.Mock()
        runner.run.return_value = feishu_codex_bot.ExecutionResult("done", worktree_path=self.tmp)
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, transport, runner, intake.store)
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"), \
                mock.patch.object(intake.store, "record_result", side_effect=sqlite3.OperationalError("fixture")):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("unknown", intake.get_task(job.task_id)["status"])
        self.assertEqual(1, runner.run.call_count)


if __name__ == "__main__":
    unittest.main()
