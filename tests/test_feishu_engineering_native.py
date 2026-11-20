"""Offline native Codex app-server and turn effect contracts. No model calls."""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import queue
import tempfile
import time
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.appserver import (
    ApprovalPending, NativeProcess, NativeProtocolError, StdioAppServer,
)
from tools.codex_assets.feishu_engineering_agent.models import (
    InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.runtime_bridge import (
    NativeTurnCoordinator, RemoteOutcomeUnknown,
)
from tools.codex_assets.feishu_engineering_agent.sessions import RuntimeGrant, SessionRegistry
from tools.codex_assets.feishu_engineering_agent.state import RunStore
from tools.codex_assets.feishu_engineering_agent.workflow import (
    EngineeringWorkflow, ExecutionApproval,
)

HOST = "vstrong100"
REPO_PATH = "/srv/robot-app"
CODEX_HOME = "/srv/codex-private"
APPROVAL_KEY = b"test-only-independent-runtime-approval-key-32-bytes"


class NativeTurnTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="fea-native-")
        self.addCleanup(tmp.cleanup)
        self.store = RunStore(pathlib.Path(tmp.name) / "private.sqlite3")
        self.event = InboundEvent("feishu_message", "tenant1", "chat1", "actor1",
                                  "msg1", "分析代码")
        self.workflow = EngineeringWorkflow(self.store)
        self.source_run = self.store.create_run(
            self.event, "robot-app", {"robot-app"}, mode="read",
            workitem=WorkItemKey("tapd", "tenant1", "10101", "defect", "33"),
        )
        self.run = self.workflow.create_attempt(
            self.source_run, self.event, "edit", {"robot-app"},
        )["run_id"]
        self.sessions = SessionRegistry(self.store)
        self.sessions.bind(self.run, self.event, HOST, REPO_PATH, CODEX_HOME, "thread_abc")
        self.turns = NativeTurnCoordinator(self.store, self.sessions)
        self.grant = RuntimeGrant(
            self.run, "actor1", "robot-app", "edit", "external_approved",
            int(time.time()) + 300, "approval_123",
        )

    def queue_run(self):
        approved = ExecutionApproval(
            self.run, "actor1", "tenant1", "chat1", "robot-app", "edit",
            "approval_123", "external_approved", int(time.time()) + 300,
            sdd_reviewed=True,
        )
        signature = self.workflow.sign_approval(approved, APPROVAL_KEY)
        self.grant = self.workflow.authorize_queue(
            approved, signature, APPROVAL_KEY, self.event, {"robot-app"},
        )

    def dispatch(self, send, grant=None, enabled=True):
        return self.turns.dispatch(
            self.run, self.event, HOST, REPO_PATH, CODEX_HOME,
            self.grant if grant is None else grant, "定位低速过流",
            send=send, model_calls_enabled=enabled,
        )

    def test_default_disabled_and_wrong_state_never_send(self):
        sender = mock.Mock(return_value={"result": {"turn": {"id": "turn_1"}}})
        with self.assertRaises(IntakeRejected):
            self.dispatch(sender)
        sender.assert_not_called()
        self.queue_run()
        with self.assertRaises(IntakeRejected):
            self.dispatch(sender, enabled=False)
        sender.assert_not_called()
        with self.assertRaises(IntakeRejected):
            self.turns.dispatch(self.run, self.event, HOST, REPO_PATH, CODEX_HOME,
                                None, "text", sender, model_calls_enabled=True)
        sender.assert_not_called()

    def test_ack_requires_real_terminal_native_event(self):
        self.queue_run()
        sender = mock.Mock(return_value={"result": {"turn": {"id": "turn_1"}}})
        started = self.dispatch(sender)
        self.assertEqual("running", started["status"])
        self.assertFalse(started["verified_complete"])
        self.assertEqual("turn/start", sender.call_args.args[0]["method"])
        self.assertEqual("running", self.store.get_run(self.run)["status"])
        with self.assertRaises(IntakeRejected):
            self.dispatch(sender)
        sender.assert_called_once()
        with self.assertRaises(IntakeRejected):
            self.turns.observe(self.run, self.event, {
                "method": "turn/completed",
                "params": {"threadId": "thread_wrong",
                           "turn": {"id": "turn_1", "status": "completed"}},
            })
        completion = {
            "method": "turn/completed",
            "params": {"threadId": "thread_abc",
                       "turn": {"id": "turn_1", "status": "completed"}},
        }
        receipt = self.turns.observe(self.run, self.event, completion)
        self.assertEqual("waiting_ci", receipt["run_status"])
        self.assertTrue(self.turns.observe(self.run, self.event, completion)["duplicate"])

    def test_read_only_workitem_analysis_finishes_without_pr_qa(self):
        read_event = InboundEvent(
            "feishu_message", "tenant1", "chat1", "actor1",
            "msg_read", "只读分析任务",
        )
        source = self.store.create_run(
            read_event, "robot-app", {"robot-app"}, mode="read",
            workitem=WorkItemKey("tapd", "tenant1", "10101", "requirement", "34"),
        )
        analysis = self.workflow.create_attempt(
            source, read_event, "read", {"robot-app"},
        )["run_id"]
        approved = ExecutionApproval(
            analysis, "actor1", "tenant1", "chat1", "robot-app", "read",
            "approval_read", "external_approved", int(time.time()) + 300,
        )
        signature = self.workflow.sign_approval(approved, APPROVAL_KEY)
        grant = self.workflow.authorize_queue(
            approved, signature, APPROVAL_KEY, read_event, {"robot-app"},
        )
        self.sessions.bind(
            analysis, read_event, HOST, REPO_PATH, CODEX_HOME, "thread_read",
        )
        result = self.turns.dispatch(
            analysis, read_event, HOST, REPO_PATH, CODEX_HOME,
            grant, "只读分析并总结测试建议",
            lambda request: {"result": {"turn": {"id": "turn_read"}}},
            model_calls_enabled=True,
        )
        self.assertFalse(result["verified_complete"])
        finished = self.turns.observe(analysis, read_event, {
            "method": "turn/completed",
            "params": {"threadId": "thread_read",
                       "turn": {"id": "turn_read", "status": "completed"}},
        })
        self.assertEqual("completed", finished["run_status"])
        self.assertFalse(finished["source_workitem_closed"])
        self.assertEqual("completed", self.store.get_run(analysis)["status"])
        with contextlib.closing(self.store._connect()) as db:
            self.assertEqual(0, db.execute(
                "SELECT COUNT(*) FROM fea_evidence WHERE run_id=?", (analysis,),
            ).fetchone()[0])

    def test_grant_expiry_cannot_be_extended_after_signed_approval(self):
        self.queue_run()
        forged = RuntimeGrant(
            self.run, "actor1", "robot-app", "edit",
            self.grant.billing_source, self.grant.expires_at + 180,
            self.grant.authorization_ref,
        )
        sender = mock.Mock()
        with self.assertRaisesRegex(IntakeRejected, "persistent signed approval"):
            self.dispatch(sender, grant=forged)
        sender.assert_not_called()
        self.assertEqual("queued", self.store.get_run(self.run)["status"])

    def test_forged_in_memory_runtime_grant_is_not_enough(self):
        # A caller can construct RuntimeGrant, but cannot use it without
        # a durable independently signed approval receipt.
        with contextlib.closing(self.store._connect()) as db:
            db.execute(
                "UPDATE fea_runs SET status='queued',revision=revision+2 "
                "WHERE run_id=?", (self.run,),
            )
            db.commit()
        sender = mock.Mock()
        with self.assertRaisesRegex(IntakeRejected, "persistent signed approval"):
            self.dispatch(sender)
        sender.assert_not_called()

    def test_edit_run_cannot_skip_pr_ci_qa(self):
        self.queue_run()
        result = self.dispatch(
            lambda request: {"result": {"turn": {"id": "turn_edit"}}},
        )
        run = self.store.get_run(self.run)
        with self.assertRaises(IntakeRejected):
            self.store.transition(self.run, run["revision"], "completed", "actor1")
        self.turns.observe(self.run, self.event, {
            "method": "turn/completed",
            "params": {"threadId": "thread_abc",
                       "turn": {"id": "turn_edit", "status": "completed"}},
        })
        self.assertEqual("waiting_ci", self.store.get_run(self.run)["status"])

    def test_unknown_send_or_restart_never_replays(self):
        self.queue_run()
        sender = mock.Mock(side_effect=TimeoutError("uncertain model charge"))
        with self.assertRaises(RemoteOutcomeUnknown):
            self.dispatch(sender)
        self.assertEqual("unknown", self.store.get_run(self.run)["status"])
        self.assertEqual("unknown", self.turns.restart_recovery(self.run, self.event))
        with self.assertRaises(IntakeRejected):
            self.dispatch(sender)
        sender.assert_called_once()

    def test_interrupt_ack_does_not_claim_turn_stopped(self):
        self.queue_run()
        self.dispatch(lambda r: {"result": {"turn": {"id": "turn_1"}}})
        sender = mock.Mock(return_value={"result": {}})
        result = self.turns.interrupt(
            self.run, self.event, HOST, REPO_PATH, CODEX_HOME, sender,
        )
        self.assertTrue(result["interruption_requested"])
        self.assertFalse(result["turn_stopped"])
        self.assertEqual("turn/interrupt", sender.call_args.args[0]["method"])
        completion = self.turns.observe(self.run, self.event, {
            "method": "turn/completed",
            "params": {"threadId": "thread_abc",
                       "turn": {"id": "turn_1", "status": "interrupted"}},
        })
        self.assertEqual("unknown", completion["run_status"])

    def test_cross_actor_and_home_not_resumable(self):
        self.queue_run()
        intruder = InboundEvent("feishu_message", "tenant1", "chat1", "actor2",
                                "msg2", "启动模型")
        sender = mock.Mock()
        with self.assertRaises(IntakeRejected):
            self.turns.dispatch(
                self.run, intruder, HOST, REPO_PATH, CODEX_HOME,
                self.grant, "bad", sender, model_calls_enabled=True,
            )
        with self.assertRaises(IntakeRejected):
            self.turns.dispatch(
                self.run, self.event, HOST, REPO_PATH, "/srv/other",
                self.grant, "bad", sender, model_calls_enabled=True,
            )
        sender.assert_not_called()


