"""Canonical event reducer and decision engine for ADK execution policy."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from .contracts import (
    ARTIFACT_TYPES,
    GATE_EVENTS,
    GOAL_INTAKE_SCHEMA,
    _identifier,
    _ids,
    _integer,
    _iso,
    _number,
    _sha256,
    _timestamp,
    _validate_event,
    _validate_goal_intake,
)
from .contracts import (
    DECISION_SCHEMA_V2 as DECISION_SCHEMA_V2,
)
from .contracts import (
    EVENT_SCHEMA as EVENT_SCHEMA,
)
from .contracts import (
    POLICY_SCHEMA_V2 as POLICY_SCHEMA_V2,
)
from .contracts import (
    STATE_SCHEMA as STATE_SCHEMA,
)
from .contracts import (
    ExecutionPolicyError as ExecutionPolicyError,
)
from .contracts import (
    goal_intake_attestation_sha256 as goal_intake_attestation_sha256,
)
from .contracts import (
    validate_policy as validate_policy,
)


def _initial_state(thread_id: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "identity": {"thread_id": thread_id, "cwd_hash": None, "model": None},
        "goal": {
            "goal_id": None,
            "status": "idle",
            "started_at": None,
            "completed_at": None,
            "token_budget": None,
            "time_budget_seconds": None,
            "usage_baseline_tokens": 0,
            "success_criteria": [],
            "required_evidence": [],
            "open_items_count": 0,
            "task_mode": None,
            "artifact_mode": None,
            "request_sha256": None,
            "routing_decision_sha256": None,
            "mode_authority_id": None,
            "intake_attestation_sha256": None,
            "intake_provenance": None,
            "intake_revision": 0,
        },
        "usage": {
            "observed_at": None,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "total_tokens": 0,
            "context_window": 0,
            "last_input_tokens": 0,
            "last_delta_tokens": 0,
            "rate_per_minute": 0.0,
        },
        "progress": {
            "revision": 0,
            "last_progress_at": None,
            "heartbeat_at": None,
            "last_heartbeat_revision": -1,
            "no_progress_heartbeats": 0,
        },
        "retry": {"used": 0},
        "checkpoint": {"revision": 0, "verified": False, "evidence_ids": []},
        "evidence": {},
        "artifacts": {},
        "events_applied": 0,
        "last_event_at": None,
    }


def _reset_goal_state(state: dict[str, Any], payload: Mapping[str, Any], at: datetime) -> None:
    base_required = {
        "goal_id", "token_budget", "time_budget_seconds", "usage_baseline_tokens",
        "success_criteria", "required_evidence", "open_items_count",
    }
    payload_fields = frozenset(payload)
    if payload_fields not in {frozenset(base_required), frozenset(base_required | {"intake"})}:
        raise ExecutionPolicyError("goal.started payload fields are invalid")
    goal_id = _identifier(payload.get("goal_id"), "goal.goal_id")
    intake = None
    if "intake" in payload:
        intake = _validate_goal_intake(
            payload.get("intake"), event_at=at, expected_kind="routing-decision",
            expected_goal_id=goal_id,
        )
    state["goal"] = {
        "goal_id": goal_id,
        "status": "active",
        "started_at": _iso(at),
        "completed_at": None,
        "token_budget": _integer(payload.get("token_budget"), "goal.token_budget", positive=True),
        "time_budget_seconds": _integer(
            payload.get("time_budget_seconds"), "goal.time_budget_seconds", positive=True
        ),
        "usage_baseline_tokens": _integer(
            payload.get("usage_baseline_tokens"), "goal.usage_baseline_tokens"
        ),
        "success_criteria": _ids(payload.get("success_criteria"), "goal.success_criteria", non_empty=True),
        "required_evidence": _ids(
            payload.get("required_evidence"), "goal.required_evidence", non_empty=True
        ),
        "open_items_count": _integer(payload.get("open_items_count"), "goal.open_items_count"),
        "task_mode": intake["task_mode"] if intake else None,
        "artifact_mode": intake["artifact_mode"] if intake else None,
        "request_sha256": intake["request_sha256"] if intake else None,
        "routing_decision_sha256": intake["routing_decision_sha256"] if intake else None,
        "mode_authority_id": intake["authority_id"] if intake else None,
        "intake_attestation_sha256": intake["attestation_sha256"] if intake else None,
        "intake_provenance": intake["provenance"] if intake else None,
        "intake_revision": 1 if intake else 0,
    }
    state["progress"] = {
        "revision": 0,
        "last_progress_at": _iso(at),
        "heartbeat_at": _iso(at),
        "last_heartbeat_revision": -1,
        "no_progress_heartbeats": 0,
    }
    state["retry"] = {"used": 0}
    state["checkpoint"] = {"revision": 0, "verified": False, "evidence_ids": []}
    state["evidence"] = {}
    state["artifacts"] = {}


def reduce_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] | None = None
    seen: dict[str, str] = {}
    last_at: datetime | None = None

    for raw in events:
        event = _validate_event(raw)
        event_id = event["event_id"]
        if event_id in seen:
            if seen[event_id] != event["fingerprint"]:
                raise ExecutionPolicyError("duplicate event_id has a different payload")
            continue
        seen[event_id] = event["fingerprint"]
        at = event["observed_at"]
        if last_at is not None and at < last_at:
            raise ExecutionPolicyError("runtime control events must be time ordered")
        last_at = at

        if state is None:
            state = _initial_state(event["thread_id"])
        if event["thread_id"] != state["identity"]["thread_id"]:
            raise ExecutionPolicyError("one state cannot mix thread_id values")

        kind = event["event_type"]
        payload = event["payload"]
        goal = state["goal"]

        if kind == "goal.started":
            if goal["status"] == "active":
                raise ExecutionPolicyError("cannot start a second active goal")
            _reset_goal_state(state, payload, at)
        elif kind == "goal.updated":
            allowed = {
                "open_items_count", "token_budget", "time_budget_seconds",
                "intake", "mode_change_reason",
            }
            if goal["status"] != "active" or not payload or not set(payload) <= allowed:
                raise ExecutionPolicyError("goal.updated requires one active goal and canonical budget fields")
            has_intake = "intake" in payload
            has_reason = "mode_change_reason" in payload
            if has_intake != has_reason:
                raise ExecutionPolicyError(
                    "goal.updated mode changes require intake and mode_change_reason"
                )
            if has_intake:
                if payload.get("mode_change_reason") != "replan":
                    raise ExecutionPolicyError("goal mode may change only through an explicit replan")
                intake = _validate_goal_intake(
                    payload.get("intake"), event_at=at, expected_kind="goal-replan",
                    expected_goal_id=str(goal["goal_id"]),
                )
                if intake["attestation_sha256"] == goal.get("intake_attestation_sha256"):
                    raise ExecutionPolicyError("goal replan must carry a new intake attestation")
                goal["task_mode"] = intake["task_mode"]
                goal["artifact_mode"] = intake["artifact_mode"]
                goal["request_sha256"] = intake["request_sha256"]
                goal["routing_decision_sha256"] = intake["routing_decision_sha256"]
                goal["mode_authority_id"] = intake["authority_id"]
                goal["intake_attestation_sha256"] = intake["attestation_sha256"]
                goal["intake_provenance"] = intake["provenance"]
                goal["intake_revision"] = int(goal.get("intake_revision") or 0) + 1
            if "open_items_count" in payload:
                goal["open_items_count"] = _integer(
                    payload.get("open_items_count"), "goal.open_items_count"
                )
            if "token_budget" in payload:
                goal["token_budget"] = _integer(payload.get("token_budget"), "goal.token_budget", positive=True)
            if "time_budget_seconds" in payload:
                goal["time_budget_seconds"] = _integer(
                    payload.get("time_budget_seconds"), "goal.time_budget_seconds", positive=True
                )
        elif kind == "goal.completed":
            if goal["status"] != "active" or payload:
                raise ExecutionPolicyError("goal.completed requires one active goal and empty payload")
            goal["status"] = "completed"
            goal["completed_at"] = _iso(at)
            state["progress"]["last_progress_at"] = _iso(at)
            state["progress"]["heartbeat_at"] = _iso(at)
        elif kind == "goal.aborted":
            if goal["status"] != "active" or payload:
                raise ExecutionPolicyError("goal.aborted requires one active goal and empty payload")
            goal["status"] = "aborted"
            goal["completed_at"] = _iso(at)
        elif kind == "usage.snapshot":
            required = {
                "cwd_hash", "model", "input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "total_tokens", "context_window", "last_input_tokens",
                "last_delta_tokens", "rate_per_minute",
            }
            if set(payload) != required:
                raise ExecutionPolicyError("usage.snapshot payload fields are invalid")
            total = _integer(payload.get("total_tokens"), "usage.total_tokens")
            previous = int(state["usage"]["total_tokens"])
            if total < previous:
                raise ExecutionPolicyError("usage snapshot must be monotonic")
            input_tokens = _integer(payload.get("input_tokens"), "usage.input_tokens")
            cached = _integer(payload.get("cached_input_tokens"), "usage.cached_input_tokens")
            if cached > input_tokens:
                raise ExecutionPolicyError("cached_input_tokens must not exceed input_tokens")
            output_tokens = _integer(payload.get("output_tokens"), "usage.output_tokens")
            reasoning_tokens = _integer(payload.get("reasoning_tokens"), "usage.reasoning_tokens")
            if reasoning_tokens > output_tokens:
                raise ExecutionPolicyError("reasoning_tokens must not exceed output_tokens")
            if total != input_tokens + output_tokens:
                raise ExecutionPolicyError("total_tokens must equal input_tokens + output_tokens")
            context_window = _integer(payload.get("context_window"), "usage.context_window", positive=True)
            last_input_tokens = _integer(payload.get("last_input_tokens"), "usage.last_input_tokens")
            if last_input_tokens > context_window:
                raise ExecutionPolicyError("last_input_tokens must not exceed context_window")
            for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
                if int(payload.get(field) or 0) < int(state["usage"].get(field) or 0):
                    raise ExecutionPolicyError("usage snapshot cumulative fields must be monotonic")
            state["identity"]["cwd_hash"] = _sha256(payload.get("cwd_hash"), "usage.cwd_hash")
            state["identity"]["model"] = _identifier(payload.get("model"), "usage.model")
            state["usage"] = {
                "observed_at": _iso(at),
                "input_tokens": input_tokens,
                "cached_input_tokens": cached,
                "output_tokens": output_tokens,
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": total,
                "context_window": context_window,
                "last_input_tokens": last_input_tokens,
                "last_delta_tokens": _integer(payload.get("last_delta_tokens"), "usage.last_delta_tokens"),
                "rate_per_minute": max(0.0, _number(payload.get("rate_per_minute"), "usage.rate_per_minute")),
            }
        elif kind == "progress.advanced":
            if goal["status"] != "active" or set(payload) != {"revision"}:
                raise ExecutionPolicyError("progress.advanced requires active goal and revision")
            revision = _integer(payload.get("revision"), "progress.revision", positive=True)
            if revision <= state["progress"]["revision"]:
                raise ExecutionPolicyError("progress revision must increase")
            state["progress"]["revision"] = revision
            state["progress"]["last_progress_at"] = _iso(at)
        elif kind == "heartbeat.recorded":
            if goal["status"] != "active" or payload:
                raise ExecutionPolicyError("heartbeat.recorded requires active goal and empty payload")
            progress = state["progress"]
            if progress["last_heartbeat_revision"] == progress["revision"]:
                progress["no_progress_heartbeats"] += 1
            else:
                progress["no_progress_heartbeats"] = 0
            progress["last_heartbeat_revision"] = progress["revision"]
            progress["heartbeat_at"] = _iso(at)
        elif kind == "retry.recorded":
            if goal["status"] != "active" or set(payload) != {"reason_id"}:
                raise ExecutionPolicyError("retry.recorded requires active goal and reason_id")
            _identifier(payload.get("reason_id"), "retry.reason_id")
            state["retry"]["used"] += 1
        elif kind == "evidence.added":
            if goal["status"] not in {"active", "completed"} or set(payload) != {"evidence_id", "sha256"}:
                raise ExecutionPolicyError("evidence.added payload fields are invalid")
            evidence_id = _identifier(payload.get("evidence_id"), "evidence.evidence_id")
            digest = _sha256(payload.get("sha256"), "evidence.sha256")
            existing = state["evidence"].get(evidence_id)
            if existing is not None and existing != digest:
                raise ExecutionPolicyError("evidence_id cannot change digest")
            state["evidence"][evidence_id] = digest
        elif kind == "checkpoint.verified":
            required = {"revision", "evidence_ids"}
            if goal["status"] not in {"active", "completed"} or set(payload) != required:
                raise ExecutionPolicyError("checkpoint.verified payload fields are invalid")
            revision = _integer(payload.get("revision"), "checkpoint.revision")
            if revision > state["progress"]["revision"]:
                raise ExecutionPolicyError("checkpoint revision cannot exceed progress revision")
            evidence_ids = _ids(payload.get("evidence_ids"), "checkpoint.evidence_ids", non_empty=True)
            state["checkpoint"] = {"revision": revision, "verified": True, "evidence_ids": evidence_ids}
        elif kind == "artifact.verified":
            if set(payload) != {"artifact_type", "evidence_id"}:
                raise ExecutionPolicyError("artifact.verified payload fields are invalid")
            artifact_type = payload.get("artifact_type")
            if artifact_type not in ARTIFACT_TYPES:
                raise ExecutionPolicyError("unknown artifact_type")
            evidence_id = _identifier(payload.get("evidence_id"), "artifact.evidence_id")
            state["artifacts"][artifact_type] = evidence_id
        else:  # pragma: no cover
            raise ExecutionPolicyError("unhandled runtime control event")

        state["events_applied"] += 1
        state["last_event_at"] = _iso(at)

    if state is None:
        raise ExecutionPolicyError("runtime control requires at least one event")
    return state


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
