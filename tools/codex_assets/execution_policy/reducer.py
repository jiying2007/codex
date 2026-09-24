"""Deterministic event reduction for ADK execution-policy state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from .contracts import (
    ARTIFACT_TYPES,
    STATE_SCHEMA,
    ExecutionPolicyError,
    _identifier,
    _ids,
    _integer,
    _iso,
    _number,
    _sha256,
    _validate_event,
    _validate_goal_intake,
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
