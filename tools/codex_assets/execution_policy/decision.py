"""Execution-policy gate evaluation for reduced ADK runtime state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from .contracts import (
    DECISION_SCHEMA_V2,
    GATE_EVENTS,
    GOAL_INTAKE_SCHEMA,
    STATE_SCHEMA,
    ExecutionPolicyError,
    _iso,
    _timestamp,
    _validate_goal_intake,
    validate_policy,
)


def evaluate(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    gate_event: str = "steady",
    task_mode: str | None = None,
    mode_authority_verifier: Callable[[Mapping[str, Any], Mapping[str, Any]], bool] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    normalized_policy = validate_policy(policy)
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise ExecutionPolicyError("unsupported runtime control state schema")
    if gate_event not in GATE_EVENTS:
        raise ExecutionPolicyError("unsupported gate_event")
    goal = state.get("goal") or {}
    if task_mode is not None:
        raise ExecutionPolicyError(
            "runtime_control.policy/v2 task mode is state-bound and cannot be overridden"
        )
    provenance = goal.get("intake_provenance")
    if not isinstance(provenance, dict) or provenance.get("kind") not in {
        "routing-decision", "goal-replan"
    }:
        raise ExecutionPolicyError("runtime_control.policy/v2 requires an attested goal intake")
    last_event_at = state.get("last_event_at")
    if not last_event_at:
        raise ExecutionPolicyError("runtime control state is missing its event provenance")
    bound_intake = _validate_goal_intake(
        {
            "schema_version": GOAL_INTAKE_SCHEMA,
            "task_mode": goal.get("task_mode"),
            "artifact_mode": goal.get("artifact_mode"),
            "goal_id": goal.get("goal_id"),
            "request_sha256": goal.get("request_sha256"),
            "routing_decision_sha256": goal.get("routing_decision_sha256"),
            "authority_id": goal.get("mode_authority_id"),
            "attestation_sha256": goal.get("intake_attestation_sha256"),
            "provenance": provenance,
        },
        event_at=_timestamp(last_event_at, "state.last_event_at"),
        expected_kind=str(provenance["kind"]),
        expected_goal_id=str(goal.get("goal_id")),
    )
    normalized_task_mode = str(bound_intake["task_mode"])
    normalized_artifact_mode = str(bound_intake["artifact_mode"])
    authority_policy = normalized_policy["mode_authority_policy"]
    authority_registered = (
        authority_policy["verification_backend"] == "managed-authority-registry"
        and bound_intake["authority_id"]
        in authority_policy["trusted_mode_authorities"]
    )
    mode_authority_managed = False
    if authority_registered and mode_authority_verifier is not None:
        try:
            mode_authority_managed = mode_authority_verifier(
                bound_intake, authority_policy
            ) is True
        except Exception:
            mode_authority_managed = False
    effective_artifact_mode = normalized_artifact_mode
    if not mode_authority_managed and normalized_artifact_mode == "readonly":
        effective_artifact_mode = "implementation"
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        raise ExecutionPolicyError("as_of must include timezone")
    now = now.astimezone(UTC)

    usage = state.get("usage") or {}
    progress = state.get("progress") or {}
    retry = state.get("retry") or {}
    checkpoint = state.get("checkpoint") or {}
    evidence = state.get("evidence") or {}
    artifacts = state.get("artifacts") or {}
    reasons: list[str] = []

    required_evidence = set(goal.get("required_evidence") or [])
    evidence_present = set(evidence)
    missing_evidence = sorted(required_evidence - evidence_present)
    checkpoint_missing = sorted(set(checkpoint.get("evidence_ids") or []) - evidence_present)
    configured_artifacts = normalized_policy["artifact_applicability"][effective_artifact_mode][gate_event]
    gate_applicable = configured_artifacts is not None
    required_artifacts = configured_artifacts or []
    missing_artifacts = sorted(item for item in required_artifacts if item not in artifacts)
    artifact_evidence_missing = sorted(
        item for item in required_artifacts if item in artifacts and artifacts[item] not in evidence_present
    )

    total_tokens = int(usage.get("total_tokens") or 0)
    baseline_tokens = int(goal.get("usage_baseline_tokens") or 0)
    goal_tokens = max(total_tokens - baseline_tokens, 0)
    if usage.get("observed_at") and total_tokens < baseline_tokens:
        raise ExecutionPolicyError("goal usage baseline cannot exceed current usage snapshot")
    token_budget = goal.get("token_budget")
    token_ratio = (goal_tokens / token_budget) if token_budget else None
    context_window = int(usage.get("context_window") or 0)
    last_input_tokens = int(usage.get("last_input_tokens") or 0)
    context_ratio = (last_input_tokens / context_window) if context_window else 0.0

    started_at = _timestamp(goal["started_at"], "goal.started_at") if goal.get("started_at") else None
    time_elapsed = (now - started_at).total_seconds() if started_at else 0.0
    time_budget = goal.get("time_budget_seconds")
    heartbeat_at = _timestamp(progress["heartbeat_at"], "progress.heartbeat_at") if progress.get("heartbeat_at") else None
    heartbeat_age = (now - heartbeat_at).total_seconds() if heartbeat_at else None
    if heartbeat_age is not None and heartbeat_age < 0:
        raise ExecutionPolicyError("heartbeat cannot be in the future")

    completion_valid = True
    if goal.get("status") == "completed":
        if not gate_applicable:
            reasons.append("gate-not-applicable")
        if int(goal.get("open_items_count") or 0) != 0:
            reasons.append("open-items-remain")
        if not checkpoint.get("verified"):
            reasons.append("checkpoint-not-verified")
        elif int(checkpoint.get("revision") or 0) != int(progress.get("revision") or 0):
            reasons.append("checkpoint-stale")
        if missing_evidence or checkpoint_missing:
            reasons.append("required-evidence-missing")
        if missing_artifacts or artifact_evidence_missing:
            reasons.append("required-artifact-missing")
        if int(retry.get("used") or 0) >= int(normalized_policy["progress"]["retry_limit"]):
            reasons.append("retry-budget-exhausted")
        if int(progress.get("no_progress_heartbeats") or 0) >= int(
            normalized_policy["progress"]["no_progress_limit"]
        ):
            reasons.append("no-progress-limit-reached")
        completion_valid = not reasons

    if goal.get("status") == "aborted":
        action = "blocked"
        reasons.append("goal-aborted")
    elif goal.get("status") == "completed":
        action = "pass" if completion_valid else "replan"
    elif goal.get("status") != "active":
        action = "continue"
    elif token_ratio is not None and token_ratio >= normalized_policy["token"]["stop_ratio"]:
        action = "stop"
        reasons.append("token-budget-exhausted")
    elif time_budget and time_elapsed >= time_budget:
        action = "stop"
        reasons.append("time-budget-exhausted")
    elif heartbeat_age is None or heartbeat_age > normalized_policy["progress"]["staleness_seconds"]:
        action = "replan"
        reasons.append("heartbeat-stale")
    elif int(retry.get("used") or 0) >= int(normalized_policy["progress"]["retry_limit"]):
        action = "replan"
        reasons.append("retry-budget-exhausted")
    elif int(progress.get("no_progress_heartbeats") or 0) >= int(
        normalized_policy["progress"]["no_progress_limit"]
    ):
        action = "replan"
        reasons.append("no-progress-limit-reached")
    elif context_ratio >= normalized_policy["context"]["compact_ratio"]:
        action = "compact"
        reasons.append("context-pressure")
    elif token_ratio is not None and token_ratio >= normalized_policy["token"]["compact_ratio"]:
        action = "compact"
        reasons.append("token-budget-critical")
    elif (
        token_ratio is not None
        and token_ratio >= normalized_policy["token"]["checkpoint_ratio"]
        and (
            not checkpoint.get("verified")
            or int(checkpoint.get("revision") or 0) != int(progress.get("revision") or 0)
        )
    ):
        action = "checkpoint"
        reasons.append("token-budget-warning")
    else:
        action = "continue"

    gate_allowed = gate_event == "steady" and gate_applicable
    if not gate_applicable:
        gate_allowed = False
    elif gate_event == "apply":
        gate_allowed = (
            goal.get("status") in {"active", "completed"}
            and action in {"continue", "pass"}
            and not missing_artifacts
            and not artifact_evidence_missing
        )
    elif gate_event != "steady":
        gate_allowed = goal.get("status") == "completed" and completion_valid

    if gate_event != "steady" and not gate_allowed:
        if not gate_applicable:
            reasons.append("gate-not-applicable")
        if missing_artifacts or artifact_evidence_missing:
            reasons.append("required-artifact-missing")
        if gate_event != "apply" and goal.get("status") != "completed":
            reasons.append("goal-not-completed")
        if action == "continue":
            action = "replan"
    elif gate_event != "steady" and gate_allowed:
        action = "pass"

    reasons = list(dict.fromkeys(reasons))
    completion_allowed = (
        goal.get("status") == "completed" and completion_valid and gate_applicable
    )
    status = "pass" if gate_allowed and gate_event != "steady" else (
        "pass" if completion_allowed else (
        "active" if action == "continue" else (
            "attention" if action in {"checkpoint", "compact"} else "fail"
        )
    ))
    decision = {
        "schema_version": DECISION_SCHEMA_V2,
        "status": status,
        "gate_event": gate_event,
        "recommended_action": action,
        "completion_allowed": completion_allowed,
        "advisory_only": action in {"continue", "checkpoint", "compact"},
        "evaluated_at": _iso(now),
        "thread_id": (state.get("identity") or {}).get("thread_id"),
        "goal_id": goal.get("goal_id"),
        "goal_status": goal.get("status"),
        "gate_allowed": gate_allowed,
        "goal_tokens": goal_tokens,
        "token_budget": token_budget,
        "token_ratio": round(token_ratio, 6) if token_ratio is not None else None,
        "context_ratio": round(context_ratio, 6),
        "time_elapsed_seconds": round(time_elapsed, 3),
        "heartbeat_age_seconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
        "retry_remaining": max(
            int(normalized_policy["progress"]["retry_limit"]) - int(retry.get("used") or 0), 0
        ),
        "no_progress_remaining": max(
            int(normalized_policy["progress"]["no_progress_limit"])
            - int(progress.get("no_progress_heartbeats") or 0),
            0,
        ),
        "missing_evidence": missing_evidence,
        "checkpoint_evidence_missing": checkpoint_missing,
        "missing_artifacts": missing_artifacts,
        "artifact_evidence_missing": artifact_evidence_missing,
        "reasons": reasons,
    }
    decision.update({
        "task_mode": normalized_task_mode,
        "artifact_mode": normalized_artifact_mode,
        "effective_artifact_mode": effective_artifact_mode,
        "mode_authority_id": goal.get("mode_authority_id"),
        "mode_authority_managed": mode_authority_managed,
        "intake_attestation_sha256": goal.get("intake_attestation_sha256"),
        "intake_provenance": goal.get("intake_provenance"),
        "gate_applicable": gate_applicable,
        "required_artifacts": list(required_artifacts),
    })
    return decision
