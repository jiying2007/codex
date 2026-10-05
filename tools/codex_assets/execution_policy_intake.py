"""Host-owned, idempotent routing intake; never bypass the canonical engine."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path


def _checked_request(path: Path) -> bytes:
    from .execution_policy_adapter import ExecutionPolicyAdapterError

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 131072:
                raise ExecutionPolicyAdapterError("intake request must be a bounded regular file")
            value = os.read(fd, 131073)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ExecutionPolicyAdapterError("intake request file is unavailable") from exc
    if not value.strip() or len(value) > 131072:
        raise ExecutionPolicyAdapterError("intake request is empty or exceeds its byte budget")
    try:
        value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExecutionPolicyAdapterError("intake request must be UTF-8 text") from exc
    return value


def ensure(args: argparse.Namespace) -> int:
    from . import execution_policy_adapter as adapter

    if not args.thread_id:
        raise adapter.ExecutionPolicyAdapterError("ensure requires the exact current thread id")
    if os.environ.get("CODEX_THREAD_ID") and args.thread_id != os.environ["CODEX_THREAD_ID"]:
        raise adapter.ExecutionPolicyAdapterError("ensure cannot register a different thread from the current environment")
    root, config, paths, thread, journal = adapter._active_context(args)
    request_sha256 = hashlib.sha256(_checked_request(Path(args.request_file).expanduser())).hexdigest()
    rules = {}
    for label, path in (("runtime", root / "AGENTS.md"), ("project", Path(thread["cwd"]) / "AGENTS.md")):
        if path.is_file():
            rules[label] = hashlib.sha256(_checked_request(path)).hexdigest()
    if not rules:
        raise adapter.ExecutionPolicyAdapterError("ensure requires actual project or runtime routing rules")
    routing = {
        "schema_version": "codex-project-routing/v1", "task_mode": args.task_mode,
        "request_sha256": request_sha256, "rule_sha256": rules,
        "success_criteria": args.success_criterion, "required_evidence": args.required_evidence,
        "open_items": args.open_items,
    }
    routing_sha256 = hashlib.sha256(json.dumps(routing, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    goal_id = "task-" + routing_sha256[:24]
    decision_id = "routing-" + routing_sha256[:24]
    start_args = argparse.Namespace(**vars(args))
    start_args.goal_id = goal_id
    start_args.request_sha256 = request_sha256
    start_args.routing_decision_sha256 = routing_sha256
    start_args.authority_id = "codex-project-routing"
    start_args.source_id = "codex-project-routing"
    start_args.source_version = "v1"
    start_args.decision_id = decision_id
    start_args.issued_at = ""

    def started_event():
        now = adapter._now()
        event = adapter.control_event("goal.started", thread["thread_id"], {
            "goal_id": goal_id, "token_budget": args.token_budget,
            "time_budget_seconds": args.time_budget_seconds,
            "usage_baseline_tokens": adapter.usage_event(thread)["payload"]["total_tokens"],
            "success_criteria": args.success_criterion, "required_evidence": args.required_evidence,
            "open_items_count": args.open_items, "intake": adapter._goal_intake(start_args, now),
        })
        adapter._engine_state([event])
        return event
    # Serialize ensure callers, re-read state under the lock, and never replace an active goal.
    if args.dry_run:
        started_event()  # Validate budgets and canonical intake even when no write is requested.
        state = adapter._engine_state(adapter.load_journal(journal) + [adapter.usage_event(thread)])
        if state["goal"].get("status") in {"completed", "aborted"} and state["goal"].get("goal_id") != goal_id:
            state = dict(state, goal={"status": "idle"})
        return _result(adapter, state, goal_id, request_sha256, routing_sha256, args)
    journal.parent.mkdir(parents=True, exist_ok=True)
    lock = journal.with_suffix(".intake.lock")
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise adapter.ExecutionPolicyAdapterError("intake lock must be a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        events = adapter.load_journal(journal)
        state = adapter._engine_state(events + [adapter.usage_event(thread)])
        if (state["goal"].get("goal_id") == goal_id
                or state["goal"].get("status") == "active"):
            return _result(adapter, state, goal_id, request_sha256, routing_sha256, args)
        if events and not state["goal"].get("goal_id"):
            raise adapter.ExecutionPolicyAdapterError("ensure refuses to reset a journal without a valid goal")
        # Actual local routing authority, not an invented human or Digital Worker attestation.
        event = started_event()
        adapter._engine_state(events + [event])
        if events:
            adapter.append_journal(journal, event)
        else:
            adapter._write_new_journal(journal, event)
        state = adapter._engine_state(adapter.load_journal(journal))
        if (state["goal"].get("goal_id") != goal_id
                or not state["goal"].get("intake_attestation_sha256")):
            raise adapter.ExecutionPolicyAdapterError("intake readback failed")
        return _result(adapter, state, goal_id, request_sha256, routing_sha256, args, created=True)
    finally:
        os.close(fd)


def _result(adapter, state, goal_id, request_hash, routing_hash, args, created=False):
    goal = state["goal"]
    if goal.get("goal_id"):
        if (goal.get("goal_id") != goal_id or goal.get("request_sha256") != request_hash
                or goal.get("routing_decision_sha256") != routing_hash
                or not goal.get("intake_attestation_sha256")):
            raise adapter.ExecutionPolicyAdapterError("ensure conflicts with existing goal; explicitly replan or start a new task")
        status = "REGISTERED" if created else "ALREADY_REGISTERED"
    else:
        status = "PLANNED"
    adapter._emit({"schema_version": "codex-intake-receipt/v1", "status": status,
                   "persisted": bool(goal.get("goal_id")),
                   "write_performed": created, "read_only": args.dry_run,
                   "thread_id": args.thread_id, "goal_id": goal_id,
                   "request_sha256": request_hash, "routing_decision_sha256": routing_hash,
                   "goal_status": goal.get("status"), "final_gate_passed": False})
    return 0


def configure(parser):
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--task-mode", choices=["readonly", "implementation", "debugging", "review", "release"], required=True)
    parser.add_argument("--success-criterion", action="append", required=True)
    parser.add_argument("--required-evidence", action="append", required=True)
    parser.add_argument("--open-items", type=int, required=True)
    parser.add_argument("--token-budget", type=int, default=300000)
    parser.add_argument("--time-budget-seconds", type=int, default=14400)
    parser.add_argument("--dry-run", action="store_true")
