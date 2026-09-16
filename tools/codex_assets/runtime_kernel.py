"""Codex-native facade over the exact ADK v5.1.1 execution-policy source set.

The canonical engine/contracts are vendored byte-for-byte under
``tools.codex_assets.execution_policy``.  The small facade preserves the
existing Codex import surface while keeping runtime assembly local and
stdlib-only.
"""

from .execution_policy.engine import (
    DECISION_SCHEMA,
    DECISION_SCHEMA_V2,
    EVENT_SCHEMA,
    POLICY_SCHEMA,
    POLICY_SCHEMA_V2,
    STATE_SCHEMA,
    RuntimeControlError,
    evaluate,
    goal_intake_attestation_sha256,
    reduce_events,
    validate_policy,
)

__all__ = [
    "DECISION_SCHEMA",
    "DECISION_SCHEMA_V2",
    "EVENT_SCHEMA",
    "POLICY_SCHEMA",
    "POLICY_SCHEMA_V2",
    "STATE_SCHEMA",
    "RuntimeControlError",
    "evaluate",
    "goal_intake_attestation_sha256",
    "reduce_events",
    "validate_policy",
]
