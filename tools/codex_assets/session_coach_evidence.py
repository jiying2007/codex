from __future__ import annotations

import pathlib
import time
from typing import Any

from .core import read_json, write_json


def default_evidence_file(root: pathlib.Path) -> pathlib.Path:
    return root / ".cache/session-coach-evidence.json"


def load_evidence(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "records": []}
    try:
        data = read_json(path)
    except Exception:
        return {"schema_version": 1, "records": []}
    data.setdefault("schema_version", 1)
    data.setdefault("records", [])
    return data


def record_evidence(path: pathlib.Path, command: str, status: str, summary: str) -> dict[str, Any]:
    data = load_evidence(path)
    record = {
        "command": command,
        "status": status,
        "summary": summary,
        "recorded_at": int(time.time()),
    }
    data["records"] = [record] + data.get("records", [])[:49]
    write_json(path, data)
    return record


def latest_pass(path: pathlib.Path, command: str) -> dict[str, Any] | None:
    for record in load_evidence(path).get("records", []):
        if record.get("command") == command and record.get("status") == "pass":
            return record
    return None


def age_minutes(record: dict[str, Any]) -> int:
    return max(0, int((time.time() - int(record.get("recorded_at", 0))) / 60))
