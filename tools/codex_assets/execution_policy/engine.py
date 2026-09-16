"""Deterministic event reducer and fail-closed policy engine for Runtime Control."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from .contracts import (
    ARTIFACT_TYPES,
    DECISION_SCHEMA,
    DECISION_SCHEMA_V2,
    GOAL_INTAKE_SCHEMA,
    GATE_EVENTS,
    POLICY_SCHEMA,
    POLICY_SCHEMA_V2,
    STATE_SCHEMA,
    TASK_MODES,
    RuntimeControlError,
    _identifier,
    _ids,
    _integer,
    _iso,
    _number,
    _sha256,
    _timestamp,
    _validate_event,
    _validate_goal_intake,
    validate_policy,
)


UTC = UTC
ModeAuthorityVerifier = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def goal_intake_attestation_sha256(
    task_mode: str,
    artifact_mode: str,
    provenance: Mapping[str, Any],
    *,
    goal_id: str,
    request_sha256: str,
    routing_decision_sha256: str,
    authority_id: str,
) -> str:
    """Return canonical attestation digest for an attested goal intake."""
    from .contracts import goal_intake_attestation_sha256 as _digest

    return _digest(
        task_mode,
        artifact_mode,
        provenance,
        goal_id=goal_id,
        request_sha256=request_sha256,
        routing_decision_sha256=routing_decision_sha256,
        authority_id=authority_id,
    )


def _initial_state(thread_id: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "thread_id": thread_id,
        "goal_id": "",
        "goal_generation": 0,
        "status": "idle",
        "started_at": "",
        "last_event_at": "",
        "last_progress_at": "",
        "last_heartbeat_at": "",
        "last_checkpoint_at": "",
        "goal_intake": None,
        "goal_intake_attestation_sha256": "",
        "task_mode": "",
        "artifact_mode": "",
        "mode_authority": None,
        "goal_replan_identity": "",
        "usage": {"tokens_used": 0, "token_budget": 0, "context_ratio": 0.0},
        "retry": {"total": 0, "no_progress": 0},
        "evidence_ids": [],
        "artifacts": {},
        "event_count": 0,
    }


def _require_active(state: Mapping[str, Any], event_type: str) -> None:
    if state.get("status") != "active":
        raise RuntimeControlError(f"{event_type} requires an active goal")


def _payload_fields(payload: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(payload) != expected:
        raise RuntimeControlError(f"{label} payload fields are invalid")


def _reset_goal_state(
    state: dict[str, Any],
    goal_id: str,
    observed_at: datetime,
    intake: Mapping[str, Any],
) -> None:
    state["goal_id"] = goal_id
    state["goal_generation"] += 1
    state["status"] = "active"
    state["started_at"] = _iso(observed_at)
    state["last_progress_at"] = _iso(observed_at)
    state["last_heartbeat_at"] = ""
    state["last_checkpoint_at"] = ""
    state["goal_intake"] = copy.deepcopy(dict(intake))
    state["goal_intake_attestation_sha256"] = str(intake["attestation_sha256"])
    state["task_mode"] = str(intake["task_mode"])
    state["artifact_mode"] = str(intake["artifact_mode"])
    state["mode_authority"] = None
    state["goal_replan_identity"] = ""
    state["usage"] = {"tokens_used": 0, "token_budget": 0, "context_ratio": 0.0}
    state["retry"] = {"total": 0, "no_progress": 0}
    state["evidence_ids"] = []
    state["artifacts"] = {}


def _event_goal_id(payload: Mapping[str, Any], field: str = "goal_id") -> str:
    return _identifier(payload.get(field), field)


def reduce_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Reduce append-only runtime events into one deterministic state."""
    state: dict[str, Any] | None = None
    thread_id = ""
    last_time: datetime | None = None
    fingerprints: set[str] = set()

    for raw in events:
        event = _validate_event(raw)
        if event["fingerprint"] in fingerprints:
            raise RuntimeControlError("runtime control event history contains a duplicate record")
        fingerprints.add(event["fingerprint"])
        if not thread_id:
            thread_id = event["thread_id"]
            state = _initial_state(thread_id)
        elif event["thread_id"] != thread_id:
            raise RuntimeControlError("runtime control events must belong to one thread")
        observed_at = event["observed_at"]
        if last_time is not None and observed_at < last_time:
            raise RuntimeControlError("runtime control event history must be monotonic")
        last_time = observed_at
        assert state is not None
        payload = event["payload"]
        event_type = event["event_type"]

        if event_type == "goal.started":
            _payload_fields(payload, {"goal_id", "intake"}, event_type)
            goal_id = _event_goal_id(payload)
            intake = _validate_goal_intake(
                payload.get("intake"),
                event_at=observed_at,
                expected_kind="goal-start",
                expected_goal_id=goal_id,
            )
            if state["status"] == "active":
                raise RuntimeControlError("goal.started cannot replace an active goal")
            _reset_goal_state(state, goal_id, observed_at, intake)
        elif event_type == "goal.updated":
            _payload_fields(payload, {"goal_id", "supersedes_goal_id", "intake"}, event_type)
            supersedes = _event_goal_id(payload, "supersedes_goal_id")
            if not state["goal_id"] or supersedes != state["goal_id"]:
                raise RuntimeControlError("goal.updated must supersede the current goal")
            goal_id = _event_goal_id(payload)
            if goal_id == supersedes:
                raise RuntimeControlError("goal.updated requires a new goal_id")
            intake = _validate_goal_intake(
                payload.get("intake"),
                event_at=observed_at,
                expected_kind="goal-update",
                expected_goal_id=goal_id,
            )
            replan_payload = {
                "supersedes_goal_id": supersedes,
                "goal_id": goal_id,
                "intake_attestation_sha256": intake["attestation_sha256"],
            }
            _reset_goal_state(state, goal_id, observed_at, intake)
            state["goal_replan_identity"] = hashlib.sha256(
                json.dumps(
                    replan_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        elif event_type == "goal.completed":
            _payload_fields(payload, {"goal_id"}, event_type)
            _require_active(state, event_type)
            if _event_goal_id(payload) != state["goal_id"]:
                raise RuntimeControlError("goal.completed goal_id mismatch")
            state["status"] = "completed"
        elif event_type == "goal.aborted":
            _payload_fields(payload, {"goal_id", "reason_id"}, event_type)
            _require_active(state, event_type)
            if _event_goal_id(payload) != state["goal_id"]:
                raise RuntimeControlError("goal.aborted goal_id mismatch")
            _identifier(payload.get("reason_id"), "reason_id")
            state["status"] = "aborted"
        elif event_type == "usage.snapshot":
            _payload_fields(payload, {"tokens_used", "token_budget", "context_ratio"}, event_type)
            _require_active(state, event_type)
            tokens_used = _integer(payload.get("tokens_used"), "tokens_used")
            token_budget = _integer(payload.get("token_budget"), "token_budget", positive=True)
            context_ratio = _number(payload.get("context_ratio"), "context_ratio")
            if context_ratio < 0:
                raise RuntimeControlError("context_ratio must be non-negative")
            state["usage"] = {
                "tokens_used": tokens_used,
                "token_budget": token_budget,
                "context_ratio": context_ratio,
            }
        elif event_type == "progress.advanced":
            _payload_fields(payload, {"progress_id"}, event_type)
            _require_active(state, event_type)
            _identifier(payload.get("progress_id"), "progress_id")
            state["last_progress_at"] = _iso(observed_at)
            state["retry"]["no_progress"] = 0
        elif event_type == "heartbeat.recorded":
            _payload_fields(payload, set(), event_type)
            _require_active(state, event_type)
            state["last_heartbeat_at"] = _iso(observed_at)
        elif event_type == "checkpoint.verified":
            _payload_fields(payload, {"checkpoint_id"}, event_type)
            _require_active(state, event_type)
            _identifier(payload.get("checkpoint_id"), "checkpoint_id")
            state["last_checkpoint_at"] = _iso(observed_at)
        elif event_type == "retry.recorded":
            _payload_fields(payload, {"retry_id", "progress_made"}, event_type)
            _require_active(state, event_type)
            _identifier(payload.get("retry_id"), "retry_id")
            progress_made = payload.get("progress_made")
            if not isinstance(progress_made, bool):
                raise RuntimeControlError("progress_made must be boolean")
            state["retry"]["total"] += 1
            if progress_made:
                state["retry"]["no_progress"] = 0
                state["last_progress_at"] = _iso(observed_at)
            else:
                state["retry"]["no_progress"] += 1
        elif event_type == "evidence.added":
            _payload_fields(payload, {"evidence_id"}, event_type)
            _require_active(state, event_type)
            evidence_id = _identifier(payload.get("evidence_id"), "evidence_id")
            if evidence_id not in state["evidence_ids"]:
                state["evidence_ids"].append(evidence_id)
        elif event_type == "artifact.verified":
            _payload_fields(payload, {"artifact_type", "artifact_id"}, event_type)
            _require_active(state, event_type)
            artifact_type = payload.get("artifact_type")
            if artifact_type not in ARTIFACT_TYPES:
                raise RuntimeControlError("unknown artifact_type")
            artifact_id = _identifier(payload.get("artifact_id"), "artifact_id")
            current = state["artifacts"].get(artifact_type)
            if current is not None and current != artifact_id:
                raise RuntimeControlError("artifact type already verified with a different identity")
            state["artifacts"][artifact_type] = artifact_id

        state["last_event_at"] = _iso(observed_at)
        state["event_count"] += 1

    if state is None:
        raise RuntimeControlError("runtime control event history is empty")
    state["evidence_ids"] = sorted(state["evidence_ids"])
    state["artifacts"] = dict(sorted(state["artifacts"].items()))
    return state


def _missing_artifacts(state: Mapping[str, Any], required: Iterable[str]) -> list[str]:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, dict):
        raise RuntimeControlError("state artifacts are invalid")
    return sorted(item for item in required if item not in artifacts)


def _effective_artifact_mode(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    verifier: ModeAuthorityVerifier | None,
) -> tuple[str, dict[str, Any] | None, list[str]]:
    mode = state.get("artifact_mode")
    if mode not in TASK_MODES:
        raise RuntimeControlError("state artifact_mode is invalid")
    authority_policy = policy.get("mode_authority_policy")
    if not isinstance(authority_policy, dict):
        raise RuntimeControlError("mode authority policy is missing")
    trusted = authority_policy.get("trusted_mode_authorities")
    backend = authority_policy.get("verification_backend")
    managed = authority_policy.get("managed")
    if managed is not True or not isinstance(trusted, list) or not isinstance(backend, str):
        raise RuntimeControlError("mode authority policy is invalid")
    if mode != "readonly":
        return str(mode), None, []
    intake = state.get("goal_intake")
    if not isinstance(intake, dict):
        raise RuntimeControlError("readonly state is missing attested goal intake")
    authority_id = intake.get("authority_id")
    if authority_id not in trusted:
        return "implementation", None, ["mode-authority-untrusted-fallback"]
    if backend != "managed-authority-registry" or verifier is None:
        return "implementation", None, ["mode-authority-verifier-unavailable-fallback"]
    try:
        result = dict(verifier(intake))
    except Exception as exc:
        raise RuntimeControlError("mode authority verification failed closed") from exc
    if set(result) != {"verified", "authority_id", "attestation_sha256"}:
        raise RuntimeControlError("mode authority verifier result is invalid")
    if result.get("verified") is not True:
        return "implementation", result, ["mode-authority-verification-fallback"]
    if result.get("authority_id") != authority_id:
        raise RuntimeControlError("mode authority verifier returned a different authority")
    if result.get("attestation_sha256") != state.get("goal_intake_attestation_sha256"):
        raise RuntimeControlError("mode authority verifier attestation mismatch")
    return "readonly", result, []


def evaluate(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    now: datetime | None = None,
    gate_event: str = "steady",
    mode_authority_verifier: ModeAuthorityVerifier | None = None,
) -> dict[str, Any]:
    """Evaluate one reduced state against policy and return a fail-closed decision."""
    normalized_policy = validate_policy(policy)
    if state.get("schema_version") != STATE_SCHEMA:
        raise RuntimeControlError("unsupported runtime control state schema")
    if gate_event not in GATE_EVENTS:
        raise RuntimeControlError("unsupported gate_event")
    thread_id = _identifier(state.get("thread_id"), "thread_id")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    policy_schema = normalized_policy["schema_version"]
    decision_schema = DECISION_SCHEMA if policy_schema == POLICY_SCHEMA else DECISION_SCHEMA_V2
    effective_artifact_mode = "legacy-v1"
    mode_authority_evidence: dict[str, Any] | None = None
    gate_applicable = True
    action = "continue"
    reasons: list[str] = []
    missing: list[str] = []

    if state.get("status") == "active":
        usage = state.get("usage")
        if not isinstance(usage, dict):
            raise RuntimeControlError("state usage is invalid")
        tokens_used = _integer(usage.get("tokens_used"), "tokens_used")
        token_budget = _integer(usage.get("token_budget"), "token_budget")
        context_ratio = _number(usage.get("context_ratio"), "context_ratio")
        token_ratio = (tokens_used / token_budget) if token_budget else 0.0
        token_policy = normalized_policy["token"]
        context_policy = normalized_policy["context"]
        progress_policy = normalized_policy["progress"]

        if token_budget and token_ratio >= token_policy["stop_ratio"]:
            action = "stop"
            reasons.append("token-stop-threshold")
        elif token_budget and token_ratio >= token_policy["compact_ratio"]:
            action = "compact"
            reasons.append("token-compact-threshold")
        elif token_budget and token_ratio >= token_policy["checkpoint_ratio"]:
            action = "checkpoint"
            reasons.append("token-checkpoint-threshold")
        elif context_ratio >= context_policy["compact_ratio"]:
            action = "compact"
            reasons.append("context-compact-threshold")

        last_progress = _timestamp(state.get("last_progress_at"), "last_progress_at")
        staleness = max(0, int((timestamp - last_progress).total_seconds()))
        retry = state.get("retry")
        if not isinstance(retry, dict):
            raise RuntimeControlError("state retry is invalid")
        total_retry = _integer(retry.get("total"), "retry.total")
        no_progress = _integer(retry.get("no_progress"), "retry.no_progress")
        if total_retry >= progress_policy["retry_limit"] and no_progress:
            action = "stop"
            reasons.append("retry-limit")
        if no_progress >= progress_policy["no_progress_limit"]:
            action = "stop"
            reasons.append("no-progress-limit")
        if staleness >= progress_policy["staleness_seconds"]:
            action = "stop"
            reasons.append("progress-stale")
    else:
        staleness = 0

    if policy_schema == POLICY_SCHEMA:
        required = normalized_policy["gate_policy"][gate_event]
    else:
        effective_artifact_mode, mode_authority_evidence, authority_reasons = _effective_artifact_mode(
            state, normalized_policy, mode_authority_verifier
        )
        reasons.extend(authority_reasons)
        required = normalized_policy["artifact_applicability"][effective_artifact_mode][gate_event]
        gate_applicable = required is not None
        if required is None:
            required = []
    missing = _missing_artifacts(state, required)
    if missing and action != "stop":
        action = "blocked"
        reasons.append("missing-artifact")
    if not gate_applicable and action != "stop":
        action = "blocked"
        reasons.append("gate-not-applicable")

    reason_list = sorted(set(reasons)) or ["within-policy"]
    decision: dict[str, Any] = {
        "schema_version": decision_schema,
        "thread_id": thread_id,
        "goal_id": state.get("goal_id", ""),
        "goal_generation": _integer(state.get("goal_generation"), "goal_generation"),
        "evaluated_at": _iso(timestamp),
        "gate_event": gate_event,
        "action": action,
        "reasons": reason_list,
        "missing_artifacts": missing,
        "progress_staleness_seconds": staleness,
    }
    if policy_schema == POLICY_SCHEMA_V2:
        decision.update({
            "goal_intake_attestation_sha256": _sha256(
                state.get("goal_intake_attestation_sha256"),
                "goal_intake_attestation_sha256",
            ),
            "task_mode": state.get("task_mode"),
            "artifact_mode": state.get("artifact_mode"),
            "effective_artifact_mode": effective_artifact_mode,
            "gate_applicable": gate_applicable,
            "mode_authority_evidence": mode_authority_evidence,
            "goal_replan_identity": state.get("goal_replan_identity", ""),
        })
    return decision
