"""Source-only Feature/Bug lifecycle proof with fake Codex/Git/QA transports.

No paid model, external API, Git publication or hardware is touched.
"""
from __future__ import annotations

import hashlib
import hmac
import pathlib
import tempfile
import time
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.delivery import (
    DeliveryCoordinator, PublicationGrant,
)
from tools.codex_assets.feishu_engineering_agent.feedback import SourceFeedback
from tools.codex_assets.feishu_engineering_agent.manual_items import ManualWorkItemService
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent
from tools.codex_assets.feishu_engineering_agent.runtime_bridge import NativeTurnCoordinator
from tools.codex_assets.feishu_engineering_agent.sessions import SessionRegistry
from tools.codex_assets.feishu_engineering_agent.workflow import (
    EngineeringWorkflow, ExecutionApproval,
)

KEY = b"full-feature-fake-private-approval-key-32bytes"
QA_KEY = b"separate-human-qa-key-32-bytes-minimum-for-tests"
SHA = "0123456789abcdef0123456789abcdef01234567"


class FullWorkflowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="fea-e2e-")
        self.addCleanup(tmp.cleanup)
        self.manual = ManualWorkItemService(
            pathlib.Path(tmp.name) / "private.sqlite3",
        )
        self.store = self.manual.store
        self.workflow = EngineeringWorkflow(self.store)
        self.sessions = SessionRegistry(self.store)
        self.native = NativeTurnCoordinator(self.store, self.sessions)
        self.delivery = DeliveryCoordinator(self.store)
        self.feedback = SourceFeedback(self.store)

    def event(self, message_id, text):
        return InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_engineer",
            message_id, text,
        )

    def run_scenario(self, kind, suffix, repo):
        provider = "tapd" if kind == "defect" else "feishu_project"
        provider_kind = "缺陷" if kind == "defect" else "需求"
        registration = self.event(
            "om_source_" + suffix,
            "/wi add " + provider + " " + provider_kind + " ws" + suffix +
            " 123456 repo=" + repo + " | 提交原业务工作项",
        )
        response = self.manual.handle(registration, repo, {repo})
        source_id = response.split("AgentRun：", 1)[1].split("\n")[0]
        action = self.event(
            "om_attempt_" + suffix,
            "/wi attempt " + source_id + " edit | 在隔离工作区完成SDD、代码和测试",
        )
        child = self.manual.handle(action, repo, {repo})
        child_id = child.split("新Run：", 1)[1].split("\n")[0]
        approved = ExecutionApproval(
            child_id, "ou_engineer", "tenantA", "oc_team", repo, "edit",
            "sdd_approved_" + suffix, "external_approved",
            int(time.time()) + 300, True,
        )
        signature = self.workflow.sign_approval(approved, KEY)
        grant = self.workflow.authorize_queue(
            approved, signature, KEY, action, {repo},
        )
        self.sessions.bind(
            child_id, action, "qualified-host", "/srv/" + repo,
            "/srv/codex-private", "thread_" + suffix,
        )
        fake_codex = mock.Mock(return_value={
            "result": {"turn": {"id": "turn_" + suffix}},
        })
        started = self.native.dispatch(
            child_id, action, "qualified-host", "/srv/" + repo,
            "/srv/codex-private", grant, "研究后按已审批SDD实现",
            fake_codex, model_calls_enabled=True,
        )
        self.assertFalse(started["verified_complete"])
        self.assertEqual(1, fake_codex.call_count)
        self.native.observe(child_id, action, {
            "method": "turn/completed",
            "params": {"threadId": "thread_" + suffix,
                       "turn": {"id": "turn_" + suffix, "status": "completed"}},
        })
        publication_grant = PublicationGrant(
            child_id, "ou_engineer", repo, "manual_publication_" + suffix,
            int(time.time()) + 300,
        )
        fake_publisher = mock.Mock(return_value={
            "pr_id": "pr_" + suffix, "head_sha": SHA,
            "repo_full_name": "team/" + repo,
        })
        submitted = self.delivery.publish_once(
            child_id, action, publication_grant, "team/" + repo, SHA,
            "feat_" + suffix, fake_publisher,
            remote_write_enabled=True,
        )
        self.assertEqual("acknowledged_not_verified", submitted["publication"])
        for evidence_type, reference in (
            ("pr", "github://pr_" + suffix),
            ("ci", "github://ci_" + suffix),
        ):
            observation = {
                "head_sha": SHA, "repo_alias": repo,
                "reference": reference, "state": "open", "conclusion": "success",
            }
            self.delivery.verify_git(
                child_id, action, evidence_type, reference, SHA,
                lambda unused, observation=observation: observation,
            )
        self.assertEqual("waiting_qa",
                         self.delivery.advance_after_ci(child_id, action)["status"])
        stamp = int(time.time())
        ref = "qa://independent_" + suffix
        fingerprint = self.store.get_run(child_id)["workitem_fp"]
        proof = self.delivery.qa_message(
            child_id, fingerprint, SHA, "ou_independent_qa", ref, stamp,
        )
        sig = hmac.new(QA_KEY, proof, hashlib.sha256).hexdigest()
        self.delivery.accept_manual_qa(
            child_id, action, SHA, "ou_independent_qa", ref, stamp, sig, QA_KEY,
        )
        finished = self.delivery.complete_engineering_only(child_id, action)
        self.assertEqual("completed", finished["run_status"])
        self.assertEqual("external_owner_must_accept", finished["workitem_status"])
        draft = self.feedback.draft(child_id, action)
        self.assertIn("原系统负责人", draft)
        self.assertEqual("proposed", self.store.get_run(source_id)["status"])
        self.assertTrue(self.workflow.status_for_source(
            source_id, action,
        )["attempts"])
        return child_id

    def test_one_requirement_and_one_bug_go_through_code_level_contract(self):
        # All external operations are stubbed and no real model is invoked.
        feature = self.run_scenario("requirement", "feat", "robot-app")
        bug = self.run_scenario("defect", "bug", "pcr02-mcu")
        self.assertNotEqual(feature, bug)
        self.assertEqual(2, len([feature, bug]))


if __name__ == "__main__":
    unittest.main()
