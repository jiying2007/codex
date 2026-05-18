from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from .core import read_json, write_json

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "INFO": 1}


@dataclass
class GitChange:
    index: str
    worktree: str
    path: str


@dataclass
class Notice:
    severity: str
    code: str
    phase: str
    priority: int
    summary: str
    action: str
    commands: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    repeated: bool = False

    def finalize(self) -> "Notice":
        payload = json.dumps(
            {"code": self.code, "phase": self.phase, "evidence": self.evidence},
            ensure_ascii=False,
            sort_keys=True,
        )
        self.fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return self


def run_git(root: pathlib.Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["rtk", "git", "-C", str(root), *args], text=True, capture_output=True, check=False)


def parse_porcelain(output: str) -> list[GitChange]:
    changes: list[GitChange] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changes.append(GitChange(line[0], line[1], path))
    return changes


def git_changes(root: pathlib.Path) -> list[GitChange]:
    proc = run_git(root, ["status", "--porcelain=v1"])
    return parse_porcelain(proc.stdout) if proc.returncode == 0 else []


def starts(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def group_paths(changes: list[GitChange]) -> dict[str, list[str]]:
    paths = [change.path for change in changes]
    groups = {
        "staged": [c.path for c in changes if c.index not in {" ", "?"}],
        "agents": [p for p in paths if p in {"AGENTS.md", "src/codex-home/AGENTS.md"}],
        "skills": [p for p in paths if starts(p, ("src/codex-home/vendor/skills/", "manifests/skills.json"))],
        "agents_manifest": [p for p in paths if starts(p, ("src/codex-home/vendor/agents/", "manifests/agents.json"))],
        "workflows": [p for p in paths if starts(p, ("manifests/workflows.json",))],
        "manifests": [p for p in paths if starts(p, ("manifests/", "schemas/"))],
        "scripts": [p for p in paths if starts(p, ("scripts/", "tools/"))],
        "source": [
            p for p in paths
            if starts(p, ("src/codex-home/", "README.md", "docs/session-continuity-coach.md", "docs/design.md"))
        ],
        "archive": [p for p in paths if starts(p, ("docs/archive/",))],
    }
    groups["delivery"] = sorted(set().union(
        groups["agents"],
        groups["skills"],
        groups["agents_manifest"],
        groups["workflows"],
        groups["manifests"],
        groups["scripts"],
        groups["source"],
    ))
    return groups


def detect_phase(groups: dict[str, list[str]], token_pressure: bool, live_issue: bool) -> str:
    if live_issue:
        return "apply"
    if groups["staged"]:
        return "commit"
    if groups["delivery"]:
        return "asset-update"
    if token_pressure:
        return "handoff"
    if groups["archive"]:
        return "archive"
    return "steady"


def make_notice(
    severity: str,
    code: str,
    phase: str,
    priority: int,
    summary: str,
    action: str,
    commands: list[str] | None = None,
    **evidence: Any,
) -> Notice:
    return Notice(severity, code, phase, priority, summary, action, commands or [], evidence).finalize()


def load_state(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {"fingerprints": {}}
    try:
        return read_json(path)
    except Exception:
        return {"fingerprints": {}}


def apply_cooldown(notices: list[Notice], state_path: pathlib.Path, no_cooldown: bool, reset: bool) -> tuple[list[Notice], int]:
    if reset and state_path.exists():
        state_path.unlink()
    if no_cooldown:
        return notices, 0
    state = load_state(state_path)
    seen = state.setdefault("fingerprints", {})
    now = int(time.time())
    kept: list[Notice] = []
    suppressed = 0
    for notice in notices:
        record = seen.get(notice.fingerprint)
        if record:
            notice.repeated = True
        payload = {"last_seen": now, "count": int((record or {}).get("count", 0)) + 1, "code": notice.code}
        seen[notice.fingerprint] = payload
        if record and notice.severity in {"MEDIUM", "INFO"}:
            suppressed += 1
            continue
        kept.append(notice)
    write_json(state_path, state)
    return kept, suppressed


def rank_notices(notices: list[Notice], top: int, show_all: bool) -> list[Notice]:
    ranked = sorted(notices, key=lambda n: (n.priority, SEVERITY_RANK.get(n.severity, 0)), reverse=True)
    return ranked if show_all else ranked[:max(top, 0)]


def overall_status(notices: list[Notice]) -> str:
    severities = {n.severity for n in notices}
    if "CRITICAL" in severities:
        return "CRITICAL"
    if "HIGH" in severities:
        return "HOT"
    if "MEDIUM" in severities:
        return "WATCH"
    return "STABLE"
