"""Validation and contract primitives for the execution-policy engine."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ..model import ManifestError
from ..privacy_ref import validate_no_secrets

EVENT_SCHEMA = "runtime_control.event/v1"
STATE_SCHEMA = "runtime_control.state/v1"
DECISION_SCHEMA_V2 = "runtime_control.decision/v2"
POLICY_SCHEMA_V2 = "runtime_control.policy/v2"
GOAL_INTAKE_SCHEMA = "runtime_control.goal-intake/v1"

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
TASK_MODES = {"readonly", "implementation", "release"}
GOAL_TASK_MODES = {"readonly", "implementation", "debugging", "review", "release"}
GOAL_TASK_ARTIFACT_MODES = {
    "readonly": "readonly",
    "implementation": "implementation",
    "debugging": "readonly",
    "review": "readonly",
    "release": "release",
}
TASK_MODE_ARTIFACT_FLOORS = {
    "implementation": {
        "final": {"repo", "build"},
        "commit": {"repo", "build", "review"},
        "apply": {"repo", "build", "plan", "dry-run"},
    },
    "release": {
        "final": {"repo", "build"},
        "commit": {"repo", "build", "review"},
        "apply": {"repo", "build", "plan", "dry-run"},
        "release": {"repo", "build", "live", "review"},
    },
}
READONLY_IMPLEMENTATION_ARTIFACTS = {"repo", "build", "plan", "dry-run", "live"}
SENSITIVE_FIELDS = {"prompt", "messages", "content", "text", "raw_input", "raw_output", "objective"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UTC = UTC


class ExecutionPolicyError(ValueError):
    """Raised when policy, event history or state violates the canonical contract."""


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ExecutionPolicyError(f"{field} must be a bounded stable identifier")
    try:
        validate_no_secrets(value, field)
    except ManifestError as exc:
        raise ExecutionPolicyError(str(exc)) from exc
    return value


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        label = "positive" if positive else "non-negative"
        raise ExecutionPolicyError(f"{field} must be a {label} integer")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionPolicyError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ExecutionPolicyError(f"{field} must be finite")
    return result


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ExecutionPolicyError(f"{field} must be an RFC3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ExecutionPolicyError(f"{field} must be an RFC3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ExecutionPolicyError(f"{field} must include a timezone")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _reject_sensitive(value: Any) -> None:
    try:
        validate_no_secrets(value, "runtime control input")
    except ManifestError as exc:
        raise ExecutionPolicyError(str(exc)) from exc
    if isinstance(value, dict):
        if set(value) & SENSITIVE_FIELDS:
            raise ExecutionPolicyError("runtime control input contains a forbidden sensitive field")
        for nested in value.values():
            _reject_sensitive_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_fields(nested)


def _reject_sensitive_fields(value: Any) -> None:
    if isinstance(value, dict):
        if set(value) & SENSITIVE_FIELDS:
            raise ExecutionPolicyError("runtime control input contains a forbidden sensitive field")
        for nested in value.values():
            _reject_sensitive_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_fields(nested)


def _ids(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ExecutionPolicyError(f"{field} must be a list")
    result = [_identifier(item, field) for item in value]
    if len(result) != len(set(result)):
        raise ExecutionPolicyError(f"{field} must not contain duplicates")
    if non_empty and not result:
        raise ExecutionPolicyError(f"{field} must not be empty")
    return result


def _sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise ExecutionPolicyError(f"{field} must be a SHA-256 digest")
    return value


def _fingerprint(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
    """Return the canonical digest callers must bind into a goal intake."""
    return _fingerprint({
        "schema_version": GOAL_INTAKE_SCHEMA,
        "task_mode": task_mode,
        "artifact_mode": artifact_mode,
        "goal_id": goal_id,
        "request_sha256": request_sha256,
        "routing_decision_sha256": routing_decision_sha256,
        "authority_id": authority_id,
        "provenance": provenance,
    })


def _validate_goal_intake(
    value: Any,
    *,
    event_at: datetime,
    expected_kind: str,
    expected_goal_id: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "task_mode", "artifact_mode", "goal_id", "request_sha256",
        "routing_decision_sha256", "authority_id", "attestation_sha256", "provenance"
    }:
        raise ExecutionPolicyError("goal intake fields are invalid")
    if value.get("schema_version") != GOAL_INTAKE_SCHEMA:
        raise ExecutionPolicyError("unsupported goal intake schema")
    task_mode = value.get("task_mode")
    artifact_mode = value.get("artifact_mode")
    if task_mode not in GOAL_TASK_MODES:
        raise ExecutionPolicyError("unsupported goal intake task_mode")
    if artifact_mode not in TASK_MODES:
        raise ExecutionPolicyError("unsupported goal intake artifact_mode")
    if GOAL_TASK_ARTIFACT_MODES[task_mode] != artifact_mode:
        raise ExecutionPolicyError("goal intake task_mode and artifact_mode are inconsistent")
    goal_id = _identifier(value.get("goal_id"), "goal.intake.goal_id")
    if goal_id != expected_goal_id:
        raise ExecutionPolicyError("goal intake goal_id does not match its goal event")
    request_sha256 = _sha256(value.get("request_sha256"), "goal.intake.request_sha256")
    routing_decision_sha256 = _sha256(
        value.get("routing_decision_sha256"), "goal.intake.routing_decision_sha256"
    )
    authority_id = _identifier(value.get("authority_id"), "goal.intake.authority_id")
    provenance = value.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {
        "kind", "source_id", "source_version", "decision_id", "issued_at"
    }:
        raise ExecutionPolicyError("goal intake provenance fields are invalid")
    if provenance.get("kind") != expected_kind:
        raise ExecutionPolicyError(
            f"goal intake provenance kind must be {expected_kind}"
        )
    normalized_provenance = {
        "kind": expected_kind,
        "source_id": _identifier(provenance.get("source_id"), "goal.intake.provenance.source_id"),
        "source_version": _identifier(
            provenance.get("source_version"), "goal.intake.provenance.source_version"
        ),
        "decision_id": _identifier(
            provenance.get("decision_id"), "goal.intake.provenance.decision_id"
        ),
        "issued_at": _iso(
            _timestamp(provenance.get("issued_at"), "goal.intake.provenance.issued_at")
        ),
    }
    if _timestamp(normalized_provenance["issued_at"], "goal.intake.provenance.issued_at") > event_at:
        raise ExecutionPolicyError("goal intake provenance cannot be issued after its event")
    expected_digest = goal_intake_attestation_sha256(
        str(task_mode), str(artifact_mode), normalized_provenance,
        goal_id=goal_id,
        request_sha256=request_sha256,
        routing_decision_sha256=routing_decision_sha256,
        authority_id=authority_id,
    )
    if value.get("attestation_sha256") != expected_digest:
        raise ExecutionPolicyError("goal intake attestation digest mismatch")
    return {
        "schema_version": GOAL_INTAKE_SCHEMA,
        "task_mode": task_mode,
        "artifact_mode": artifact_mode,
        "goal_id": goal_id,
        "request_sha256": request_sha256,
        "routing_decision_sha256": routing_decision_sha256,
        "authority_id": authority_id,
        "attestation_sha256": expected_digest,
        "provenance": normalized_provenance,
    }


def validate_policy(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_version") != POLICY_SCHEMA_V2:
        raise ExecutionPolicyError("unsupported runtime control policy schema")
    _reject_sensitive(value)
    expected_fields = {
        "schema_version",
        "token",
        "context",
        "progress",
        "artifact_applicability",
        "mode_authority_policy",
        "retention",
    }
    if set(value) != expected_fields:
        raise ExecutionPolicyError("runtime control policy fields are invalid")

    token = value.get("token")
    if not isinstance(token, dict) or set(token) != {"checkpoint_ratio", "compact_ratio", "stop_ratio"}:
        raise ExecutionPolicyError("token policy fields are invalid")
    checkpoint_ratio = _number(token.get("checkpoint_ratio"), "token.checkpoint_ratio")
    compact_ratio = _number(token.get("compact_ratio"), "token.compact_ratio")
    stop_ratio = _number(token.get("stop_ratio"), "token.stop_ratio")
    if not 0 < checkpoint_ratio < compact_ratio < stop_ratio:
        raise ExecutionPolicyError("token ratios must satisfy checkpoint < compact < stop")

    context = value.get("context")
    if not isinstance(context, dict) or set(context) != {"compact_ratio"}:
        raise ExecutionPolicyError("context policy fields are invalid")
    context_ratio = _number(context.get("compact_ratio"), "context.compact_ratio")
    if not 0 < context_ratio <= 1:
        raise ExecutionPolicyError("context.compact_ratio must be in (0, 1]")

    progress = value.get("progress")
    if not isinstance(progress, dict) or set(progress) != {
        "staleness_seconds", "retry_limit", "no_progress_limit"
    }:
        raise ExecutionPolicyError("progress policy fields are invalid")
    _integer(progress.get("staleness_seconds"), "progress.staleness_seconds", positive=True)
    _integer(progress.get("retry_limit"), "progress.retry_limit", positive=True)
    _integer(progress.get("no_progress_limit"), "progress.no_progress_limit", positive=True)

    applicability = value.get("artifact_applicability")
    if not isinstance(applicability, dict) or set(applicability) != TASK_MODES:
        raise ExecutionPolicyError("artifact_applicability must define every canonical task mode")
    normalized_applicability: dict[str, dict[str, list[str] | None]] = {}
    for task_mode, gate_matrix in applicability.items():
        if not isinstance(gate_matrix, dict) or set(gate_matrix) != GATE_EVENTS:
            raise ExecutionPolicyError(
                f"artifact_applicability.{task_mode} must define every canonical gate event"
            )
        normalized_matrix: dict[str, list[str] | None] = {}
        for gate, required in gate_matrix.items():
            if required is None:
                normalized_matrix[gate] = None
                continue
            items = _ids(required, f"artifact_applicability.{task_mode}.{gate}")
            if set(items) - ARTIFACT_TYPES:
                raise ExecutionPolicyError("artifact_applicability references unknown artifact types")
            normalized_matrix[gate] = items
        normalized_applicability[task_mode] = normalized_matrix

    readonly = normalized_applicability["readonly"]
    if (
        readonly["steady"] != []
        or readonly["commit"] is not None
        or readonly["apply"] is not None
        or readonly["release"] is not None
    ):
        raise ExecutionPolicyError("readonly task mode may only use steady and final gates")
    if readonly["final"] is None:
        raise ExecutionPolicyError("readonly.final must be applicable")
    if set(readonly["final"] or []) & READONLY_IMPLEMENTATION_ARTIFACTS:
        raise ExecutionPolicyError("readonly.final cannot require implementation artifacts")

    implementation = normalized_applicability["implementation"]
    if implementation["steady"] != [] or implementation["release"] is not None:
        raise ExecutionPolicyError("implementation task mode cannot use the release gate")
    for gate, floor in TASK_MODE_ARTIFACT_FLOORS["implementation"].items():
        required = implementation[gate]
        if required is None or not floor <= set(required):
            raise ExecutionPolicyError(
                f"implementation.{gate} must retain fail-closed artifact requirements"
            )

    release = normalized_applicability["release"]
    if release["steady"] != []:
        raise ExecutionPolicyError("release.steady must not require artifacts")
    for gate, floor in TASK_MODE_ARTIFACT_FLOORS["release"].items():
        required = release[gate]
        if required is None or not floor <= set(required):
            raise ExecutionPolicyError(
                f"release.{gate} must retain fail-closed artifact requirements"
            )

    authority_policy = value.get("mode_authority_policy")
    if not isinstance(authority_policy, dict) or set(authority_policy) != {
        "managed", "trusted_mode_authorities", "verification_backend"
    }:
        raise ExecutionPolicyError("mode_authority_policy fields are invalid")
    if authority_policy.get("managed") is not True:
        raise ExecutionPolicyError("mode authority policy must be managed")
    trusted_mode_authorities = _ids(
        authority_policy.get("trusted_mode_authorities"),
        "mode_authority_policy.trusted_mode_authorities",
    )
    verification_backend = authority_policy.get("verification_backend")
    if verification_backend not in {"not-configured", "managed-authority-registry"}:
        raise ExecutionPolicyError("unsupported mode authority verification backend")
    if trusted_mode_authorities and verification_backend == "not-configured":
        raise ExecutionPolicyError(
            "trusted mode authorities require a configured verification backend"
        )
    if not trusted_mode_authorities and verification_backend != "not-configured":
        raise ExecutionPolicyError(
            "mode authority backend cannot be configured without trusted authorities"
        )
    normalized_authority_policy = {
        "managed": True,
        "trusted_mode_authorities": trusted_mode_authorities,
        "verification_backend": verification_backend,
    }

    retention = value.get("retention")
    if not isinstance(retention, dict) or set(retention) != {"journal_days", "raw_content_stored"}:
        raise ExecutionPolicyError("retention policy fields are invalid")
    _integer(retention.get("journal_days"), "retention.journal_days", positive=True)
    if retention.get("raw_content_stored") is not False:
        raise ExecutionPolicyError("runtime control must not store raw content")

    return {
        "schema_version": POLICY_SCHEMA_V2,
        "token": {
            "checkpoint_ratio": checkpoint_ratio,
            "compact_ratio": compact_ratio,
            "stop_ratio": stop_ratio,
        },
        "context": {"compact_ratio": context_ratio},
        "progress": dict(progress),
        "artifact_applicability": normalized_applicability,
        "mode_authority_policy": normalized_authority_policy,
        "retention": dict(retention),
    }


def _validate_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExecutionPolicyError("runtime control event must be an object")
    _reject_sensitive(value)
    if set(value) != {"schema_version", "event_id", "event_type", "thread_id", "observed_at", "payload"}:
        raise ExecutionPolicyError("runtime control event fields are invalid")
    if value.get("schema_version") != EVENT_SCHEMA:
        raise ExecutionPolicyError("unsupported runtime control event schema")
    event_type = value.get("event_type")
    if event_type not in EVENT_TYPES:
        raise ExecutionPolicyError("unsupported runtime control event_type")
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise ExecutionPolicyError("event payload must be an object")
    return {
        "schema_version": EVENT_SCHEMA,
        "event_id": _identifier(value.get("event_id"), "event_id"),
        "event_type": event_type,
        "thread_id": _identifier(value.get("thread_id"), "thread_id"),
        "observed_at": _timestamp(value.get("observed_at"), "observed_at"),
        "payload": dict(payload),
        "fingerprint": _fingerprint(value),
    }
