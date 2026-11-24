"""Manual WorkItem -> many separate signed and scoped AgentRun attempts."""
from __future__ import annotations

import hashlib
import pathlib
import sqlite3
import tempfile
import time
import unittest

from tools.codex_assets.feishu_engineering_agent.manual_items import ManualWorkItemService
from tools.codex_assets.feishu_engineering_agent.models import (
    EventConflict, InboundEvent, IntakeRejected,
)
from tools.codex_assets.feishu_engineering_agent.workflow import (
    EngineeringWorkflow, ExecutionApproval, local_agent_policy_digest,
)

SECRET = b"host-independent-approval-key-over-thirty-two-bytes"


class WorkflowContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-workflow-chain-")
        self.addCleanup(temp.cleanup)
        self.db = pathlib.Path(temp.name) / "state.sqlite3"
        self.manual = ManualWorkItemService(self.db)
        self.event = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_source", "/wi add tapd 缺陷 10104801 123456 repo=robot-app | 回充过流",
        )
        receipt = self.manual.handle(self.event, "robot-app", {"robot-app"})
        self.source_id = receipt.split("AgentRun：", 1)[1].split("\n")[0]
        self.workflow = EngineeringWorkflow(self.manual.store)

    def attempt(self, event_id="om_attempt", mode="edit", text="实现修复并回归测试"):
        msg = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", event_id,
            "/wi attempt " + self.source_id + " " + mode + " | " + text,
        )
        response = self.manual.handle(msg, "robot-app", {"robot-app"})
        return msg, response.split("新Run：", 1)[1].split("\n")[0]

    def approval(self, run_id, **overrides):
        args = dict(
            run_id=run_id, actor="ou_owner", tenant="tenantA", chat="oc_team",
            repo="robot-app", mode="edit", approval_ref="verified_sdd_1",
            billing_source="external_approved", expires_at=int(time.time()) + 180,
            sdd_reviewed=True,
        )
        args.update(overrides)
        return ExecutionApproval(**args)

    def test_attempt_creates_separate_run_without_model_or_source_change(self):
        event, child_id = self.attempt()
        self.assertNotEqual(self.source_id, child_id)
        child = self.manual.store.get_run(child_id, event)
        with sqlite3.connect(str(self.db)) as db:
            scope_digest = db.execute(
                "SELECT scope_sha256 FROM fea_attempt_links WHERE attempt_run_id=?",
                (child_id,),
            ).fetchone()[0]
        self.assertEqual(hashlib.sha256("实现修复并回归测试".encode("utf-8")).hexdigest(),
                         scope_digest)
        self.assertEqual("edit", child["mode"])
        self.assertEqual("proposed", child["status"])
        self.assertEqual(
            self.manual.store.get_run(self.source_id)["workitem_fp"],
            child["workitem_fp"],
        )
        linked = self.workflow.status_for_source(self.source_id, event)
        self.assertEqual(child_id, linked["attempts"][0]["attempt_run_id"])
        self.assertFalse(linked["workitem_closed"])
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(2, db.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])
        self.assertNotIn("实现修复并回归测试".encode(), self.db.read_bytes())
        same = self.manual.handle(event, "robot-app", {"robot-app"})
        self.assertIn(child_id, same)
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(2, db.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])

    def test_chat_status_lists_bounded_attempts_and_replay_uses_actual_state(self):
        event, child_id = self.attempt()
        scope = hashlib.sha256("实现修复并回归测试".encode("utf-8")).hexdigest()
        policy = local_agent_policy_digest(
            1000, "robot-app", "edit", "external_api_key", {"edit"}, "worktree", True,
        )
        self.workflow.authorize_local_agent_queue(
            child_id, event, 1000, {"robot-app"}, {"edit"}, scope,
            "external_api_key", policy,
        )
        replay = self.manual.handle(event, "robot-app", {"robot-app"})
        self.assertIn("状态：queued", replay)
        self.assertIn("未重复创建或执行", replay)
        status = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", "om_status",
            "/wi status " + self.source_id,
        )
        reply = self.manual.handle(status, "robot-app", {"robot-app"})
        self.assertIn(child_id + " edit queued", reply)
        self.assertNotIn("实现修复并回归测试", reply)
        for i in range(6):
            self.attempt(event_id="om_more_" + str(i))
        limited = self.workflow.status_for_source(self.source_id, status)
        self.assertEqual(5, len(limited["attempts"]))
        self.assertTrue(limited["has_more"])
        self.assertIn("仅显示最近 5 条", self.manual.handle(status, "robot-app", {"robot-app"}))
        with self.assertRaises(IntakeRejected):
            self.manual.handle(status, "robot-app", {"other-repo"})
        foreign = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_other", "om_foreign_status",
            status.text,
        )
        with self.assertRaises(IntakeRejected):
            self.manual.handle(foreign, "robot-app", {"robot-app"})

    def test_attempt_replay_and_scope_changes_are_denied(self):
        event, child_id = self.attempt()
        different = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", "om_attempt",
            event.text + " 不同需求",
        )
        with self.assertRaises(EventConflict):
            self.manual.handle(different, "robot-app", {"robot-app"})
        with self.assertRaises(IntakeRejected):
            self.workflow.create_attempt(self.source_id, event, "read", {"robot-app"})
        attacker = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_else",
            "om_bad", event.text,
        )
        with self.assertRaises(IntakeRejected):
            self.workflow.create_attempt(self.source_id, attacker, "edit", {"robot-app"})
        with self.assertRaises(IntakeRejected):
            self.workflow.create_attempt(self.source_id, event, "edit", {"motor-mcu"})

    def test_replayed_event_cannot_rebind_a_different_workitem(self):
        from tools.codex_assets.feishu_engineering_agent.models import WorkItemKey
        event, first_id = self.attempt()
        unrelated = self.manual.store.create_run(
            self.event, "robot-app", {"robot-app"}, mode="read",
            workitem=WorkItemKey("tapd", "tenantA", "10104801", "defect", "999"),
        )
        with self.assertRaisesRegex(IntakeRejected, "cannot change WorkItem source"):
            self.workflow.create_attempt(
                unrelated, event, "edit", {"robot-app"},
                scope_sha256=hashlib.sha256("实现修复并回归测试".encode("utf-8")).hexdigest(),
            )
        self.assertEqual(
            first_id, self.workflow.status_for_source(
                self.source_id, event,
            )["attempts"][0]["attempt_run_id"],
        )

    def test_local_agent_queue_is_scope_bound_and_uses_non_shared_billing(self):
        event, child_id = self.attempt()
        task = "实现修复并回归测试"
        scope = hashlib.sha256(task.encode("utf-8")).hexdigest()
        uid = 1000
        billing = "external_api_key"
        policy = local_agent_policy_digest(
            uid, "robot-app", "edit", billing, {"edit"}, "worktree", True,
        )
        result = self.workflow.authorize_local_agent_queue(
            child_id, event, uid, {"robot-app"}, {"edit"},
            scope, billing, policy,
        )
        self.assertTrue(result["authorized"])
        self.assertEqual("queued", self.manual.store.get_run(child_id)["status"])
        receipt = self.workflow.local_agent_approval(child_id)
        self.assertEqual(uid, receipt["unix_uid"])
        self.assertEqual(scope, receipt["scope_sha256"])
        again = self.workflow.authorize_local_agent_queue(
            child_id, event, uid, {"robot-app"}, {"edit"},
            scope, billing, policy,
        )
        self.assertFalse(again["authorized"])
        with self.assertRaisesRegex(IntakeRejected, "scope"):
            self.workflow.authorize_local_agent_queue(
                child_id, event, uid, {"robot-app"}, {"edit"},
                hashlib.sha256(b"changed").hexdigest(), billing, policy,
            )
        with self.assertRaisesRegex(IntakeRejected, "non-shared"):
            self.workflow.authorize_local_agent_queue(
                child_id, event, uid, {"robot-app"}, {"edit"},
                scope, "codex_shared", policy,
            )
        other_uid = 1001
        other_policy = local_agent_policy_digest(
            other_uid, "robot-app", "edit", billing, {"edit"}, "worktree", True,
        )
        with self.assertRaisesRegex(IntakeRejected, "conflicts"):
            self.workflow.authorize_local_agent_queue(
                child_id, event, other_uid, {"robot-app"}, {"edit"},
                scope, billing, other_policy,
            )

    def test_local_agent_queue_requires_a_manual_workitem_source(self):
        from tools.codex_assets.feishu_engineering_agent.models import WorkItemKey
        parent = self.manual.store.create_run(
            self.event, "robot-app", {"robot-app"}, mode="read",
            workitem=WorkItemKey("tapd", "tenantA", "space", "defect", "other"),
        )
        attempt_event = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_nonmanual_attempt", "/wi attempt " + parent + " edit | exact scope",
        )
        child = self.workflow.create_attempt(
            parent, attempt_event, "edit", {"robot-app"},
            scope_sha256=hashlib.sha256(b"exact scope").hexdigest(),
        )["run_id"]
        from tools.codex_assets.feishu_engineering_agent.workflow import local_agent_policy_digest
        policy = local_agent_policy_digest(
            1000, "robot-app", "edit", "external_api_key", {"edit"}, "worktree", True,
        )
        with self.assertRaisesRegex(IntakeRejected, "manually registered"):
            self.workflow.authorize_local_agent_queue(
                child, attempt_event, 1000, {"robot-app"}, {"edit"},
                hashlib.sha256(b"exact scope").hexdigest(),
                "external_api_key", policy,
            )

    def test_queued_approval_not_reissued_after_remote_dispatch(self):
        event, child_id = self.attempt()
        approved = self.approval(child_id)
        signed = self.workflow.sign_approval(approved, SECRET)
        self.workflow.authorize_queue(
            approved, signed, SECRET, event, {"robot-app"},
        )
        current = self.manual.store.get_run(child_id)
        self.manual.store.transition(
            child_id, current["revision"], "running", event.actor,
        )
        with self.assertRaisesRegex(IntakeRejected, "already started or ended"):
            self.workflow.authorize_queue(
                approved, signed, SECRET, event, {"robot-app"},
            )

    def test_signed_edit_requires_sdd_scoped_repo_and_unshared_budget(self):
        event, child_id = self.attempt()
        bad = self.approval(child_id, sdd_reviewed=False)
        bad_sig = self.workflow.sign_approval(bad, SECRET)
        with self.assertRaises(IntakeRejected):
            self.workflow.authorize_queue(bad, bad_sig, SECRET, event, {"robot-app"})
        approval = self.approval(child_id)
        signature = self.workflow.sign_approval(approval, SECRET)
        with self.assertRaises(IntakeRejected):
            self.workflow.authorize_queue(approval, "forged", SECRET, event,
                                          {"robot-app"})
        grant = self.workflow.authorize_queue(
            approval, signature, SECRET, event, {"robot-app"},
        )
        self.assertEqual("edit", grant.mode)
        self.assertEqual("external_approved", grant.billing_source)
        self.assertEqual("queued", self.manual.store.get_run(child_id)["status"])
        again = self.workflow.authorize_queue(
            approval, signature, SECRET, event, {"robot-app"},
        )
        self.assertEqual(grant.run_id, again.run_id)
        with self.assertRaises(IntakeRejected):
            self.workflow.authorize_queue(
                self.approval(child_id, billing_source="another_approved"),
                signature, SECRET, event, {"robot-app"},
            )

    def test_grant_denied_after_repo_revoked_or_actor_mismatch(self):
        event, child_id = self.attempt()
        approval = self.approval(child_id)
        signature = self.workflow.sign_approval(approval, SECRET)
        with self.assertRaises(IntakeRejected):
            self.workflow.authorize_queue(
                approval, signature, SECRET, event, {"other-repo"},
            )
        other = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_attacker",
            "om_other", "启动开发",
        )
        with self.assertRaises(IntakeRejected):
            self.workflow.authorize_queue(
                approval, signature, SECRET, other, {"robot-app"},
            )
        self.assertEqual("proposed", self.manual.store.get_run(child_id)["status"])

    def test_unapproved_chat_attempt_never_enters_model_queue(self):
        event, child_id = self.attempt(mode="review")
        self.assertEqual("proposed", self.manual.store.get_run(child_id)["status"])
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(0, db.execute(
                "SELECT COUNT(*) FROM fea_run_approvals"
            ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
