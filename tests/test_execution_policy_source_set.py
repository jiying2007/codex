from __future__ import annotations

import hashlib
import json
import pathlib
import unittest

from tools.codex_assets.execution_policy.engine import (
    POLICY_SCHEMA_V2,
    goal_intake_attestation_sha256,
    reduce_events,
    validate_policy,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE_BLOB = "05dd80065ec4c58c342e48ff12d4cd53d3897740"
CONTRACTS_BLOB = "626af591141b2dda6302edbe4363637435066628"


def git_blob_sha(path: pathlib.Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class ExecutionPolicySourceSetTest(unittest.TestCase):
    def test_vendored_execution_policy_matches_adk_704(self) -> None:
        engine = ROOT / "tools/codex_assets/execution_policy/engine.py"
        contracts = ROOT / "tools/codex_assets/execution_policy/contracts.py"
        self.assertEqual(ENGINE_BLOB, git_blob_sha(engine))
        self.assertEqual(CONTRACTS_BLOB, git_blob_sha(contracts))
        provider = json.loads((ROOT / "manifests/provider-locks/agent-dev-kit.json").read_text())
        self.assertEqual("7.0.4", provider["version"])
        self.assertEqual("1d6c28e89eb98a4af5ac978707730783f0c84437", provider["provider_commit"])

    def test_policy_manifest_is_v2_only(self) -> None:
        manifest = json.loads((ROOT / "manifests/execution_policy.json").read_text())
        self.assertEqual(3, manifest["schema_version"])
        self.assertEqual(POLICY_SCHEMA_V2, manifest["policy"]["schema_version"])
        self.assertEqual(POLICY_SCHEMA_V2, validate_policy(manifest["policy"])["schema_version"])
        serialized = json.dumps(manifest, sort_keys=True)
        self.assertNotIn("runtime_control.policy/v1", serialized)
        self.assertNotIn("runtime_control.v1", serialized)

    def test_attested_goal_intake_is_required_by_source_set(self) -> None:
        provenance = {
            "kind": "routing-decision",
            "source_id": "digital-worker",
            "source_version": "1.0.0",
            "decision_id": "decision-1",
            "issued_at": "2026-09-20T00:00:00Z",
        }
        intake = {
            "schema_version": "runtime_control.goal-intake/v1",
            "task_mode": "implementation",
            "artifact_mode": "implementation",
            "goal_id": "goal-1",
            "request_sha256": "a" * 64,
            "routing_decision_sha256": "b" * 64,
            "authority_id": "digital-worker",
            "provenance": provenance,
        }
        intake["attestation_sha256"] = goal_intake_attestation_sha256(
            intake["task_mode"], intake["artifact_mode"], provenance,
            goal_id=intake["goal_id"],
            request_sha256=intake["request_sha256"],
            routing_decision_sha256=intake["routing_decision_sha256"],
            authority_id=intake["authority_id"],
        )
        event = {
            "schema_version": "runtime_control.event/v1",
            "event_id": "evt-1",
            "event_type": "goal.started",
            "thread_id": "thread-1",
            "observed_at": "2026-09-20T00:00:00Z",
            "payload": {
                "goal_id": "goal-1",
                "token_budget": 1000,
                "time_budget_seconds": 3600,
                "usage_baseline_tokens": 0,
                "success_criteria": ["evidence"],
                "required_evidence": ["evidence"],
                "open_items_count": 1,
                "intake": intake,
            },
        }
        state = reduce_events([event])
        self.assertEqual("implementation", state["goal"]["task_mode"])
        self.assertEqual(intake["attestation_sha256"], state["goal"]["intake_attestation_sha256"])


if __name__ == "__main__":
    unittest.main()
