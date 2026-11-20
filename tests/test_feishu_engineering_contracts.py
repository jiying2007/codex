"""Transport-neutral cross-repo interface version and proof isolation."""
from __future__ import annotations

import hashlib
import pathlib
import tempfile
import unittest

from tools.codex_assets.feishu_engineering_agent.contracts import ContractRegistry
from tools.codex_assets.feishu_engineering_agent.models import (
    InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.state import RunStore

DIGEST = hashlib.sha256(b"proto: differential-wheels-v1").hexdigest()


class CrossRepoContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-contract-")
        self.addCleanup(temp.cleanup)
        self.store = RunStore(pathlib.Path(temp.name) / "state.sqlite3")
        self.event = InboundEvent("feishu_message", "tenantA", "oc_team",
                                  "ou_owner", "om_1", "查看机器人协议")
        self.key = WorkItemKey("tapd", "tenantA", "10104801", "requirement", "123")
        self.soc = self.store.create_run(
            self.event, "robot-app", {"robot-app", "motor-mcu"},
            workitem=self.key,
        )
        self.mcu = self.store.create_run(
            self.event, "motor-mcu", {"robot-app", "motor-mcu"},
            workitem=self.key,
        )
        self.contract = ContractRegistry(self.store)
        self.contract.register(
            self.key, "motion-protocol", "1.0.0", DIGEST,
            ("robot-app", "motor-mcu"), self.event,
            {"robot-app", "motor-mcu"},
        )

    def observer(self, repository):
        return lambda reference: {
            "repo_alias": repository, "reference": reference,
            "contract_sha256": DIGEST, "semantic_version": "1.0.0",
            "ci_conclusion": "success",
        }

    def test_both_repositories_need_own_contract_proof(self):
        status = self.contract.status(
            self.key, "motion-protocol", self.event,
            {"robot-app", "motor-mcu"},
        )
        self.assertEqual(["motor-mcu", "robot-app"], status["missing"])
        self.assertFalse(status["all_repositories_verified"])
        first = self.contract.verify_repository(
            self.soc, self.event, "motion-protocol", "github://contract/soc",
            self.observer("robot-app"),
        )
        self.assertTrue(first["verified"])
        self.assertFalse(first["device_pass"])
        self.assertEqual(
            ["motor-mcu"],
            self.contract.status(self.key, "motion-protocol", self.event,
                                 {"robot-app", "motor-mcu"})["missing"],
        )
        self.contract.verify_repository(
            self.mcu, self.event, "motion-protocol", "github://contract/mcu",
            self.observer("motor-mcu"),
        )
        completed = self.contract.status(
            self.key, "motion-protocol", self.event, {"motor-mcu"},
        )
        self.assertTrue(completed["all_repositories_verified"])
        self.assertFalse(completed["device_verified"])
        self.assertFalse(completed["business_accepted"])

    def test_conflicting_version_cannot_overwrite_same_contract(self):
        with self.assertRaises(IntakeRejected):
            self.contract.register(
                self.key, "motion-protocol", "1.0.0",
                hashlib.sha256(b"different").hexdigest(),
                ("robot-app", "motor-mcu"), self.event,
                {"robot-app", "motor-mcu"},
            )
        with self.assertRaises(IntakeRejected):
            self.contract.register(
                self.key, "motion-protocol", "1.0.0", DIGEST,
                ("robot-app", "untrusted-repo"), self.event,
                {"robot-app", "motor-mcu"},
            )

    def test_missing_qa_or_wrong_repository_evidence_fails(self):
        with self.assertRaises(IntakeRejected):
            self.contract.verify_repository(
                self.soc, self.event, "motion-protocol",
                "github://contract/soc", self.observer("motor-mcu"),
            )
        with self.assertRaises(IntakeRejected):
            self.contract.verify_repository(
                self.soc, self.event, "motion-protocol",
                "github://contract/soc",
                lambda ref: {
                    "repo_alias": "robot-app", "reference": ref,
                    "contract_sha256": DIGEST, "semantic_version": "1.0.0",
                    "ci_conclusion": "failure",
                },
            )
        attacker = InboundEvent("feishu_message", "tenantA", "oc_team",
                                "ou_attacker", "om_x", "状态")
        with self.assertRaises(IntakeRejected):
            self.contract.status(self.key, "motion-protocol", attacker, {"robot-app"})
        with self.assertRaises(IntakeRejected):
            self.contract.verify_repository(
                self.soc, attacker, "motion-protocol",
                "github://contract/soc", self.observer("robot-app"),
            )


if __name__ == "__main__":
    unittest.main()
