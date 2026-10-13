"""Host-owned context diagnostics and bounded native configuration overlay.

This module neither compacts a session nor changes the canonical policy decision.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

KEYS = ("model_auto_compact_token_limit", "model_auto_compact_token_limit_scope")


def reusable_context_input(receipt: Mapping[str, Any]) -> str:
    """Restore only an unchanged explicit input, never guess a member config."""
    expected = receipt.get("context_config_input_sha256")
    if expected is None:
        return ""
    path = receipt.get("context_config_input_path")
    if not isinstance(path, str) or not path:
        raise ValueError("context build receipt lacks its explicit input path")
    try:
        actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("context build input is unavailable") from exc
    if actual != expected:
        raise ValueError("context build input changed; refusing implicit rebuild")
    return path


def parse_config(text: str) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError as exc:
            raise ValueError("context configuration requires tomli on Python < 3.11") from exc
    try:
        return tomllib.loads(text)
    except Exception as exc:
        raise ValueError("invalid TOML context configuration") from exc


def merge_context_config(existing: str, managed: str) -> str:
    """Change only two root keys; reject layouts that cannot be edited safely."""
    before, source = parse_config(existing), parse_config(managed)
    limit = source.get(KEYS[0])
    if type(limit) is not int or limit <= 0 or source.get(KEYS[1]) != "total":
        raise ValueError("managed context settings require a positive limit and total scope")
    lines = existing.splitlines(keepends=True)
    boundary = next((i for i, line in enumerate(lines) if re.match(r"\s*\[", line)), len(lines))
    root = lines[:boundary]
    for key in KEYS:
        # Root keys may be bare or quoted. Semantic verification below rejects
        # dotted/multiline layouts rather than touching unrelated values.
        pattern = r"^\s*(?:" + key + r"|\"" + key + r"\"|'" + key + r"')\s*="
        root = [line for line in root if not re.match(pattern, line)]
    prefix = "".join(root)
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    result = prefix + f'{KEYS[0]} = {limit}\n{KEYS[1]} = "total"\n' + "".join(lines[boundary:])
    after = parse_config(result)
    expected = dict(before)
    expected.update({key: source[key] for key in KEYS})
    if after != expected:
        raise ValueError("context overlay changed unrelated configuration; refusing build")
    return result


def maintenance_diagnostic(
    state: Mapping[str, Any], decision: Mapping[str, Any], policy: Mapping[str, Any], config_path: Path
) -> dict[str, Any]:
    usage = state.get("usage") or {}
    window = int(usage.get("context_window") or 0)
    guard = int(window * policy["context"]["compact_ratio"])
    settings: dict[str, Any] = {}
    config_status = "absent"
    if config_path.is_file():
        try:
            settings = parse_config(config_path.read_text(encoding="utf-8"))
            config_status = "read"
        except (OSError, ValueError):
            config_status = "unreadable-or-invalid"
    limit = settings.get(KEYS[0])
    scope = settings.get(KEYS[1], "total")
    valid_limit = type(limit) is int and limit > 0
    alignment = "unknown"
    if valid_limit and window > 0 and scope == "total":
        alignment = "before-policy-guard" if limit < guard else "at-or-after-policy-guard"
    required = decision.get("recommended_action") == "compact" and "context-pressure" in decision.get("reasons", [])
    return {
        "schema_version": "codex.context-maintenance/v1",
        "required": required,
        "state": "compaction-required" if required else "not-requested",
        "policy_guard_tokens": guard if window else None,
        "native_config_status": config_status,
        "configured_auto_compact_token_limit": limit if valid_limit else None,
        "configured_scope": scope if isinstance(scope, str) else None,
        "threshold_alignment": alignment,
        "effective_runtime_config_verified": False,
        "compaction_completion_verified": False,
        "next_action": "checkpoint-then-host-compaction-and-recheck" if required else "follow-policy-decision",
        "repeat_polling_is_progress": False,
        "gate_override": False,
    }
