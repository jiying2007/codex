"""Host-owned verification of local routing; never a human or release approval."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


# This is the sole serialized digest domain, not a runtime release or an
# alternate routing backend. The upstream intake requires source_version.
_ROUTING_SCHEMA = "codex-project-routing/v2"
_ROUTING_AUTHORITY, _ROUTING_VERSION = _ROUTING_SCHEMA.split("/")


def routing_binding(root, thread, request_sha256, task_mode, criteria, evidence, open_items):
    """Construct the single canonical local binding for intake and verification."""
    from .execution_policy_intake import _checked_request
    from .execution_policy_adapter import ExecutionPolicyAdapterError

    rules = {}
    for label, path in (("runtime", root / "AGENTS.md"), ("project", Path(thread["cwd"]) / "AGENTS.md")):
        if path.is_file():
            rules[label] = hashlib.sha256(_checked_request(path)).hexdigest()
    if not rules:
        raise ExecutionPolicyAdapterError("ensure requires actual project or runtime routing rules")
    record = {
        "schema_version": _ROUTING_SCHEMA, "task_mode": task_mode,
        "thread_id": thread["thread_id"],
        "cwd_sha256": hashlib.sha256(str(Path(thread["cwd"]).resolve()).encode()).hexdigest(),
        "request_sha256": request_sha256, "rule_sha256": rules,
        "success_criteria": criteria, "required_evidence": evidence, "open_items": open_items,
    }
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "goal_id": "task-" + digest[:24],
        "routing_decision_sha256": digest,
        "authority_id": _ROUTING_AUTHORITY,
        "source_id": _ROUTING_AUTHORITY,
        "source_version": _ROUTING_VERSION,
        "decision_id": "routing-" + digest[:24],
    }


def verifier(root, thread, events):
    """Bind the engine callback to the current thread and its actual start event.

    Mode is the Agent's recorded task boundary. Verification establishes local
    routing provenance, not that an OS sandbox enforced read-only execution.
    Unverified or replanned intakes retain the canonical conservative floor.
    """
    def verify(intake, policy):
        from .execution_policy_intake import _user_request_matches

        if (policy.get("verification_backend") != "managed-authority-registry"
                or intake.get("authority_id") != _ROUTING_AUTHORITY
                or thread["thread_id"] != os.environ.get("CODEX_THREAD_ID")):
            return False
        provenance = intake["provenance"]
        if (provenance.get("kind") != "routing-decision"
                or provenance.get("source_id") != _ROUTING_AUTHORITY
                or provenance.get("source_version") != _ROUTING_VERSION):
            return False
        for event in reversed(events):
            payload = event.get("payload", {})
            if event.get("event_type") != "goal.started" or payload.get("goal_id") != intake["goal_id"]:
                continue
            if event.get("thread_id") != thread["thread_id"] or payload.get("intake") != intake:
                return False
            binding = routing_binding(root, thread, intake["request_sha256"], intake["task_mode"],
                                      payload["success_criteria"], payload["required_evidence"],
                                      payload["open_items_count"])
            return (binding["routing_decision_sha256"] == intake["routing_decision_sha256"]
                    and intake["goal_id"] == binding["goal_id"]
                    and provenance["decision_id"] == binding["decision_id"]
                    and _user_request_matches(Path(thread["rollout_path"]), sha256=intake["request_sha256"]))
        return False
    return verify
