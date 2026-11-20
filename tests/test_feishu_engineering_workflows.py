"""Offline SDD TASK-002..005 contracts, no network/model/production service."""
from __future__ import annotations

import copy
import pathlib
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.models import (
    EventConflict, InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.state import RunStore
from tools.codex_assets.feishu_engineering_agent.cards import (
    CARD_LIFETIME_SECONDS, accept_callback, bind_sent_message, card_ack,
    pending_actions, register_card, render_card,
)
from tools.codex_assets.feishu_engineering_agent.sessions import (
    RuntimeGrant, SessionRegistry, probe_local_app_server,
)
from tools.codex_assets.feishu_engineering_agent.workitems import (
    FeishuProjectReader, TapdReader,
)

KEY = b"independent-private-test-card-key-32-bytes-minimum"
NOW = 1800000000


class EngineeringRunContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fea-workflow-")
        self.addCleanup(self.tmp.cleanup)
        self.store = RunStore(pathlib.Path(self.tmp.name) / "state.sqlite3")
        self.event = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", "om_new", "分析系统"
        )
        self.key = WorkItemKey("tapd", "tenantA", "10104801", "defect", "123456")

    def run_id(self, repo="robot-app", mode="edit", workitem=None):
        return self.store.create_run(
            self.event, repo, {"robot-app", "pcr02-mcu"},
            mode=mode, workitem=workitem,
        )

    def test_runs_are_separate_from_workitems_and_repos(self):
        one = self.run_id("robot-app", workitem=self.key)
        two = self.run_id("pcr02-mcu", workitem=self.key)
        self.assertNotEqual(one, two)
        rows = self.store.workitem_runs(self.key)
        self.assertEqual({"robot-app", "pcr02-mcu"}, {r["repo"] for r in rows})
        self.assertEqual({"proposed"}, {r["status"] for r in rows})
        self.assertFalse(any("prompt" in column for column in self.store.get_run(one)))

    def test_run_policy_and_cross_tenant_fail_closed(self):
        with self.assertRaises(IntakeRejected):
            self.store.create_run(self.event, "bad-repo", {"robot-app"})
        with self.assertRaises(IntakeRejected):
            self.run_id(workitem=WorkItemKey("tapd", "tenantB", "101", "defect", "123"))
        run = self.run_id()
        other = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_other", "om_second", "状态"
        )
        with self.assertRaises(IntakeRejected):
            self.store.get_run(run, other)

    def test_state_transitions_are_revision_checked_and_unknown_not_replayed(self):
        run = self.run_id(workitem=self.key)
        record = self.store.transition(run, 0, "ready", "ou_owner")
        self.assertEqual(1, record["revision"])
        with self.assertRaises(IntakeRejected):
            self.store.transition(run, 0, "queued", "ou_owner")
        for state in ("queued", "running", "unknown"):
            record = self.store.transition(run, record["revision"], state, "ou_owner")
        with self.assertRaises(IntakeRejected):
            self.store.transition(run, record["revision"], "running", "ou_owner")

    def test_independent_qa_evidence_is_required_not_ci_alone(self):
        run = self.run_id(workitem=self.key)
        record = self.store.get_run(run)
        for state in ("ready", "queued", "running", "waiting_ci", "waiting_qa"):
            record = self.store.transition(run, record["revision"], state, "ou_owner")
        for kind in ("pr", "ci", "qa"):
            self.store.add_evidence(run, kind, "github://source/123", "ou_owner",
                                    verified=False)
        with self.assertRaises(IntakeRejected):
            self.store.transition(run, record["revision"], "completed", "ou_owner")
        # An independently trusted adapter must supply verified=True, and its
        # verifier identity must differ from the implementer.
        self.store.add_evidence(run, "pr", "github://source/verified_pr",
                                "trusted_github", verified=True)
        self.store.add_evidence(run, "ci", "github://source/verified_ci",
                                "trusted_github", verified=True)
        self.store.add_evidence(run, "qa", "tapd://source/verified_qa",
                                "ou_qa", verified=True)
        self.assertEqual(
            "completed",
            self.store.transition(run, record["revision"], "completed", "ou_owner")["status"],
        )

    def make_card(self, run):
        register_card(self.store, run, "card_1", now=NOW)
        bind_sent_message(self.store, "card_1", "om_card")
        return render_card(self.store, "card_1", KEY, now=NOW)

    def callback(self, button, event_id="evt_1", actor="ou_owner",
                 message_id="om_card", chat="oc_team", tenant="tenantA"):
        return {
            "schema": "2.0",
            "header": {
                "event_id": event_id, "tenant_key": tenant,
                "token": "private-verification-token",
                "event_type": "card.action.trigger", "app_id": "cli_test",
            },
            "event": {
                "operator": {"open_id": actor, "tenant_key": tenant},
                "action": {"tag": "button", "value": copy.deepcopy(button)},
                "host": "im_message",
                "context": {"open_message_id": message_id, "open_chat_id": chat},
            },
        }

    def accept(self, callback, now=NOW):
        return accept_callback(
            self.store, callback, "private-verification-token",
            "cli_test", KEY, now=now,
        )

    def test_card_json_and_durable_action_ack_without_execution(self):
        run = self.run_id()
        payload = self.make_card(run)
        self.assertEqual("2.0", payload["schema"])
        self.assertEqual("研发任务", payload["header"]["title"]["content"])
        buttons = [x for x in payload["body"]["elements"] if x["tag"] == "button"]
        self.assertEqual(3, len(buttons))
        action = next(b for b in buttons if
                      b["behaviors"][0]["value"]["action"] == "request_execution")
        receipt = self.accept(self.callback(action["behaviors"][0]["value"]))
        self.assertTrue(receipt["accepted"])
        self.assertIn("等待执行端", card_ack(receipt)["toast"]["content"])
        self.assertEqual("proposed", self.store.get_run(run)["status"])
        self.assertEqual(1, len(pending_actions(self.store)))

    def test_duplicate_click_is_idempotent_distinct_event_stale(self):
        run = self.run_id()
        self.make_card(run)
        button = render_card(self.store, "card_1", KEY, now=NOW)["body"]["elements"][1]
        click = self.callback(button["behaviors"][0]["value"])
        self.assertTrue(self.accept(click)["accepted"])
        self.assertTrue(self.accept(click)["duplicate"])
        with self.assertRaises(IntakeRejected):
            self.accept(self.callback(button["behaviors"][0]["value"], event_id="evt_2"))
        self.assertEqual(1, len(pending_actions(self.store)))

    def test_card_event_conflict_wrong_user_wrong_message_bad_signature(self):
        run = self.run_id()
        self.make_card(run)
        value = render_card(self.store, "card_1", KEY, now=NOW)["body"]["elements"][1][
            "behaviors"][0]["value"]
        for payload in (
            self.callback(value, actor="ou_attacker"),
            self.callback(value, message_id="om_other"),
            self.callback(value, tenant="tenantB"),
            self.callback(value, chat="oc_other"),
        ):
            with self.assertRaises(IntakeRejected):
                self.accept(payload)
        forged = copy.deepcopy(value)
        forged["action"] = "request_cancel"
        with self.assertRaises(IntakeRejected):
            self.accept(self.callback(forged))
        good = self.callback(value)
        self.accept(good)
        # Signed but distinct valid value with same event ID conflicts.
        new_value = render_card(self.store, "card_1", KEY, now=NOW)[
            "body"]["elements"][1]["behaviors"][0]["value"]
        with self.assertRaises(EventConflict):
            self.accept(self.callback(new_value))

    def test_expiry_and_message_rebinding_denied(self):
        run = self.run_id()
        register_card(self.store, run, "card_1", now=NOW)
        first = render_card(self.store, "card_1", KEY, now=NOW)
        bind_sent_message(self.store, "card_1", "om_card")
        with self.assertRaises(IntakeRejected):
            bind_sent_message(self.store, "card_1", "om_other")
        value = first["body"]["elements"][1]["behaviors"][0]["value"]
        with self.assertRaises(IntakeRejected):
            self.accept(self.callback(value), now=NOW + CARD_LIFETIME_SECONDS)
        with self.assertRaises(IntakeRejected):
            render_card(self.store, "card_1", KEY, now=NOW + CARD_LIFETIME_SECONDS)

    def test_session_exact_scope_binding_and_no_last(self):
        run = self.run_id()
        sessions = SessionRegistry(self.store)
        sessions.bind(run, self.event, "vstrong100", "/srv/robot-app",
                      "/srv/codex-home", "thr_abc")
        binding = sessions.exact(run, self.event, "vstrong100", "/srv/robot-app",
                                 "/srv/codex-home")
        request = sessions.resume_request(binding)
        self.assertEqual("thr_abc", request["params"]["threadId"])
        self.assertNotIn("--last", repr(request))
        self.assertEqual("turn/interrupt",
                         sessions.interrupt_request(binding, "turn_xyz")["method"])
        for host, path, home in (
            ("other_host", "/srv/robot-app", "/srv/codex-home"),
            ("vstrong100", "/srv/other", "/srv/codex-home"),
            ("vstrong100", "/srv/robot-app", "/srv/other"),
        ):
            with self.assertRaises(IntakeRejected):
                sessions.exact(run, self.event, host, path, home)
        with self.assertRaises(IntakeRejected):
            sessions.bind(run, self.event, "vstrong100", "/srv/robot-app",
                          "/srv/codex-home", "thr_different")

    def test_session_turn_requires_explicit_fresh_nonshared_grant(self):
        run = self.run_id()
        sessions = SessionRegistry(self.store)
        sessions.bind(run, self.event, "vstrong100", "/srv/robot-app",
                      "/srv/codex-home", "thr_abc")
        binding = sessions.exact(run, self.event, "vstrong100", "/srv/robot-app",
                                 "/srv/codex-home")
        with self.assertRaises(IntakeRejected):
            sessions.turn_request(binding, None, "分析系统")
        with self.assertRaises(IntakeRejected):
            RuntimeGrant(run, "ou_owner", "robot-app", "edit", "codex_shared",
                         NOW+10, "approval_1")
        grant = RuntimeGrant(run, "ou_owner", "robot-app", "edit",
                             "approved_external", NOW+10, "approval_1")
        with self.assertRaises(IntakeRejected):
            sessions.turn_request(binding, grant, "分析系统", now=NOW)
        with self.assertRaises(IntakeRejected):
            sessions.turn_request(binding, grant, "分析系统",
                                  model_calls_enabled=True, now=NOW+11)
        rpc = sessions.turn_request(binding, grant, "分析系统",
                                    model_calls_enabled=True, now=NOW)
        self.assertEqual("turn/start", rpc["method"])
        self.assertEqual("on-request", rpc["params"]["approvalPolicy"])

    def test_nonmodel_host_probe_uses_only_help_and_version(self):
        fake = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.sessions.subprocess.run",
            return_value=fake,
        ) as called:
            result = probe_local_app_server()
        self.assertTrue(result["available"])
        self.assertFalse(result["qualified_for_model_calls"])
        self.assertEqual(
            [["codex", "--version"], ["codex", "app-server", "--help"]],
            [c.args[0] for c in called.call_args_list],
        )


