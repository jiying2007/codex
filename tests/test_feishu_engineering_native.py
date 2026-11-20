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
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent, IntakeRejected
from tools.codex_assets.feishu_engineering_agent.runtime_bridge import (
    NativeTurnCoordinator, RemoteOutcomeUnknown,
)
from tools.codex_assets.feishu_engineering_agent.sessions import RuntimeGrant, SessionRegistry
from tools.codex_assets.feishu_engineering_agent.state import RunStore

HOST = "vstrong100"
REPO_PATH = "/srv/robot-app"
CODEX_HOME = "/srv/codex-private"
FAKE_NOW = 2000000000


class NativeTurnTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="fea-native-")
        self.addCleanup(tmp.cleanup)
        self.store = RunStore(pathlib.Path(tmp.name) / "private.sqlite3")
        self.event = InboundEvent("feishu_message", "tenant1", "chat1", "actor1",
                                  "msg1", "分析代码")
        self.run = self.store.create_run(self.event, "robot-app", {"robot-app"}, mode="edit")
        self.sessions = SessionRegistry(self.store)
        self.sessions.bind(self.run, self.event, HOST, REPO_PATH, CODEX_HOME, "thread_abc")
        self.turns = NativeTurnCoordinator(self.store, self.sessions)
        self.grant = RuntimeGrant(
            self.run, "actor1", "robot-app", "edit", "external_approved", FAKE_NOW+300,
            "approval_123",
        )

    def queue_run(self):
        row = self.store.transition(self.run, 0, "ready", self.event.actor)
        self.store.transition(self.run, row["revision"], "queued", self.event.actor)

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
