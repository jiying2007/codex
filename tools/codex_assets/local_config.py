"""Hash-bound, partial machine preferences over the current managed template."""

import copy
import hashlib
import json
import math
from pathlib import Path

from .context_maintenance import parse_config


# Sandbox/command permissions, credentials, MCP transports and instructions stay source-owned.
ROOT_KEYS = {"model", "model_provider", "model_reasoning_effort", "plan_mode_reasoning_effort",
             "model_verbosity", "service_tier", "projects", "notice", "apps", "tui"}
TUI_KEYS = {"screen_reader_detection_done", "resume_cwd"}
NOTICE_FLAGS = {"hide_full_access_warning", "hide_gpt-5.1-codex-max_migration_prompt",
                "hide_gpt5_1_migration_prompt", "hide_rate_limit_model_nudge", "hide_world_writable_warning"}
APP_FLAGS = {"enabled", "default_tools_enabled", "destructive_enabled", "open_world_enabled"}
APP_KEYS = APP_FLAGS | {"tools", "default_tools_approval_mode", "approvals_reviewer"}
APPROVAL_MODES = {"auto", "prompt", "writes", "approve"}


def _choice(value, choices, name):
    if not isinstance(value, str) or value not in choices:
        raise ValueError("invalid local " + name)


def _validate_local_state(overrides):
    notice = overrides.get("notice", {})
    if set(notice) - (NOTICE_FLAGS | {"model_migrations"}):
        raise ValueError("unsupported local notice field")
    for key, value in notice.items():
        if key == "model_migrations":
            if not isinstance(value, dict) or any(not isinstance(v, str) or not v for v in value.values()):
                raise ValueError("invalid local model migrations")
        elif type(value) is not bool:
            raise ValueError("invalid local notice acknowledgement")
    for app in overrides.get("apps", {}).values():
        if not isinstance(app, dict) or set(app) - APP_KEYS:
            raise ValueError("unsupported local app field")
        for key, value in app.items():
            if key in APP_FLAGS and type(value) is not bool:
                raise ValueError("invalid local app flag")
            if key == "approvals_reviewer":
                _choice(value, {"user", "auto_review"}, "app reviewer")
            if key == "default_tools_approval_mode":
                _choice(value, APPROVAL_MODES, "app approval mode")
            if key == "tools":
                if not isinstance(value, dict):
                    raise ValueError("local app tools must be an object")
                for tool in value.values():
                    if not isinstance(tool, dict) or set(tool) - {"enabled", "approval_mode"}:
                        raise ValueError("unsupported local app tool field")
                    if "enabled" in tool and type(tool["enabled"]) is not bool:
                        raise ValueError("invalid local app tool enabled flag")
                    if "approval_mode" in tool:
                        _choice(tool["approval_mode"], APPROVAL_MODES, "app tool approval mode")


def load_config(path, expected_sha256, profile):
    path = Path(path).expanduser().resolve()
    raw = path.read_bytes()
    if len(raw) > 131072 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("local config input hash mismatch")
    data = json.loads(raw)
    if (not isinstance(data, dict)
            or set(data) != {"schema_version", "profile", "target", "overrides"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["profile"] != profile or data["target"] != "config.toml"):
        raise ValueError("local config input does not match target/profile")
    overrides = data["overrides"]
    if not isinstance(overrides, dict) or set(overrides) - ROOT_KEYS:
        raise ValueError("unsupported local config override")
    for name, value in overrides.items():
        if name in {"projects", "notice", "apps", "tui"}:
            if not isinstance(value, dict):
                raise ValueError("local config table must be an object")
        elif not isinstance(value, str) or not value:
            raise ValueError("local model preferences must be nonempty strings")
    if set(overrides.get("tui", {})) - TUI_KEYS:
        raise ValueError("unsupported local TUI override")
    tui = overrides.get("tui", {})
    if "resume_cwd" in tui:
        _choice(tui["resume_cwd"], {"current", "session"}, "resume_cwd")
    if "screen_reader_detection_done" in tui and type(tui["screen_reader_detection_done"]) is not bool:
        raise ValueError("invalid screen reader state")
    for path_name, entry in overrides.get("projects", {}).items():
        if (not Path(path_name).is_absolute() or not isinstance(entry, dict)
                or set(entry) != {"trust_level"}):
            raise ValueError("invalid local project trust entry")
        _choice(entry["trust_level"], {"trusted", "untrusted"}, "trust level")
    _validate_local_state(overrides)
    # Ensure the partial document is representable without unsupported TOML types.
    serialize_config(overrides)
    return overrides, {"path": str(path), "sha256": expected_sha256}


def _value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is float and math.isfinite(value):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(json.dumps(k, ensure_ascii=False) + " = " + _value(v)
                                 for k, v in value.items()) + " }"
    raise ValueError("unsupported TOML value in local configuration")


def serialize_config(config):
    lines = ["# Generated from the current managed template and explicit local overrides.",
             "# Edit source or the recorded local input, then build/plan/apply.", ""]

    def table(value, path):
        if path:
            lines.extend(["", "[" + ".".join(json.dumps(k, ensure_ascii=False) for k in path) + "]"])
        for key, item in value.items():
            if not isinstance(item, dict):
                lines.append(json.dumps(key, ensure_ascii=False) + " = " + _value(item))
        for key, item in value.items():
            if isinstance(item, dict):
                table(item, path + (key,))

    table(config, ())
    result = "\n".join(lines) + "\n"
    if parse_config(result) != config:
        raise ValueError("local config serialization changed TOML semantics")
    return result


def merge_config(managed, overrides):
    current = parse_config(managed)

    def merge(base, extra):
        for key, value in extra.items():
            if isinstance(value, dict):
                if key in base and not isinstance(base[key], dict):
                    raise ValueError("local config table conflicts with managed value")
                merge(base.setdefault(key, {}), value)
            else:
                base[key] = copy.deepcopy(value)

    merge(current, overrides)
    return serialize_config(current)
