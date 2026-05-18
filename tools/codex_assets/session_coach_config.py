from __future__ import annotations

import pathlib
import re
from typing import Any

from .core import read_json

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "defaults": {
        "top": 3,
        "warn_thread_tokens": 50_000_000,
        "context_pressure_ratio": 0.5,
        "large_delta_tokens": 100_000,
        "evidence_fresh_minutes": 240,
        "archive_max_bytes": 262_144,
    },
    "events": {},
    "protected_archive_patterns": [],
}

ALLOWED_EVENTS = {"final", "commit", "push", "apply", "resume", "target-switch", "memory-curation"}
ALLOWED_PHASES = {"apply", "commit", "asset-update", "handoff", "archive", "steady"}


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(root: pathlib.Path, config_path: str = "") -> dict[str, Any]:
    path = pathlib.Path(config_path).expanduser() if config_path else root / "manifests/session_coach.json"
    if not path.is_file():
        return dict(DEFAULT_CONFIG)
    return merge_dict(DEFAULT_CONFIG, read_json(path))


def validate_config(config: dict[str, Any]) -> list[str]:
    merged = merge_dict(DEFAULT_CONFIG, config)
    errors: list[str] = []
    if not isinstance(config.get("defaults", {}), dict):
        errors.append("defaults 必须是 object")
        return errors
    if not isinstance(config.get("events", {}), dict):
        errors.append("events 必须是 object")
        return errors
    defaults = merged.get("defaults", {})
    int_fields = ["top", "warn_thread_tokens", "large_delta_tokens", "evidence_fresh_minutes", "archive_max_bytes"]
    for field in int_fields:
        value = defaults.get(field)
        if not isinstance(value, int) or value < 0:
            errors.append(f"defaults.{field} 必须是非负整数")
    ratio = defaults.get("context_pressure_ratio")
    if not isinstance(ratio, (int, float)) or ratio <= 0 or ratio > 1:
        errors.append("defaults.context_pressure_ratio 必须在 (0, 1] 范围内")
    events = merged.get("events", {})
    for name, event in events.items():
        if name not in ALLOWED_EVENTS:
            errors.append(f"events 包含未知事件: {name}")
        if not isinstance(event, dict):
            errors.append(f"events.{name} 必须是 object")
            continue
        phase = event.get("phase", "")
        if phase and phase not in ALLOWED_PHASES:
            errors.append(f"events.{name}.phase 非法: {phase}")
        required = event.get("required_evidence", "")
        if required and not isinstance(required, str):
            errors.append(f"events.{name}.required_evidence 必须是字符串")
    patterns = merged.get("protected_archive_patterns", [])
    if not isinstance(patterns, list):
        errors.append("protected_archive_patterns 必须是数组")
        return errors
    for index, pattern in enumerate(patterns):
        if not isinstance(pattern, str):
            errors.append(f"protected_archive_patterns[{index}] 必须是字符串")
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"protected_archive_patterns[{index}] 正则非法: {exc}")
    return errors


def default_value(config: dict[str, Any], key: str, fallback: Any = None) -> Any:
    return config.get("defaults", {}).get(key, fallback)


def event_config(config: dict[str, Any], event: str) -> dict[str, Any]:
    if not event:
        return {}
    return config.get("events", {}).get(event, {})
