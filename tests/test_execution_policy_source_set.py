from __future__ import annotations

import hashlib
import json
import pathlib
import unittest

from tools.codex_assets.execution_policy.contracts import (
    POLICY_SCHEMA_V2,
    goal_intake_attestation_sha256,
    validate_policy,
)
from tools.codex_assets.execution_policy.reducer import reduce_events

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_BLOBS = {
    "__init__.py": "677b83c8f18254bea0b07a497ceef0941fe766ce",
    "contracts.py": "10139ff831beb12468363e35982be87c9b87701c",
    "decision.py": "63215b0d7a8a7b0d354dc1f463d96c788b69e0e8",
    "reducer.py": "65659cd0b739c9c582dd166c4d76050d8e6c4996"
}

def git_blob_sha(path: pathlib.Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class ExecutionPolicySourceSetTest(unittest.TestCase):
    def test_vendored_execution_policy_is_explicitly_pinned_to_11416(self) -> None:
        directory = ROOT / "tools/codex_assets/execution_policy"
        self.assertEqual(set(SOURCE_BLOBS), {p.name for p in directory.glob("*.py")})
        for filename, expected in SOURCE_BLOBS.items():
            self.assertEqual(expected, git_blob_sha(directory / filename))
        provider = json.loads((ROOT / "manifests/provider-locks/agent-dev-kit.json").read_text())
        self.assertRegex(provider["version"], r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertRegex(provider["provider_commit"], r"^[0-9a-f]{40}$")
        behavior=json.loads((ROOT/"manifests/execution_policy.json").read_text())["engine"]["behavior_baseline"]
        self.assertEqual("11.4.16", behavior["version"])
        self.assertEqual("c41f7c933f653dd702b0d8042ae9df38807430dc", behavior["commit"])
        split=json.loads((ROOT/"manifests/provider-locks/agent-dev-kit-execution-policy.json").read_text())
        self.assertEqual("codex-execution-policy-source-lock/v1", split["schema"])
        self.assertEqual(behavior["commit"], split["source"]["commit"])
        self.assertEqual(behavior["version"], split["source"]["version"])
        self.assertEqual(SOURCE_BLOBS, behavior["source_blobs"])
        self.assertEqual(provider["provider_commit"], split["consumer"]["commit"])
        self.assertEqual(provider["version"], split["consumer"]["version"])

    def test_policy_manifest_is_v2_only(self) -> None:
        manifest = json.loads((ROOT / "manifests/execution_policy.json").read_text())
        self.assertEqual(4, manifest["schema_version"])
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
