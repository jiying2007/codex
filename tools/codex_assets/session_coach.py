from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import asdict
from typing import Any

from .session_coach_core import (
    GitChange,
    Notice,
    apply_cooldown,
    detect_phase,
    git_changes,
    group_paths,
    overall_status,
    parse_porcelain,
    rank_notices,
)
from .session_coach_rules import live_notices, repo_notices, usage_notices

__all__ = [
    "GitChange",
    "Notice",
    "apply_cooldown",
    "detect_phase",
    "group_paths",
    "parse_porcelain",
    "rank_notices",
    "run",
]


def emit_markdown(payload: dict[str, Any]) -> None:
    print("# Session Coach")
    print(f"status: {payload['status']}")
    print(f"phase: {payload['phase']}")
    print(f"suppressed: {payload['suppressed']}")
    print()
    notices = payload["notices"]
    if not notices:
        print("- [INFO] STABLE: 暂无会话连续性提醒。")
        print("  next: 聚焦当前用户目标；收口前再次运行 `rtk bash scripts/session-coach.sh --deep`。")
        return
    for notice in notices:
        repeat = " repeated" if notice.get("repeated") else ""
        print(f"- [{notice['severity']}] {notice['code']} ({notice['phase']}{repeat}): {notice['summary']}")
        print(f"  next: {notice['action']}")
        if notice.get("commands"):
            print(f"  commands: {' ; '.join(notice['commands'])}")
        if notice.get("evidence"):
            print(f"  evidence: {json.dumps(notice['evidence'], ensure_ascii=False, sort_keys=True)}")


def collect_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).expanduser().resolve()
    codex_home = pathlib.Path(args.codex_home).expanduser().resolve()
    target = pathlib.Path(args.target).expanduser().resolve()
    state_file = pathlib.Path(args.state_file).expanduser() if args.state_file else root / ".cache/session-coach-state.json"
    groups = group_paths(git_changes(root))
    usage, token_pressure = usage_notices(codex_home, args.warn_thread_tokens)
    live, live_issue = live_notices(root, target) if args.deep else ([], False)
    phase = detect_phase(groups, token_pressure, live_issue)
    notices, suppressed = apply_cooldown(usage + repo_notices(groups, phase) + live, state_file, args.no_cooldown, args.reset_state)
    ranked = rank_notices(notices, args.top, args.all)
    return {
        "schema_version": 2,
        "status": overall_status(ranked),
        "phase": phase,
        "deep": bool(args.deep),
        "suppressed": suppressed,
        "state_file": str(state_file),
        "notices": [asdict(notice) for notice in ranked],
    }


def run(args: argparse.Namespace) -> int:
    payload = collect_payload(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        emit_markdown(payload)
    return 0
