"""Feature/Bug PR/CI/QA + source-feedback contracts; entirely offline."""
from __future__ import annotations

import hashlib
import hmac
import pathlib
import tempfile
import time
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.delivery import (
    DeliveryCoordinator, PublicationGrant, PublicationUnknown,
)
from tools.codex_assets.feishu_engineering_agent.feedback import (
    FeedbackUnknown, SourceFeedback,
)
from tools.codex_assets.feishu_engineering_agent.models import (
    InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.state import RunStore

SHA = "0123456789abcdef0123456789abcdef01234567"
QA_SECRET = b"independent-qa-reviewer-private-key-32-bytes-required"


class DeliveryContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-delivery-")
        self.addCleanup(temp.cleanup)
        self.store = RunStore(pathlib.Path(temp.name) / "state.sqlite3")
        self.event = InboundEvent("feishu_message", "tenantA", "oc_team",
                                  "ou_engineer", "om_1", "开发需求")
        self.key = WorkItemKey("tapd", "tenantA", "10104801", "defect", "123")
        self.run = self.store.create_run(
            self.event, "robot-app", {"robot-app"}, "edit", self.key,
        )
        self.delivery = DeliveryCoordinator(self.store)
        self.feedback = SourceFeedback(self.store)
        row = self.store.get_run(self.run)
        for status in ("ready", "queued", "running", "waiting_ci"):
            row = self.store.transition(
                self.run, row["revision"], status, self.event.actor,
            )

    def grant(self):
        return PublicationGrant(
            self.run, "ou_engineer", "robot-app",
            "approved_pr_only", int(time.time())+120,
        )

    def publication(self, publisher, enabled=True):
        return self.delivery.publish_once(
            self.run, self.event, self.grant(), "jiying2007/robot-app", SHA,
            "refs/heads/feat-test", publisher,
            remote_write_enabled=enabled,
        )

    def observer(self, kind, reference, success=True):
        return lambda ref: {
            "head_sha": SHA, "repo_alias": "robot-app", "reference": ref,
            "state": "open", "conclusion": "success" if success else "failure",
            "contract_verified": True,
        }

    def verify_pr_ci(self):
        self.delivery.verify_git(
            self.run, self.event, "pr", "github://pr/11", SHA,
            self.observer("pr", "github://pr/11"),
        )
        self.delivery.verify_git(
            self.run, self.event, "ci", "github://actions/22", SHA,
            self.observer("ci", "github://actions/22"),
        )

    def test_explicit_pr_publication_and_no_blind_replay(self):
        remote = mock.Mock(return_value={
            "pr_id": "PR_11", "head_sha": SHA,
            "repo_full_name": "jiying2007/robot-app",
        })
        with self.assertRaises(IntakeRejected):
            self.publication(remote, enabled=False)
        remote.assert_not_called()
        receipt = self.publication(remote)
        self.assertEqual("acknowledged_not_verified", receipt["publication"])
        self.assertEqual(1, remote.call_count)
        with self.assertRaises(IntakeRejected):
            self.publication(remote)
        remote.assert_called_once()

    def test_uncertain_pr_result_recovery_requires_manual_reconcile(self):
        remote = mock.Mock(side_effect=TimeoutError("remote write may have succeeded"))
        with self.assertRaises(PublicationUnknown):
            self.publication(remote)
        with self.assertRaises(IntakeRejected):
            self.publication(remote)
        self.assertEqual(1, remote.call_count)
        self.assertEqual(0, self.delivery.mark_unconfirmed_remote_effects_unknown())

    def test_observed_pr_and_ci_are_distinct_from_qa(self):
        self.delivery.verify_git(
            self.run, self.event, "pr", "github://pr/11", SHA,
            self.observer("pr", "github://pr/11"),
        )
        with self.assertRaises(IntakeRejected):
            self.delivery.advance_after_ci(self.run, self.event)
        with self.assertRaises(IntakeRejected):
            self.delivery.verify_git(
                self.run, self.event, "ci", "github://actions/22", SHA,
                self.observer("ci", "github://actions/22", success=False),
            )
        self.delivery.verify_git(
            self.run, self.event, "ci", "github://actions/22", SHA,
            self.observer("ci", "github://actions/22"),
        )
        self.assertEqual("waiting_qa",
                         self.delivery.advance_after_ci(self.run, self.event)["status"])
        with self.assertRaises(IntakeRejected):
            self.delivery.complete_engineering_only(self.run, self.event)

    def test_signed_independent_qa_completes_run_not_external_workitem(self):
        self.verify_pr_ci()
        self.delivery.advance_after_ci(self.run, self.event)
        stamp = int(time.time())
        reference = "tapd://qa/retest_1"
        payload = DeliveryCoordinator.qa_message(
            self.run, self.key.fingerprint, SHA, "ou_independent_qa", reference, stamp,
        )
        signature = hmac.new(QA_SECRET, payload, hashlib.sha256).hexdigest()
        with self.assertRaises(IntakeRejected):
            self.delivery.accept_manual_qa(
                self.run, self.event, SHA, "ou_engineer", reference, stamp,
                signature, QA_SECRET,
            )
        with self.assertRaises(IntakeRejected):
            self.delivery.accept_manual_qa(
                self.run, self.event, SHA, "ou_independent_qa", reference, stamp,
                "forged", QA_SECRET,
            )
        result = self.delivery.accept_manual_qa(
            self.run, self.event, SHA, "ou_independent_qa", reference, stamp,
            signature, QA_SECRET,
        )
        self.assertTrue(result["verified"])
        self.assertFalse(result["source_closed"])
        self.assertTrue(self.delivery.accept_manual_qa(
            self.run, self.event, SHA, "ou_independent_qa", reference, stamp,
            signature, QA_SECRET,
        )["duplicate"])
        finished = self.delivery.complete_engineering_only(self.run, self.event)
        self.assertEqual("completed", finished["run_status"])
        self.assertEqual("external_owner_must_accept", finished["workitem_status"])

    def test_feedback_manual_draft_and_explicit_remote_comment_only(self):
        draft = self.feedback.draft(self.run, self.event)
        self.assertIn("用户", draft)
        self.assertIn("原系统负责人", draft)
        writer = mock.Mock(return_value={
            "operation": "append_comment_only", "provider": "tapd",
            "item_id": "123", "reference": "tapd://comment_55",
        })
        with self.assertRaises(IntakeRejected):
            self.feedback.post_once(
                self.run, self.event, "version_1", "approved_comment",
                writer, remote_write_enabled=False,
            )
        writer.assert_not_called()
        with self.assertRaises(IntakeRejected):
            self.feedback.post_once(
                self.run, self.event, "version_1", "approved_comment",
                writer, remote_write_enabled=True,
            )  # waiting_ci is not source feedback-ready
        writer.assert_not_called()
        self.verify_pr_ci()
        self.delivery.advance_after_ci(self.run, self.event)
        posted = self.feedback.post_once(
            self.run, self.event, "version_1", "approved_comment",
            writer, remote_write_enabled=True,
        )
        self.assertFalse(posted["source_workitem_closed"])
        self.assertEqual("append_comment_only", writer.call_args.args[0]["operation"])
        with self.assertRaises(IntakeRejected):
            self.feedback.post_once(
                self.run, self.event, "version_1", "approved_comment",
                writer, remote_write_enabled=True,
            )
        writer.assert_called_once()

    def test_uncertain_source_feedback_not_replayed(self):
        self.verify_pr_ci()
        self.delivery.advance_after_ci(self.run, self.event)
        writer = mock.Mock(side_effect=TimeoutError("unknown response"))
        with self.assertRaises(FeedbackUnknown):
            self.feedback.post_once(
                self.run, self.event, "version_1", "approved_comment",
                writer, remote_write_enabled=True,
            )
        self.assertEqual("unknown", self.feedback.recover_unknown(self.run, self.event))
        with self.assertRaises(IntakeRejected):
            self.feedback.post_once(
                self.run, self.event, "version_1", "approved_comment",
                writer, remote_write_enabled=True,
            )
        writer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
