from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import asdict
from typing import Any

from .session_coach_core import (
    GitChange,
    Notice,
    ack_notice,
    apply_cooldown,
    detect_phase,
    event_phase,
    fail_on_triggered,
    git_changes,
    group_paths,
    overall_status,
    parse_porcelain,
    rank_notices,
)
from .session_coach_config import default_value, load_config
from .session_coach_evidence import default_evidence_file, record_evidence
from .session_coach_rules import live_notices, repo_notices, usage_notices

__all__ = [
    "GitChange",
    "Notice",
    "ack_notice",
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
    if payload.get("event"):
        print(f"event: {payload['event']}")
    if payload.get("fail_on") and payload.get("fail_on") != "never":
        print(f"fail_on: {payload['fail_on']}")
        print(f"gate_failed: {payload['gate_failed']}")
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
    config = load_config(root, args.config)
    state_file = pathlib.Path(args.state_file).expanduser() if args.state_file else root / ".cache/session-coach-state.json"
    evidence_file = pathlib.Path(args.evidence_file).expanduser() if args.evidence_file else default_evidence_file(root)
    groups = group_paths(git_changes(root))
    usage, token_pressure = usage_notices(codex_home, config, args.warn_thread_tokens)
    live, live_issue = live_notices(root, target) if args.deep else ([], False)
    phase = event_phase(args.event, config) or detect_phase(groups, token_pressure, live_issue)
    notices, suppressed = apply_cooldown(
        usage + repo_notices(root, groups, phase, args.event, config, evidence_file, args.deep) + live,
        state_file,
        args.no_cooldown,
        args.reset_state,
    )
    status = overall_status(notices)
    fail_on = getattr(args, "fail_on", "never") or "never"
    gate_failed = fail_on_triggered(notices, fail_on)
    top = args.top if args.top is not None else int(default_value(config, "top", 3))
    ranked = rank_notices(notices, top, args.all)
    return {
        "schema_version": 2,
        "status": status,
        "phase": phase,
        "event": args.event,
        "deep": bool(args.deep),
        "fail_on": fail_on,
        "gate_failed": gate_failed,
        "suppressed": suppressed,
        "state_file": str(state_file),
        "evidence_file": str(evidence_file),
        "notices": [asdict(notice) for notice in ranked],
    }


def run(args: argparse.Namespace) -> int:
    if args.ack or args.clear_acks:
        root = pathlib.Path(args.root).expanduser().resolve()
        state_file = pathlib.Path(args.state_file).expanduser() if args.state_file else root / ".cache/session-coach-state.json"
        state = ack_notice(state_file, args.ack, clear=args.clear_acks)
        print(json.dumps({"schema_version": 1, "state_file": str(state_file), "acks": state.get("acks", {})}, ensure_ascii=False, indent=2))
        return 0
    if args.record_evidence:
        root = pathlib.Path(args.root).expanduser().resolve()
        evidence_file = pathlib.Path(args.evidence_file).expanduser() if args.evidence_file else default_evidence_file(root)
        record = record_evidence(evidence_file, args.record_evidence, args.evidence_status, args.evidence_summary)
        print(json.dumps({"schema_version": 1, "evidence_file": str(evidence_file), "record": record}, ensure_ascii=False, indent=2))
        return 0
    payload = collect_payload(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        emit_markdown(payload)
    return 2 if payload.get("gate_failed") else 0
