from __future__ import annotations

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SessionBootstrapContractTests(unittest.TestCase):
    def test_daily_contract_no_retired_consumer(self):
        contract = json.loads((ROOT / "manifests/session_bootstrap.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], "2.0")
        self.assertEqual(contract["output_contract"]["kind"], "codex-session-bootstrap/v2")
        self.assertEqual(set(contract["modes"]), {"L0", "L1"})
        self.assertEqual(contract["resolution_precedence"], ["explicit_mode", "governed_signal", "default_l0"])
        serialized = json.dumps(contract, sort_keys=True)
        self.assertNotIn("digital-worker", serialized)
        self.assertNotIn("digital_worker", serialized)
        self.assertNotIn("formal", serialized)
        self.assertNotIn("L2", serialized)
        self.assertNotIn("runtime_binding_contract_modes", serialized)

    def test_historical_receipt_schema_is_not_live_bootstrap_authority(self):
        receipt = json.loads((ROOT / "schemas/runtime-execution-receipt.v2.schema.json").read_text(encoding="utf-8"))
        self.assertIs(receipt["additionalProperties"], False)
        for field in ("work_item_id", "run_id", "execution_source_set_identity", "digital_worker_governance_identity"):
            self.assertIn(field, receipt["required"])
        contract = json.loads((ROOT / "manifests/session_bootstrap.json").read_text())
        self.assertNotIn("runtime_receipt_handoff", contract["output_contract"])
        self.assertNotIn("execution_source_set", contract["owns"])


if __name__ == "__main__":
    unittest.main()
