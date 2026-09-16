from __future__ import annotations

import hashlib
import pathlib
import unittest

from tools.codex_assets.runtime_kernel import (
    POLICY_SCHEMA_V2,
    goal_intake_attestation_sha256,
    reduce_events,
    validate_policy,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE_BLOB = "0acf94e0b6b2224ec6dbabd9d31d9b4e14366a03"
CONTRACTS_BLOB = "4e9ee519e5673025446ddf93dd2a088edd02e283"


def git_blob_sha(path: pathlib.Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class RuntimeControlV2SourceSetTest(unittest.TestCase):
    def test_vendored_execution_policy_matches_provider_blobs(self) -> None:
        engine = ROOT / "tools/codex_assets/execution_policy/engine.py"
        contracts = ROOT / "tools/codex_assets/execution_policy/contracts.py"
        self.assertEqual(ENGINE_BLOB, git_blob_sha(engine))
        self.assertEqual(CONTRACTS_BLOB, git_blob_sha(contracts))

    def test_attested_readonly_goal_intake_is_active(self) -> None:
        policy = {
            "schema_version": POLICY_SCHEMA_V2,
            "token": {"checkpoint_ratio": 0.7, "compact_ratio": 0.9, "stop_ratio": 1.0},
            "context": {"compact_ratio": 0.5},
            "progress": {"staleness_seconds": 900, "retry_limit": 2, "no_progress_limit": 3},
            "artifact_applicability": {
                "readonly": {"steady": [], "final": [], "commit": None, "apply": None, "release": None},
                "implementation": {
                    "steady": [],
                    "final": ["repo", "build"],
                    "commit": ["repo", "build", "review"],
                    "apply": ["repo", "build", "plan", "dry-run"],
                    "release": None,
                },
                "release": {
                    "steady": [],
                    "final": ["repo", "build"],
                    "commit": ["repo", "build", "review"],
                    "apply": ["repo", "build", "plan", "dry-run"],
                    "release": ["repo", "build", "live", "review"],
                },
            },
            "mode_authority_policy": {
                "managed": True,
                "trusted_mode_authorities": [],
                "verification_backend": "not-configured",
            },
            "retention": {"journal_days": 14, "raw_content_stored": False},
        }
        self.assertEqual(POLICY_SCHEMA_V2, validate_policy(policy)["schema_version"])

        provenance = {
            "kind": "routing-decision",
            "source_id": "digital-worker",
            "source_version": "1.0.0",
            "decision_id": "decision-1",
            "issued_at": "2026-09-16T12:00:00Z",
        }
        intake = {
            "schema_version": "runtime_control.goal-intake/v1",
            "task_mode": "readonly",
            "artifact_mode": "readonly",
            "goal_id": "goal-1",
            "request_sha256": "a" * 64,
            "routing_decision_sha256": "b" * 64,
            "authority_id": "digital-worker",
            "provenance": provenance,
        }
        intake["attestation_sha256"] = goal_intake_attestation_sha256(
            intake["task_mode"],
            intake["artifact_mode"],
            provenance,
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
            "observed_at": "2026-09-16T12:00:00Z",
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
        self.assertEqual("readonly", state["goal"]["task_mode"])
        self.assertEqual("readonly", state["goal"]["artifact_mode"])
        self.assertEqual(1, state["goal"]["intake_revision"])
        self.assertEqual(intake["attestation_sha256"], state["goal"]["intake_attestation_sha256"])


if __name__ == "__main__":
    unittest.main()
