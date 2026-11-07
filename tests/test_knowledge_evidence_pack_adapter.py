import copy
import json
import unittest
from unittest import mock

from tools.codex_assets import knowledge_provider_adapter as adapter


def pack():
    lanes = {lane: [] for lane in ("must", "should", "context", "provisional", "conflict", "missing")}
    lanes["provisional"] = [{"id": "candidate", "summary_zh": "ASP仅支持8k或16k S16LE", "status": "reviewing", "authority": "provisional"}]
    return dict(lanes, schema_version="knowledge-hub.evidence-pack.v1", read_only=True,
                counts={key: len(value) for key, value in lanes.items()}, authority_contract={"active_only": True})


class EvidencePackAdapterTests(unittest.TestCase):
    def test_current_wire_schema_needs_no_generic_status(self):
        adapter.validate_evidence_pack(pack())

    def test_bad_schema_readonly_counts_and_lanes_fail_closed(self):
        for key, value in (("schema_version", "future"), ("read_only", False), ("counts", {}),
                           ("must", {}), ("should", ["instruction"]), ("authority_contract", {})):
            with self.subTest(key=key):
                payload = pack()
                payload[key] = value
                with self.assertRaises(adapter.ProviderAdapterError):
                    adapter.validate_evidence_pack(payload)

    def test_candidate_cannot_be_promoted_by_transport(self):
        for update in ({"authority": "active"}, {"summary_zh": []}, {"id": ""}):
            with self.subTest(update=update):
                payload = pack()
                payload["provisional"][0].update(update)
                with self.assertRaises(adapter.ProviderAdapterError):
                    adapter.validate_evidence_pack(payload)

    def test_active_lane_cannot_contain_reviewing_constraint(self):
        # Hub can keep active metadata pending manual validation in the provisional lane.
        payload = pack()
        payload["provisional"][0]["status"] = "active"
        adapter.validate_evidence_pack(payload)
        self.assertEqual(payload["provisional"][0]["authority"], "provisional")

    def test_active_lane_still_requires_active_authority(self):
        payload = pack()
        payload["must"] = payload["provisional"]
        payload["counts"]["must"] = 1
        with self.assertRaises(adapter.ProviderAdapterError):
            adapter.validate_evidence_pack(payload)

    def test_counts_are_exact_integers(self):
        payload = pack()
        payload["counts"]["provisional"] = True
        with self.assertRaises(adapter.ProviderAdapterError):
            adapter.validate_evidence_pack(payload)

    def test_real_adapter_branch_forwards_existing_auxiliary_contract(self):
        with mock.patch.object(adapter, "verify_source", return_value={"identity": "same"}), \
                mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(pack()))), \
                mock.patch("builtins.print") as output:
            self.assertEqual(adapter.main(["evidence-pack", "ASP", "--json"]), 0)
            self.assertEqual(json.loads(output.call_args.args[0])["provisional"][0]["authority"], "provisional")


if __name__ == "__main__":
    unittest.main()
