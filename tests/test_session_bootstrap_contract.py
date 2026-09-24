from __future__ import annotations

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SessionBootstrapContractTests(unittest.TestCase):
    def test_formal_work_run_and_receipt_handoff_are_ratcheted(self) -> None:
        contract = json.loads((ROOT / "manifests/session_bootstrap.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], "1.3")
        self.assertEqual(contract["runtime_binding_contract_modes"], ["L2"])
        for mode in ("L0", "L1", "L2"):
            self.assertIs(contract["modes"][mode]["digital_worker_contract_required"], mode == "L2")
        self.assertIn("formal_work_run_identity_freeze", contract["owns"])

        formal = contract["modes"]["L2"]
        self.assertIn(
            "engineering_task_package_with_package_id_work_item_id_run_id_base_commit",
            formal["required_inputs"],
        )

        handoff = contract["output_contract"]["runtime_receipt_handoff"]
        self.assertEqual(handoff["schema"], "schemas/runtime-execution-receipt.v2.schema.json")
        self.assertEqual(handoff["work_item_id_from"], "work_identity.work_item_id")
        self.assertEqual(handoff["run_id_from"], "work_identity.run_id")
        self.assertEqual(
            handoff["execution_source_set_identity_from"],
            "execution_source_set.identity",
        )

        rules = contract["rules"]
        for key in (
            "formal_mode_requires_authoritative_work_run_identity_from_engineering_task_package",
            "formal_engineering_task_package_base_commit_must_match_requested_base_commit",
            "formal_execution_source_set_binds_work_item_run_and_package_identity",
            "runtime_receipt_v2_must_reuse_frozen_work_run_and_source_set_identity",
        ):
            self.assertIs(rules[key], True)

    def test_runtime_receipt_v2_requires_the_same_identity_spine(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/runtime-execution-receipt.v2.schema.json").read_text(encoding="utf-8")
        )
        for field in (
            "work_item_id",
            "run_id",
            "execution_source_set_identity",
            "digital_worker_governance_identity",
        ):
            self.assertIn(field, schema["required"])


if __name__ == "__main__":
    unittest.main()