class ReadOnlyProviderTest(unittest.TestCase):
    def test_tapd_reads_exact_bug_and_story(self):
        calls = []
        def request(method, url, headers, body):
            calls.append((method, url, body))
            field = "Bug" if "/bugs?" in url else "Story"
            return {"status": 1, "data": [{
                field: {
                    "id": "12345", "workspace_id": "10104801",
                    "title": "Crash", "name": "Add feature", "modified": "2026-11-20",
                    "description": "External text is untrusted",
                }
            }]}
        reader = TapdReader("tenantA", "secret-token", request)
        for kind in ("defect", "requirement"):
            key = WorkItemKey("tapd", "tenantA", "10104801", kind, "12345")
            snapshot = reader.read(key)
            self.assertEqual(key, snapshot.key)
            self.assertEqual("2026-11-20", snapshot.version)
        self.assertTrue(all(call[0] == "GET" and call[2] is None for call in calls))

    def test_tapd_mismatched_item_and_http_failure_fail_closed(self):
        key = WorkItemKey("tapd", "tenantA", "10104801", "defect", "12345")
        reader = TapdReader("tenantA", "secret-token", lambda *a: {
            "status": 1, "data": [{"Bug": {
                "id": "999", "workspace_id": "10104801", "title": "Wrong",
                "modified": "today",
            }}],
        })
        with self.assertRaises(IntakeRejected):
            reader.read(key)
        denied = TapdReader("tenantA", "secret-token",
                            lambda *a: {"status": 0, "info": "forbidden"})
        with self.assertRaises(IntakeRejected):
            denied.read(key)

    def test_meegle_plugin_scope_source_kind_and_id(self):
        calls = []
        def request(method, url, headers, body):
            calls.append((method, url, body))
            return {"err_code": 0, "data": [{
                "id": 98765, "project_key": "project123",
                "work_item_type_key": "story", "name": "New requirement",
                "updated_at": "2026-11-20T00:00:00Z",
            }]}
        reader = FeishuProjectReader(
            "tenantA", "https://project.feishu.cn", "secret-plugin",
            "owner", request,
        )
        key = WorkItemKey("feishu_project", "tenantA", "project123",
                          "requirement", "98765")
        snapshot = reader.read(key)
        self.assertEqual(key, snapshot.key)
        self.assertEqual("POST", calls[0][0])
        self.assertEqual({"work_item_ids": [98765]}, calls[0][2])
        self.assertTrue(calls[0][1].endswith("/work_item/story/query"))
        with self.assertRaises(IntakeRejected):
            reader.read(WorkItemKey("feishu_project", "tenantB", "project123",
                                    "requirement", "98765"))

    def test_meegle_host_and_missing_version_fail_closed(self):
        with self.assertRaises(IntakeRejected):
            FeishuProjectReader(
                "tenantA", "http://127.0.0.1", "secret-plugin", "owner",
                lambda *a: {}, 
            )
        reader = FeishuProjectReader(
            "tenantA", "https://project.feishu.cn", "secret-plugin",
            "owner", lambda *a: {"err_code": 0, "data": [{
                "id": 98765, "project_key": "project123",
                "work_item_type_key": "story", "name": "No version",
            }]},
        )
        with self.assertRaises(IntakeRejected):
            reader.read(WorkItemKey("feishu_project", "tenantA",
                                    "project123", "requirement", "98765"))


if __name__ == "__main__":
    unittest.main()