class ReactiveOutput:
    def __init__(self):
        self.data = queue.Queue()

    def readline(self, size=-1):
        return self.data.get(timeout=5)


class ReactiveInput:
    def __init__(self, output):
        self.output = output
        self.sent = []

    def write(self, raw):
        frame = json.loads(raw)
        self.sent.append(frame)
        if frame.get("method") == "initialized":
            return len(raw)
        method = frame.get("method")
        if method == "turn/start":
            reply = {"id": frame["id"], "result": {"turn": {"id": "turn_1"}}}
        else:
            reply = {"id": frame["id"], "result": {"accepted": True}}
        self.output.data.put(json.dumps(reply) + "\n")
        return len(raw)

    def flush(self):
        pass


class NativeAppServerProtocolTest(unittest.TestCase):
    def setUp(self):
        self.output = ReactiveOutput()
        self.input = ReactiveInput(self.output)
        self.server = StdioAppServer(self.input, self.output, timeout_sec=2)
        self.addCleanup(self.stop)

    def stop(self):
        self.server.close()
        self.output.data.put("")

    def test_initialize_resume_and_default_denied_turn(self):
        response = self.server.initialize()
        self.assertTrue(response["result"]["accepted"])
        self.assertTrue(self.server.initialized)
        self.assertEqual("initialized", self.input.sent[1]["method"])
        self.assertEqual("thread/resume",
                         self.server.resume_exact("thread_abc")["result"] and
                         self.input.sent[2]["method"])
        with self.assertRaises(NativeProtocolError):
            self.server.turn_start(
                {"method": "turn/start", "params": {}}, allow_model=False,
            )
        self.assertEqual(3, len(self.input.sent))
        result = self.server.turn_start(
            {"method": "turn/start", "params": {"threadId": "thread_abc"}},
            allow_model=True,
        )
        self.assertEqual("turn_1", result["result"]["turn"]["id"])

    def test_terminal_notification_before_start_ack_is_buffered(self):
        self.server.initialize()
        original_write = self.input.write
        final_event = {
            "method": "turn/completed",
            "params": {"threadId": "thread_abc",
                       "turn": {"id": "turn_1", "status": "completed"}},
        }

        def emit_terminal_before_ack(raw):
            if json.loads(raw).get("method") == "turn/start":
                self.output.data.put(json.dumps(final_event) + "\n")
            return original_write(raw)

        self.input.write = emit_terminal_before_ack
        observed = self.server.turn_start(
            {"method": "turn/start", "params": {"threadId": "thread_abc"}},
            allow_model=True,
        )
        self.assertEqual("turn_1", observed["result"]["turn"]["id"])
        self.assertEqual([final_event], self.server.drain_notifications())
        self.assertEqual([], self.server.drain_notifications())

    def test_overflow_fails_before_starting_new_native_turn(self):
        self.server.initialize()
        before = len(self.input.sent)
        self.server._notification_overflow = True
        with self.assertRaisesRegex(NativeProtocolError, "notification overflow"):
            self.server.turn_start(
                {"method": "turn/start", "params": {"threadId": "thread_abc"}},
                allow_model=True,
            )
        self.assertEqual(before, len(self.input.sent))

    def test_host_tool_approval_is_never_autoaccepted(self):
        self.server.initialize()
        class ApprovalWriter:
            def __init__(self, writer, output):
                self.writer = writer
                self.output = output
            def write(self, raw):
                frame = json.loads(raw)
                self.writer.sent.append(frame)
                if frame.get("id"):
                    self.output.data.put(json.dumps({
                        "id": 918, "method": "item/commandExecution/requestApproval",
                        "params": {"command": "danger"},
                    }) + "\n")
                return len(raw)
            def flush(self):
                pass
        self.server.stdin = ApprovalWriter(self.input, self.output)
        with self.assertRaises(ApprovalPending):
            self.server.turn_start(
                {"method": "turn/start", "params": {"threadId": "thread_abc"}},
                allow_model=True,
            )
        self.assertEqual("turn/start", self.input.sent[-1]["method"])
        self.assertFalse(any("decision" in str(x) for x in self.input.sent))

    def test_host_process_flag_and_secret_environment(self):
        proc = NativeProcess(CODEX_HOME, REPO_PATH)
        with self.assertRaises(NativeProtocolError):
            proc.open()
        fake_process = mock.Mock()
        fake_process.stdin = io.StringIO()
        fake_process.stdout = io.StringIO()
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.appserver.subprocess.Popen",
            return_value=fake_process,
        ) as opener, mock.patch.dict(
            "os.environ", {"FEISHU_APP_SECRET": "must_not_leak",
                           "FEISHU_CARD_SIGNING_KEY_HEX": "must_not_leak"},
        ):
            transport = proc.open(explicitly_qualified=True)
        kwargs = opener.call_args.kwargs
        self.assertEqual(["codex", "app-server"], opener.call_args.args[0])
        self.assertNotIn("FEISHU_APP_SECRET", kwargs["env"])
        self.assertNotIn("FEISHU_CARD_SIGNING_KEY_HEX", kwargs["env"])
        self.assertEqual(CODEX_HOME, kwargs["env"]["CODEX_HOME"])
        self.assertFalse(transport.initialized)
        proc.close()
