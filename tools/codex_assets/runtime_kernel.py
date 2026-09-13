"""Stdlib-only Codex Runtime Control v1 kernel.

Behavior is aligned to the v1 reducer/decision semantics published by
agent-dev-kit 5.1.0, while runtime ownership stays inside Codex.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional


EVENT_SCHEMA = "runtime_control.event/v1"
STATE_SCHEMA = "runtime_control.state/v1"
DECISION_SCHEMA = "runtime_control.decision/v1"
POLICY_SCHEMA = "runtime_control.policy/v1"
UTC = timezone.utc

EVENT_TYPES = {
    "goal.started",
    "goal.updated",
    "goal.completed",
    "goal.aborted",
    "usage.snapshot",
    "progress.advanced",
    "heartbeat.recorded",
    "checkpoint.verified",
    "retry.recorded",
    "evidence.added",
    "artifact.verified",
}
ARTIFACT_TYPES = {"repo", "build", "plan", "dry-run", "live", "review"}
GATE_EVENTS = {"steady", "final", "commit", "apply", "release"}
SENSITIVE_FIELDS = {
    "prompt", "prompts", "raw_prompt", "system_prompt", "message", "messages",
    "raw_message", "input_message", "input_messages", "output_message", "output_messages",
    "password", "passwords", "credential", "credentials", "secret", "secrets", "api_key",
    "access_token", "private_key", "raw_log", "tool_payload", "tool_arguments", "tool_result",
    "tool_results", "content", "text", "raw_input", "raw_output", "objective",
}
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bghp_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}=*\b", re.IGNORECASE),
    re.compile(r"\b(?:password|secret|credential|api[_ -]?key)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:raw[ _.-]?prompt|raw[ _.-]?message|tool[ _.-]?payload)\b", re.IGNORECASE),
)
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeControlError(ValueError):
    """Raised when policy, event history or state violates the v1 contract."""


def _reject_sensitive(value: Any, path: str = "runtime control input") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace(".", "_").replace("-", "_")
            if normalized in SENSITIVE_FIELDS:
                raise RuntimeControlError(f"{path} contains forbidden sensitive field: {key}")
            _reject_sensitive(child, f"{path}/{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive(child, f"{path}/{index}")
        return
    if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS):
        raise RuntimeControlError(f"{path} contains secret-like content")


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise RuntimeControlError(f"{field} must be a bounded stable identifier")
    _reject_sensitive(value, field)
    return value


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        label = "positive" if positive else "non-negative"
        raise RuntimeControlError(f"{field} must be a {label} integer")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeControlError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeControlError(f"{field} must be finite")
    return result


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise RuntimeControlError(f"{field} must be an RFC3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise RuntimeControlError(f"{field} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise RuntimeControlError(f"{field} must include a timezone")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _ids(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise RuntimeControlError(f"{field} must be a list")
    result = [_identifier(item, field) for item in value]
    if len(result) != len(set(result)):
        raise RuntimeControlError(f"{field} must not contain duplicates")
    if non_empty and not result:
        raise RuntimeControlError(f"{field} must not be empty")
    return result


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise RuntimeControlError(f"{field} must be a SHA-256 digest")
    return value


def _fingerprint(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_policy(value: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != POLICY_SCHEMA:
        raise RuntimeControlError("unsupported runtime control policy schema")
    _reject_sensitive(value)
    if set(value) != {"schema_version", "token", "context", "progress", "gate_policy", "retention"}:
        raise RuntimeControlError("runtime control policy fields are invalid")

    token = value.get("token")
    if not isinstance(token, dict) or set(token) != {"checkpoint_ratio", "compact_ratio", "stop_ratio"}:
        raise RuntimeControlError("token policy fields are invalid")
    checkpoint_ratio = _number(token.get("checkpoint_ratio"), "token.checkpoint_ratio")
    compact_ratio = _number(token.get("compact_ratio"), "token.compact_ratio")
    stop_ratio = _number(token.get("stop_ratio"), "token.stop_ratio")
    if not 0 < checkpoint_ratio < compact_ratio < stop_ratio:
        raise RuntimeControlError("token ratios must satisfy checkpoint < compact < stop")

    context = value.get("context")
    if not isinstance(context, dict) or set(context) != {"compact_ratio"}:
        raise RuntimeControlError("context policy fields are invalid")
    context_ratio = _number(context.get("compact_ratio"), "context.compact_ratio")
    if not 0 < context_ratio <= 1:
        raise RuntimeControlError("context.compact_ratio must be in (0, 1]")

    progress = value.get("progress")
    if not isinstance(progress, dict) or set(progress) != {"staleness_seconds", "retry_limit", "no_progress_limit"}:
        raise RuntimeControlError("progress policy fields are invalid")
    _integer(progress.get("staleness_seconds"), "progress.staleness_seconds", positive=True)
    _integer(progress.get("retry_limit"), "progress.retry_limit", positive=True)
    _integer(progress.get("no_progress_limit"), "progress.no_progress_limit", positive=True)

    gate_policy = value.get("gate_policy")
    if not isinstance(gate_policy, dict) or set(gate_policy) != GATE_EVENTS:
        raise RuntimeControlError("gate_policy must define every canonical gate event")
    normalized_gates: Dict[str, list[str]] = {}
    for gate, required in gate_policy.items():
        items = _ids(required, "gate_policy." + gate)
        if set(items) - ARTIFACT_TYPES:
            raise RuntimeControlError("gate_policy references unknown artifact types")
        normalized_gates[gate] = items

    retention = value.get("retention")
    if not isinstance(retention, dict) or set(retention) != {"journal_days", "raw_content_stored"}:
        raise RuntimeControlError("retention policy fields are invalid")
    _integer(retention.get("journal_days"), "retention.journal_days", positive=True)
    if retention.get("raw_content_stored") is not False:
        raise RuntimeControlError("runtime control must not store raw content")

    return {
        "schema_version": POLICY_SCHEMA,
        "token": {
            "checkpoint_ratio": checkpoint_ratio,
            "compact_ratio": compact_ratio,
            "stop_ratio": stop_ratio,
        },
        "context": {"compact_ratio": context_ratio},
        "progress": dict(progress),
        "gate_policy": normalized_gates,
        "retention": dict(retention),
    }


def _validate_event(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeControlError("runtime control event must be an object")
    _reject_sensitive(value)
    required = {"schema_version", "event_id", "event_type", "thread_id", "observed_at", "payload"}
    if set(value) != required:
        raise RuntimeControlError("runtime control event fields are invalid")
    if value.get("schema_version") != EVENT_SCHEMA:
        raise RuntimeControlError("unsupported runtime control event schema")
    event_type = value.get("event_type")
    if event_type not in EVENT_TYPES:
        raise RuntimeControlError("unsupported runtime control event_type")
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeControlError("event payload must be an object")
    return {
        "schema_version": EVENT_SCHEMA,
        "event_id": _identifier(value.get("event_id"), "event_id"),
        "event_type": event_type,
        "thread_id": _identifier(value.get("thread_id"), "thread_id"),
        "observed_at": _timestamp(value.get("observed_at"), "observed_at"),
        "payload": dict(payload),
        "fingerprint": _fingerprint(value),
    }


def _initial_state(thread_id: str) -> Dict[str, Any]:
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


def _reset_goal_state(state: Dict[str, Any], payload: Mapping[str, Any], at: datetime) -> None:
    required = {
        "goal_id", "token_budget", "time_budget_seconds", "usage_baseline_tokens",
        "success_criteria", "required_evidence", "open_items_count",
    }
    if set(payload) != required:
        raise RuntimeControlError("goal.started payload fields are invalid")
    state["goal"] = {
        "goal_id": _identifier(payload.get("goal_id"), "goal.goal_id"),
        "status": "active",
        "started_at": _iso(at),
        "completed_at": None,
        "token_budget": _integer(payload.get("token_budget"), "goal.token_budget", positive=True),
        "time_budget_seconds": _integer(payload.get("time_budget_seconds"), "goal.time_budget_seconds", positive=True),
        "usage_baseline_tokens": _integer(payload.get("usage_baseline_tokens"), "goal.usage_baseline_tokens"),
        "success_criteria": _ids(payload.get("success_criteria"), "goal.success_criteria", non_empty=True),
        "required_evidence": _ids(payload.get("required_evidence"), "goal.required_evidence", non_empty=True),
        "open_items_count": _integer(payload.get("open_items_count"), "goal.open_items_count"),
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


def reduce_events(events: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    state: Optional[Dict[str, Any]] = None
    seen: Dict[str, str] = {}
    last_at: Optional[datetime] = None
    for raw in events:
        event = _validate_event(raw)
        event_id = event["event_id"]
        if event_id in seen:
            if seen[event_id] != event["fingerprint"]:
                raise RuntimeControlError("duplicate event_id has a different payload")
            continue
        seen[event_id] = event["fingerprint"]
        at = event["observed_at"]
        if last_at is not None and at < last_at:
            raise RuntimeControlError("runtime control events must be time ordered")
        last_at = at
        if state is None:
            state = _initial_state(event["thread_id"])
        if event["thread_id"] != state["identity"]["thread_id"]:
            raise RuntimeControlError("one state cannot mix thread_id values")

        kind = event["event_type"]
        payload = event["payload"]
        goal = state["goal"]
        if kind == "goal.started":
            if goal["status"] == "active":
                raise RuntimeControlError("cannot start a second active goal")
            _reset_goal_state(state, payload, at)
        elif kind == "goal.updated":
            allowed = {"open_items_count", "token_budget", "time_budget_seconds"}
            if goal["status"] != "active" or not payload or not set(payload) <= allowed:
                raise RuntimeControlError("goal.updated requires one active goal and canonical budget fields")
            if "open_items_count" in payload:
                goal["open_items_count"] = _integer(payload.get("open_items_count"), "goal.open_items_count")
            if "token_budget" in payload:
                goal["token_budget"] = _integer(payload.get("token_budget"), "goal.token_budget", positive=True)
            if "time_budget_seconds" in payload:
                goal["time_budget_seconds"] = _integer(
                    payload.get("time_budget_seconds"), "goal.time_budget_seconds", positive=True
                )
        elif kind == "goal.completed":
            if goal["status"] != "active" or payload:
                raise RuntimeControlError("goal.completed requires one active goal and empty payload")
            goal["status"] = "completed"
            goal["completed_at"] = _iso(at)
            state["progress"]["last_progress_at"] = _iso(at)
            state["progress"]["heartbeat_at"] = _iso(at)
        elif kind == "goal.aborted":
            if goal["status"] != "active" or payload:
                raise RuntimeControlError("goal.aborted requires one active goal and empty payload")
            goal["status"] = "aborted"
            goal["completed_at"] = _iso(at)
        elif kind == "usage.snapshot":
            required = {
                "cwd_hash", "model", "input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "total_tokens", "context_window", "last_input_tokens",
                "last_delta_tokens", "rate_per_minute",
            }
            if set(payload) != required:
                raise RuntimeControlError("usage.snapshot payload fields are invalid")
            total = _integer(payload.get("total_tokens"), "usage.total_tokens")
            if total < int(state["usage"]["total_tokens"]):
                raise RuntimeControlError("usage snapshot must be monotonic")
            input_tokens = _integer(payload.get("input_tokens"), "usage.input_tokens")
            cached = _integer(payload.get("cached_input_tokens"), "usage.cached_input_tokens")
            output_tokens = _integer(payload.get("output_tokens"), "usage.output_tokens")
            reasoning_tokens = _integer(payload.get("reasoning_tokens"), "usage.reasoning_tokens")
            if cached > input_tokens:
                raise RuntimeControlError("cached_input_tokens must not exceed input_tokens")
            if reasoning_tokens > output_tokens:
                raise RuntimeControlError("reasoning_tokens must not exceed output_tokens")
            if total != input_tokens + output_tokens:
                raise RuntimeControlError("total_tokens must equal input_tokens + output_tokens")
            context_window = _integer(payload.get("context_window"), "usage.context_window", positive=True)
            last_input_tokens = _integer(payload.get("last_input_tokens"), "usage.last_input_tokens")
            if last_input_tokens > context_window:
                raise RuntimeControlError("last_input_tokens must not exceed context_window")
            for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"):
                if int(payload.get(field) or 0) < int(state["usage"].get(field) or 0):
                    raise RuntimeControlError("usage snapshot cumulative fields must be monotonic")
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
                raise RuntimeControlError("progress.advanced requires active goal and revision")
            revision = _integer(payload.get("revision"), "progress.revision", positive=True)
            if revision <= state["progress"]["revision"]:
                raise RuntimeControlError("progress revision must increase")
            state["progress"]["revision"] = revision
            state["progress"]["last_progress_at"] = _iso(at)
        elif kind == "heartbeat.recorded":
            if goal["status"] != "active" or payload:
                raise RuntimeControlError("heartbeat.recorded requires active goal and empty payload")
            progress = state["progress"]
            if progress["last_heartbeat_revision"] == progress["revision"]:
                progress["no_progress_heartbeats"] += 1
            else:
                progress["no_progress_heartbeats"] = 0
            progress["last_heartbeat_revision"] = progress["revision"]
            progress["heartbeat_at"] = _iso(at)
        elif kind == "retry.recorded":
            if goal["status"] != "active" or set(payload) != {"reason_id"}:
                raise RuntimeControlError("retry.recorded requires active goal and reason_id")
            _identifier(payload.get("reason_id"), "retry.reason_id")
            state["retry"]["used"] += 1
        elif kind == "evidence.added":
            if goal["status"] not in {"active", "completed"} or set(payload) != {"evidence_id", "sha256"}:
                raise RuntimeControlError("evidence.added payload fields are invalid")
            evidence_id = _identifier(payload.get("evidence_id"), "evidence.evidence_id")
            digest = _sha256(payload.get("sha256"), "evidence.sha256")
            existing = state["evidence"].get(evidence_id)
            if existing is not None and existing != digest:
                raise RuntimeControlError("evidence_id cannot change digest")
            state["evidence"][evidence_id] = digest
        elif kind == "checkpoint.verified":
            if goal["status"] not in {"active", "completed"} or set(payload) != {"revision", "evidence_ids"}:
                raise RuntimeControlError("checkpoint.verified payload fields are invalid")
            revision = _integer(payload.get("revision"), "checkpoint.revision")
            if revision > state["progress"]["revision"]:
                raise RuntimeControlError("checkpoint revision cannot exceed progress revision")
            evidence_ids = _ids(payload.get("evidence_ids"), "checkpoint.evidence_ids", non_empty=True)
            state["checkpoint"] = {"revision": revision, "verified": True, "evidence_ids": evidence_ids}
        elif kind == "artifact.verified":
            if set(payload) != {"artifact_type", "evidence_id"}:
                raise RuntimeControlError("artifact.verified payload fields are invalid")
            artifact_type = payload.get("artifact_type")
            if artifact_type not in ARTIFACT_TYPES:
                raise RuntimeControlError("unknown artifact_type")
            evidence_id = _identifier(payload.get("evidence_id"), "artifact.evidence_id")
            state["artifacts"][artifact_type] = evidence_id
        else:  # pragma: no cover
            raise RuntimeControlError("unhandled runtime control event")

        state["events_applied"] += 1
        state["last_event_at"] = _iso(at)

    if state is None:
        raise RuntimeControlError("runtime control requires at least one event")
    return state


def evaluate(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    gate_event: str = "steady",
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    normalized_policy = validate_policy(policy)
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
        raise RuntimeControlError("unsupported runtime control state schema")
    if gate_event not in GATE_EVENTS:
        raise RuntimeControlError("unsupported gate_event")
    now = as_of or datetime.now(UTC)
    if now.tzinfo is None:
        raise RuntimeControlError("as_of must include timezone")
    now = now.astimezone(UTC)

    goal = state.get("goal") or {}
    usage = state.get("usage") or {}
    progress = state.get("progress") or {}
    retry = state.get("retry") or {}
    checkpoint = state.get("checkpoint") or {}
    evidence = state.get("evidence") or {}
    artifacts = state.get("artifacts") or {}
    reasons: list[str] = []

    evidence_present = set(evidence)
    missing_evidence = sorted(set(goal.get("required_evidence") or []) - evidence_present)
    checkpoint_missing = sorted(set(checkpoint.get("evidence_ids") or []) - evidence_present)
    required_artifacts = normalized_policy["gate_policy"][gate_event]
    missing_artifacts = sorted(item for item in required_artifacts if item not in artifacts)
    artifact_evidence_missing = sorted(
        item for item in required_artifacts if item in artifacts and artifacts[item] not in evidence_present
    )

    total_tokens = int(usage.get("total_tokens") or 0)
    baseline_tokens = int(goal.get("usage_baseline_tokens") or 0)
    if usage.get("observed_at") and total_tokens < baseline_tokens:
        raise RuntimeControlError("goal usage baseline cannot exceed current usage snapshot")
    goal_tokens = max(total_tokens - baseline_tokens, 0)
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
        raise RuntimeControlError("heartbeat cannot be in the future")

    completion_valid = True
    if goal.get("status") == "completed":
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
        if int(progress.get("no_progress_heartbeats") or 0) >= int(normalized_policy["progress"]["no_progress_limit"]):
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
    elif int(progress.get("no_progress_heartbeats") or 0) >= int(normalized_policy["progress"]["no_progress_limit"]):
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
        and (not checkpoint.get("verified") or int(checkpoint.get("revision") or 0) != int(progress.get("revision") or 0))
    ):
        action = "checkpoint"
        reasons.append("token-budget-warning")
    else:
        action = "continue"

    gate_allowed = gate_event == "steady"
    if gate_event == "apply":
        gate_allowed = (
            goal.get("status") in {"active", "completed"}
            and action in {"continue", "pass"}
            and not missing_artifacts
            and not artifact_evidence_missing
        )
    elif gate_event != "steady":
        gate_allowed = goal.get("status") == "completed" and completion_valid

    if gate_event != "steady" and not gate_allowed:
        if missing_artifacts or artifact_evidence_missing:
            reasons.append("required-artifact-missing")
        if gate_event != "apply" and goal.get("status") != "completed":
            reasons.append("goal-not-completed")
        if action == "continue":
            action = "replan"
    elif gate_event != "steady" and gate_allowed:
        action = "pass"

    reasons = list(dict.fromkeys(reasons))
    completion_allowed = goal.get("status") == "completed" and completion_valid
    if gate_allowed and gate_event != "steady":
        status = "pass"
    elif completion_allowed:
        status = "pass"
    elif action == "continue":
        status = "active"
    elif action in {"checkpoint", "compact"}:
        status = "attention"
    else:
        status = "fail"

    return {
        "schema_version": DECISION_SCHEMA,
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
        "retry_remaining": max(int(normalized_policy["progress"]["retry_limit"]) - int(retry.get("used") or 0), 0),
        "no_progress_remaining": max(
            int(normalized_policy["progress"]["no_progress_limit"]) - int(progress.get("no_progress_heartbeats") or 0), 0
        ),
        "missing_evidence": missing_evidence,
        "checkpoint_evidence_missing": checkpoint_missing,
        "missing_artifacts": missing_artifacts,
        "artifact_evidence_missing": artifact_evidence_missing,
        "reasons": reasons,
    }
