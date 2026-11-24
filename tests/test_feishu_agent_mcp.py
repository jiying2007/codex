"""Offline local MCP intake tests; never call a model or Feishu network."""
from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import time
import threading
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
                                  return_value={"info": {"key_alias": "fixture-agent",
                                              "max_budget": 10, "spend": 1}})
        budget_patch.start()
        self.addCleanup(budget_patch.stop)

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

    def test_concurrent_workitem_submission_publishes_one_ready_task(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        other = self.intake()
        started = threading.Event()
        release = threading.Event()
        original = intake.spool.put

        def slow_put(task_id, payload):
            started.set()
            if not release.wait(3):
                raise RuntimeError("test publication timed out")
            original(task_id, payload)

        with mock.patch.object(intake.spool, "put", side_effect=slow_put):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(intake.submit_workitem_task, run_id, scope)
                try:
                    self.assertTrue(started.wait(3))
                    # The task and link cannot be observed before spool publication.
                    self.assertIsNone(other.store.agent_run_link_for_run(run_id))
                    self.assertEqual([], other.store.pending())
                    second = pool.submit(other.submit_workitem_task, run_id, scope)
                finally:
                    release.set()
                a, b = first.result(timeout=5), second.result(timeout=5)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual([False, True], sorted([a["created"], b["created"]]))
        self.assertEqual("queued", manual.store.get_run(run_id)["status"])
        self.assertEqual(scope, intake.spool.get(a["id"])["task"])

    def test_failed_spool_publication_is_unknown_and_not_replayed(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        with mock.patch.object(intake.spool, "put", side_effect=OSError("fixture")):
            with self.assertRaises(feishu_codex_bot.AgentInputPersistError):
                intake.submit_workitem_task(run_id, scope)
        link = intake.store.agent_run_link_for_run(run_id)
        self.assertIsNotNone(link)
        self.assertEqual("unknown", intake.get_task(link["task_id"])["status"])
        self.assertEqual("unknown", manual.store.get_run(run_id)["status"])
        self.assertEqual([], intake.store.pending())
        with self.assertRaises(IntakeRejected):
            intake.submit_workitem_task(run_id, scope)

    def test_generic_task_cannot_claim_workitem_idempotency_namespace(self) -> None:
        intake, _, run_id, scope = self.workitem_attempt()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "workitem-"):
            intake.submit_task("codex", "edit", scope, "workitem-" + run_id)
        self.assertEqual([], intake.store.pending())

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
        with intake.store._connect() as connection:
            task_count = connection.execute(
                "SELECT COUNT(*) FROM tasks"
            ).fetchone()[0]
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
        self.values["FEISHU_AGENT_OPENAI_API_KEY"] = "fixture-rotated-api-key"
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
        values["FEISHU_AGENT_OPENAI_BASE_URL"] = "https://user:password@gateway.example/v1?token=secret"
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "不含凭据"):
            feishu_codex_bot.BotConfig.from_values(values, self.tmp)

    def test_workitem_task_cancel_updates_agent_run(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        canceled = intake.cancel_queued_task(submitted["id"])
        self.assertTrue(canceled["queued_cancelled"])
        self.assertEqual("canceled", manual.store.get_run(run_id)["status"])

    def test_feishu_workitem_cancel_is_exact_scoped_and_idempotent(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        item = intake.submit_workitem_task(run_id, scope)
        unrelated = intake.submit_task("codex", "review", "其他任务", "cancel-other-001")
        runner = mock.Mock()
        bot = feishu_codex_bot.FeishuCodexBot(
            intake.config, mock.Mock(), runner,
            feishu_codex_bot.StateStore(intake.config.state_db),
        )
        owner = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_cancel",
            "/wi cancel " + run_id,
        )
        attacker = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_other", "om_foreign_cancel",
            owner.text,
        )
        with self.assertRaises(IntakeRejected):
            bot._cancel_workitem(run_id, attacker, frozenset({"codex"}))
        with self.assertRaises(IntakeRejected):
            bot._cancel_workitem(run_id, owner, frozenset())
        self.assertEqual("queued", intake.get_task(item["id"])["status"])
        bot._run_manual_message(owner, owner.actor, frozenset({"codex"}))
        self.assertIn("已取消排队任务", bot.transport.send_text.call_args.args[1])
        self.assertEqual("canceled", intake.get_task(item["id"])["status"])
        self.assertEqual("canceled", manual.store.get_run(run_id)["status"])
        self.assertEqual("queued", intake.get_task(unrelated["id"])["status"])
        self.assertFalse((intake.spool.root / f"{item['id']}.json").exists())
        runner.cancel_task.assert_not_called()
        bot._run_manual_message(owner, owner.actor, frozenset({"codex"}))
        self.assertIn("没有可取消", bot.transport.send_text.call_args.args[1])

    def test_running_workitem_cancel_requests_only_exact_process(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        item = intake.submit_workitem_task(run_id, scope)
        self.assertTrue(intake.store.claim_queued(item["id"]))
        record = manual.store.get_run(run_id)
        manual.store.transition(run_id, record["revision"], "running", record["actor"])
        runner = feishu_codex_bot.CodexRunner(intake.config)
        target, other = mock.Mock(), mock.Mock()
        target.poll.return_value = other.poll.return_value = None
        runner._running[item["id"]] = (intake.sender, target)
        runner._running[item["id"] + 100] = (intake.sender, other)
        bot = feishu_codex_bot.FeishuCodexBot(
            intake.config, mock.Mock(), runner, intake.store,
        )
        owner = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_cancel_live",
            "/wi cancel " + run_id,
        )
        self.assertFalse(runner.cancel_task(item["id"], "agent:999999"))
        reply = bot._cancel_workitem(run_id, owner, frozenset({"codex"}))
        self.assertIn("发送终止请求", reply)
        self.assertEqual("running", manual.store.get_run(run_id)["status"])
        self.assertEqual("running", intake.get_task(item["id"])["status"])
        self.assertIn("发送终止请求", bot._cancel_workitem(run_id, owner, frozenset({"codex"})))
        target.terminate.assert_called_once()
        other.terminate.assert_not_called()

    def test_workitem_continuation_reuses_exact_native_thread_and_worktree(self) -> None:
        intake, manual, first_run, scope = self.workitem_attempt()
        initial = intake.submit_workitem_task(first_run, scope)
        repo = intake.config.repository("codex")
        cwd = repo.worktree_root / f"task-{initial['id']}"
        branch = f"{repo.branch_prefix}-{initial['id']}"
        runner = mock.Mock()
        transport = mock.Mock()
        transport.resolve_sources.return_value = ""
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, transport, runner, intake.store)

        def worker_once(result):
            bot.refill_pending()
            job = bot.jobs.get_nowait()
            runner.run.reset_mock()
            runner.run.return_value = result
            with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                    mock.patch.object(bot.jobs, "task_done"):
                with self.assertRaises(SystemExit):
                    bot.worker()
            return job

        worker_once(feishu_codex_bot.ExecutionResult(
            "首轮完成", branch, "a" * 40, cwd, THREAD_ID, cwd,
        ))
        self.assertEqual("waiting_ci", manual.store.get_run(first_run)["status"])
        next_scope = "补充回归测试"
        event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_continue",
            "/wi continue " + first_run + " | " + next_scope,
        )
        reply = manual.handle(event, "codex", {"codex"})
        next_run = reply.split("新Run：", 1)[1].split("\n", 1)[0]
        self.assertIn(next_run, manual.handle(event, "codex", {"codex"}))
        self.assertEqual("proposed", manual.store.get_run(next_run)["status"])
        # An unapproved canceled proposal cannot permanently reserve the root.
        status_event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_status_continuation",
            "/wi status " + first_run,
        )
        self.assertIn("后续Run：" + next_run, manual.handle(status_event, "codex", {"codex"}))
        cancel_event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_cancel_proposal",
            "/wi cancel " + next_run,
        )
        self.assertIn("已撤销未授权", bot._cancel_workitem(
            next_run, cancel_event, frozenset({"codex"}),
        ))
        self.assertEqual("canceled", manual.store.get_run(next_run)["status"])
        self.assertNotIn("后续Run：", manual.handle(status_event, "codex", {"codex"}))
        self.assertIn("状态：canceled", manual.handle(event, "codex", {"codex"}))
        with self.assertRaises(IntakeRejected):
            intake.submit_workitem_task(next_run, next_scope)
        event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_continue_replacement",
            "/wi continue " + first_run + " | " + next_scope,
        )
        next_run = manual.handle(event, "codex", {"codex"}).split("新Run：", 1)[1].split("\n", 1)[0]
        fork_event = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_fork",
            event.text,
        )
        with self.assertRaisesRegex(IntakeRejected, "reserved continuation"):
            manual.handle(fork_event, "codex", {"codex"})
        with self.assertRaisesRegex(IntakeRejected, "scope"):
            intake.submit_workitem_task(next_run, next_scope + " drift")
        submitted = intake.submit_workitem_task(next_run, next_scope)
        self.assertNotEqual(initial["id"], submitted["id"])
        next_job = worker_once(feishu_codex_bot.ExecutionResult(
            "补充完成", branch, "b" * 40, cwd, THREAD_ID, cwd,
        ))
        target = runner.run.call_args.kwargs["resume_target"]
        self.assertEqual(initial["id"], target.root_task_id)
        self.assertEqual(cwd, target.working_directory)
        self.assertEqual(THREAD_ID, target.thread_id)
        self.assertEqual("a" * 40, target.commit_hash)
        self.assertEqual(submitted["id"], next_job.task_id)
        final = intake.get_workitem_task(next_run)
        self.assertEqual("waiting_ci", final["run_status"])
        self.assertEqual("b" * 40, final["task"]["commit_hash"])
        self.assertEqual(THREAD_ID, final["session"]["thread_id"])
        self.assertEqual(first_run, final["lineage"]["previous_run_id"])
        self.assertEqual(next_run, intake.get_workitem_task(first_run)["lineage"]["next_run_id"])
        self.assertEqual("a" * 40, intake.get_workitem_task(first_run)["task"]["commit_hash"])
        self.assertFalse(intake.submit_workitem_task(next_run, next_scope)["created"])
        # The old branch/commit receipt remains historical, not a second PR.
        from tools.codex_assets.feishu_engineering_agent.delivery import DeliveryCoordinator
        delivery = DeliveryCoordinator(manual.store)
        with self.assertRaisesRegex(IntakeRejected, "reserved continuation"):
            delivery.verify_git(
                first_run, event, "pr", "https://example.org/pr/1", "a" * 40,
                lambda ref: {"repo_alias": "codex", "reference": ref,
                             "state": "open", "head_sha": "a" * 40},
            )
        # Exercise the actual CLI runner without any model/network call.
        real_runner = feishu_codex_bot.CodexRunner(intake.config)
        real_runner.worktrees = mock.Mock()
        real_runner.worktrees.verify_and_commit.return_value = "b" * 40
        process = mock.Mock()
        process.returncode = 0
        frames = [
            {"type": "thread.started", "thread_id": THREAD_ID},
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": {}},
        ]
        process.communicate.return_value = ("\n".join(json.dumps(f) for f in frames), "")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            real_runner.run(next_job, persistent_session=True, resume_target=target)
        args = popen.call_args.args[0]
        self.assertEqual(THREAD_ID, args[args.index("resume") + 1])
        self.assertNotIn("--last", args)
        self.assertNotIn("--ephemeral", args)
        real_runner.worktrees.prepare.assert_not_called()
        real_runner.worktrees.require_resume_base.assert_any_call(target, repo)
        real_runner.worktrees.verify_and_commit.assert_called_once()
        import dataclasses
        next_job = dataclasses.replace(next_job, task_id=next_job.task_id + 1000)
        frames[0]["thread_id"] = "01979c6c-0354-7000-8000-000000000002"
        process.communicate.return_value = ("\n".join(json.dumps(f) for f in frames), "")
        real_runner.worktrees.verify_and_commit.reset_mock()
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process):
            with self.assertRaises(feishu_codex_bot.CodexOutcomeUnknown):
                real_runner.run(next_job, persistent_session=True, resume_target=target)
        real_runner.worktrees.verify_and_commit.assert_not_called()

    def test_existing_worker_delivers_exact_pr_all_ci_and_independent_qa(self) -> None:
        self.policy["repositories"]["codex"]["github_delivery"] = {
            "repository": "fixture/codex", "base_branch": "main",
            "required_workflows": [".github/workflows/test.yml", ".github/workflows/lint.yml"],
        }
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        repo = intake.config.repository("codex")
        cwd = repo.worktree_root / f"task-{submitted['id']}"
        branch = f"{repo.branch_prefix}-{submitted['id']}"
        sha = "a" * 40
        runner = mock.Mock()
        transport = mock.Mock()
        runner.run.return_value = feishu_codex_bot.ExecutionResult(
            "local result", branch, sha, cwd, THREAD_ID, cwd,
        )
        transport.resolve_sources.return_value = ""
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, transport, runner, intake.store)
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("waiting_ci", manual.store.get_run(run_id)["status"])
        name = "fixture/codex"
        root = "/repos/" + name
        identity = {"full_name": name}
        pr = {"number": 12, "head": {"repo": identity, "sha": sha, "ref": branch},
              "base": {"repo": identity, "ref": "main"}, "state": "open"}
        def ci(run_id, path):
            return {"id": run_id, "repository": identity, "head_repository": identity,
                    "head_sha": sha, "head_branch": branch, "status": "completed",
                    "conclusion": "success", "event": "pull_request",
                    "pull_requests": [{"number": 12}], "path": path}
        a = ci(31, ".github/workflows/test.yml")
        b = ci(32, ".github/workflows/lint.yml")
        responses = {root + "/pulls/12": pr, root + "/actions/runs/31": a,
                     root + "/actions/runs/32": b}
        def request(method, path, payload=None):
            self.assertEqual("GET", method)
            self.assertIsNone(payload)
            return responses[path]
        api = mock.Mock(side_effect=request)
        from tools.codex_assets.feishu_engineering_agent import github_adapter
        from tools.codex_assets.feishu_engineering_agent.delivery import DeliveryCoordinator
        from tools.codex_assets.feishu_engineering_agent.models import IntakeRejected
        qa_key = b"fixture-independent-review-key-32bytes"
        verifier = feishu_agent_mcp.AgentTaskIntake(
            intake.config, qa_reviewer="ou_qa", qa_key_hex=qa_key.hex(),
        )
        with mock.patch.object(github_adapter, "GitHubTransport", return_value=api):
            with self.assertRaises(IntakeRejected):
                verifier.verify_workitem_delivery(run_id, 12, [31])
            b["conclusion"] = "failure"
            with self.assertRaises(IntakeRejected):
                verifier.verify_workitem_delivery(run_id, 12, [31, 32])
            b["conclusion"] = "success"
            b["head_sha"] = "b" * 40
            with self.assertRaises(IntakeRejected):
                verifier.verify_workitem_delivery(run_id, 12, [31, 32])
            b["head_sha"] = sha
            b["path"] = a["path"]
            with self.assertRaises(IntakeRejected):
                verifier.verify_workitem_delivery(run_id, 12, [31, 32])
            b["path"] = ".github/workflows/lint.yml"
            b["pull_requests"] = [{"number": 13}]
            with self.assertRaises(IntakeRejected):
                verifier.verify_workitem_delivery(run_id, 12, [31, 32])
            b["pull_requests"] = [{"number": 12}]
            self.assertEqual("waiting_ci", manual.store.get_run(run_id)["status"])
            self.assertEqual([], verifier.get_workitem_task(run_id)["delivery"]["evidence"])
            # The authorized Feishu owner can verify the same exact delivery
            # through the existing consumer, with no second listener or model.
            message = InboundEvent(
                "feishu_message", "tenantA", "oc_test", "ou_owner", "om_delivery",
                "/wi delivery " + run_id + " 12 31 32",
            )
            foreign = InboundEvent(
                "feishu_message", "tenantA", "oc_test", "ou_other", "om_foreign_delivery",
                message.text,
            )
            calls = api.call_count
            bot._run_manual_message(foreign, foreign.actor, frozenset({"codex"}))
            self.assertEqual(calls, api.call_count)
            bot._run_manual_message(message, message.actor, frozenset())
            self.assertEqual(calls, api.call_count)
            bot._run_manual_message(message, message.actor, frozenset({"codex"}))
            self.assertIn("已核验精确 PR", transport.send_text.call_args.args[1])
            self.assertEqual("waiting_qa", manual.store.get_run(run_id)["status"])
            result = verifier.verify_workitem_delivery(run_id, 12, [31, 32])
            self.assertEqual("waiting_qa", result["run_status"])
            self.assertEqual(sha, result["head_sha"])
            self.assertEqual(3, len(result["evidence"]))
            self.assertFalse(result["workitem_closed"])
            again = verifier.verify_workitem_delivery(run_id, 12, [32, 31])
            self.assertEqual(result["evidence"], again["evidence"])
            now = int(time.time())
            ref = "qa://fixture/verified"
            message = DeliveryCoordinator.qa_message(
                run_id, result["workitem_fingerprint"], sha, "ou_qa", ref, now,
            )
            signature = hmac.new(qa_key, message, hashlib.sha256).hexdigest()
            with self.assertRaises(feishu_codex_bot.FeishuCodexError):
                verifier.accept_workitem_qa(run_id, "ou_owner", ref, now, signature)
            with self.assertRaises(IntakeRejected):
                verifier.accept_workitem_qa(run_id, "ou_qa", ref, now, "0" * 64)
            pr["head"]["sha"] = "c" * 40
            with self.assertRaises(IntakeRejected):
                verifier.accept_workitem_qa(run_id, "ou_qa", ref, now, signature)
            pr["head"]["sha"] = sha
            self.assertEqual("waiting_qa", manual.store.get_run(run_id)["status"])
            final = verifier.accept_workitem_qa(run_id, "ou_qa", ref, now, signature)
            self.assertEqual("completed", final["run_status"])
            self.assertFalse(final["workitem_closed"])
            self.assertIn("https://github.com/fixture/codex/pull/12", final["feedback"])
            self.assertIn(ref, final["feedback"])
            self.assertEqual("completed", verifier.get_workitem_task(run_id)["run_status"])
        feedback = InboundEvent(
            "feishu_message", "tenantA", "oc_test", "ou_owner", "om_feedback",
            "/wi feedback " + run_id,
        )
        self.assertIn(ref, manual.handle(feedback, "codex", {"codex"}))
        with self.assertRaises(IntakeRejected):
            manual.handle(feedback, "codex", set())
        runner.run.assert_called_once()

    def test_delivery_chat_parser_rejects_freeform_urls_and_duplicates(self) -> None:
        from tools.codex_assets.feishu_engineering_agent.manual_items import parse_manual_command
        run_id = "a" * 32
        parsed = parse_manual_command("/wi delivery " + run_id + " 12 31 32", "tenantA", "codex")
        self.assertEqual("delivery", parsed.action)
        self.assertEqual(12, parsed.pr_number)
        self.assertEqual((31, 32), parsed.ci_run_ids)
        for suffix in ("12 31 31", "12", "12 -1", "12 https://github.com/x",
                       "12 31 | success", "0 31"):
            with self.assertRaises(IntakeRejected):
                parse_manual_command("/wi delivery " + run_id + " " + suffix,
                                     "tenantA", "codex")

    def test_existing_workitem_links_do_not_allow_empty_agent_ledger_recreation(self) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        agent_db = pathlib.Path(manual.store.path)
        retained = agent_db.with_name("retained-agent.sqlite3")
        agent_db.rename(retained)
        self.assertFalse(agent_db.exists())
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "restore paired backup"):
            feishu_codex_bot.FeishuCodexBot(
                intake.config, mock.Mock(), mock.Mock(), intake.store,
            )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "restore paired backup"):
            intake.get_workitem_task(run_id)
        self.assertFalse(agent_db.exists())
        self.assertEqual("queued", intake.get_task(submitted["id"])["status"])
        retained.rename(agent_db)
        self.assertEqual("queued", intake.get_workitem_task(run_id)["run_status"])

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

    def _assert_dispatch_rechecks(self, change) -> None:
        intake, manual, run_id, scope = self.workitem_attempt()
        submitted = intake.submit_workitem_task(run_id, scope)
        runner = mock.Mock()
        transport = mock.Mock()
        bot = feishu_codex_bot.FeishuCodexBot(intake.config, transport, runner, intake.store)
        bot.recover_pending()
        job = bot.jobs.get_nowait()
        if change == "approval":
            with sqlite3.connect(str(manual.store.path)) as db:
                db.execute("DELETE FROM fea_local_agent_approvals WHERE run_id=?", (run_id,))
        elif change == "payload":
            payload = intake.spool.get(job.task_id)
            intake.spool.discard(job.task_id)
            payload["task"] += "未授权变更"
            intake.spool.put(job.task_id, payload)
        else:
            (self.agent_home / "auth.json").write_text("{}", encoding="utf-8")
        try:
            with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                    mock.patch.object(bot.jobs, "task_done"):
                with self.assertRaises(SystemExit):
                    bot.worker()
            self.assertEqual("unknown", intake.get_task(submitted["id"])["status"])
            self.assertEqual("unknown", manual.store.get_run(run_id)["status"])
            runner.run.assert_not_called()
            transport.resolve_sources.assert_not_called()
        finally:
            auth = self.agent_home / "auth.json"
            if auth.exists():
                auth.unlink()

    def test_dispatch_rechecks_revoked_approval(self) -> None:
        self._assert_dispatch_rechecks("approval")

    def test_dispatch_rechecks_changed_payload(self) -> None:
        self._assert_dispatch_rechecks("payload")

    def test_dispatch_rechecks_runtime_identity(self) -> None:
        self._assert_dispatch_rechecks("billing")

    def test_jsonrpc_initialize_list_call_and_notifications(self) -> None:
        intake = self.intake()
        def invoke(message: object) -> dict | None:
            return feishu_agent_mcp.handle_request(message, intake)
        hello = invoke({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual("2025-06-18", hello["result"]["protocolVersion"])
        listing = invoke({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(
            {"submit_task", "submit_workitem_task", "get_workitem_task",
             "verify_workitem_delivery", "accept_workitem_qa",
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
