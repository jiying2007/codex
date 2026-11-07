"""Host-owned verification of local routing; never a human or release approval."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def routing_record(root, thread, request_sha256, task_mode, criteria, evidence, open_items):
    from .execution_policy_intake import _checked_request
    from .execution_policy_adapter import ExecutionPolicyAdapterError

    rules = {}
    for label, path in (("runtime", root / "AGENTS.md"), ("project", Path(thread["cwd"]) / "AGENTS.md")):
        if path.is_file():
            rules[label] = hashlib.sha256(_checked_request(path)).hexdigest()
    if not rules:
        raise ExecutionPolicyAdapterError("ensure requires actual project or runtime routing rules")
    return {
        "schema_version": "codex-project-routing/v2", "task_mode": task_mode,
        "thread_id": thread["thread_id"],
        "cwd_sha256": hashlib.sha256(str(Path(thread["cwd"]).resolve()).encode()).hexdigest(),
        "request_sha256": request_sha256, "rule_sha256": rules,
        "success_criteria": criteria, "required_evidence": evidence, "open_items": open_items,
    }


def verifier(root, thread, events):
    """Bind the engine callback to the current thread and its actual start event.

    Mode is the Agent's recorded task boundary. Verification establishes local
    routing provenance, not that an OS sandbox enforced read-only execution.
    Unknown/manual/v1/replanned intakes retain the canonical conservative floor.
    """
    def verify(intake, policy):
        from .execution_policy_intake import _user_request_matches

        if (policy.get("verification_backend") != "managed-authority-registry"
                or intake.get("authority_id") != "codex-project-routing"
                or thread["thread_id"] != os.environ.get("CODEX_THREAD_ID")):
            return False
        provenance = intake["provenance"]
        if (provenance.get("kind") != "routing-decision"
                or provenance.get("source_id") != "codex-project-routing"
                or provenance.get("source_version") != "v2"):
            return False
        for event in reversed(events):
            payload = event.get("payload", {})
            if event.get("event_type") != "goal.started" or payload.get("goal_id") != intake["goal_id"]:
                continue
            if event.get("thread_id") != thread["thread_id"] or payload.get("intake") != intake:
                return False
            routing = routing_record(root, thread, intake["request_sha256"], intake["task_mode"],
                                     payload["success_criteria"], payload["required_evidence"],
                                     payload["open_items_count"])
            digest = hashlib.sha256(json.dumps(routing, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            return (digest == intake["routing_decision_sha256"]
                    and intake["goal_id"] == "task-" + digest[:24]
                    and provenance["decision_id"] == "routing-" + digest[:24]
                    and _user_request_matches(Path(thread["rollout_path"]), sha256=intake["request_sha256"]))
        return False
    return verify
