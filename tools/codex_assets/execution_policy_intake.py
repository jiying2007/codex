"""Host-owned, idempotent routing intake; never bypass the canonical engine."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
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


def _event_issued_on(event: dict, day: str) -> bool:
    try:
        timestamp = datetime.fromisoformat(str(event.get("timestamp", "")).replace("Z", "+00:00"))
        return timestamp.tzinfo is not None and timestamp.astimezone(timezone.utc).date().isoformat() == day
    except ValueError:
        return False


def _user_request_matches(path: Path, value: bytes = b"", *, sha256: str = "", issued_on: str = "") -> bool:
    """Compare bounded native user events; never persist or expose their text."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(str(path), flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                return False
            # Keep both initial and recent requests within a fixed total byte budget.
            half = 33554432
            windows = [(0, info.st_size)] if info.st_size <= 2 * half else [(0, half), (info.st_size - half, info.st_size)]
            expected = value.decode("utf-8").strip()
            for start, end in windows:
                stream.seek(start)
                discard = start > 0  # A tail window may start inside a record.
                while stream.tell() < end:
                    line = stream.readline(min(1048577, end - stream.tell()))
                    if not line:
                        break
                    complete = line.endswith(b"\n") or stream.tell() == info.st_size
                    if discard or len(line) > 1048576 or not complete:
                        discard = not complete
                        continue
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(event, dict):
                        continue
                    if issued_on and not _event_issued_on(event, issued_on):
                        continue
                    payload = event.get("payload", {})
                    if not isinstance(payload, dict):
                        continue
                    text = None
                    if event.get("type") == "event_msg" and payload.get("type") == "user_message":
                        text = payload.get("message")
                    elif event.get("type") == "response_item" and payload.get("role") == "user":
                        parts = payload.get("content", [])
                        if isinstance(parts, list):
                            texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("type") == "input_text"]
                            if all(isinstance(part, str) for part in texts):
                                text = "\n".join(texts)
                    if isinstance(text, str):
                        if sha256:
                            # apply_patch request files conventionally end in one newline.
                            if sha256 in {hashlib.sha256(raw.encode()).hexdigest()
                                          for raw in (text, text + "\n")}:
                                return True
                        elif text.strip() == expected:
                            return True
    except OSError:
        return False
    return False


def _explicit_request_renewal(value: bytes) -> bool:
    text = value.decode("utf-8")
    if re.search(r"不得|不要|禁止|不再|取消|撤销|do not|revoke|cancel", text, re.I):
        return False
    return bool(re.search(r"当前目标|current goal", text, re.I)
                and re.search(r"预算.{0,24}(?:延长|追加)|(?:续期|延长).{0,24}预算|(?:extend|renew).{0,40}budget", text, re.I)
                and re.search(r"沿用.{0,40}授权.{0,20}继续执行|continue.{0,40}(?:existing|prior).{0,20}authori[sz]ation", text, re.I))


def _renewed_request_provenance(adapter, config, thread, events, intake, renewal, request_hash):
    """Fresh request provenance only; never append events or grant domain approval."""
    day = adapter._now().date().isoformat()
    if (not _explicit_request_renewal(renewal)
            or not _user_request_matches(Path(thread["rollout_path"]), renewal, issued_on=day)):
        return None
    state = adapter._engine_state(events + [adapter.usage_event(thread)])
    goal = state.get("goal", {})
    if goal.get("status") != "active" or not goal.get("goal_id"):
        return None
    decision = adapter._decision(state, config, "steady")
    if decision.get("budget_status", {}).get("status") != "within":
        return None
    binding = {"schema_version": "codex-request-renewal/v1", "thread_id": thread["thread_id"],
               "request_sha256": request_hash, "original_attestation_sha256": intake["attestation_sha256"],
               "renewal_request_sha256": hashlib.sha256(renewal).hexdigest(), "goal_id": goal["goal_id"],
               "current_goal_intake_attestation_sha256": goal.get("intake_attestation_sha256"),
               "issued_on": day, "purpose": "request-provenance-only;not-owner-approval"}
    return dict(binding, attestation_sha256=hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest())


def verify_request(args: argparse.Namespace) -> int:
    """Expose attested request provenance without exposing journal paths or text."""
    from . import execution_policy_adapter as adapter
    if not args.thread_id or args.thread_id != os.environ.get("CODEX_THREAD_ID"):
        raise adapter.ExecutionPolicyAdapterError("request verification requires the exact current thread")
    _, config, _, thread, journal = adapter._active_context(args)
    value = _checked_request(Path(args.request_file).expanduser())
    expected = hashlib.sha256(value).hexdigest()
    user_verified = _user_request_matches(Path(thread["rollout_path"]), value)
    renewal_file = getattr(args, "renewal_request_file", "")
    renewal = _checked_request(Path(renewal_file).expanduser()) if renewal_file else None
    events = adapter.load_journal(journal)
    adapter._engine_state(events)  # Verify the whole canonical event stream, without appending usage.
    for event in reversed(events):
        intake = event.get("payload", {}).get("intake", {})
        if (event.get("event_type") != "goal.started" or event.get("thread_id") != thread["thread_id"]
                or intake.get("request_sha256") != expected or not user_verified):
            continue
        renewed = (_renewed_request_provenance(adapter, config, thread, events, intake, renewal, expected)
                   if renewal is not None else None)
        if renewal is not None and renewed is None:
            continue
        if renewed is None and str(intake.get("provenance", {}).get("issued_at", ""))[:10] != adapter._now().date().isoformat():
            continue
        adapter._emit({"schema_version": "codex-request-verification/v1", "status": "VERIFIED", "read_only": True,
                       "thread_id": thread["thread_id"], "request_sha256": expected,
                       "attestation_sha256": renewed["attestation_sha256"] if renewed else intake["attestation_sha256"],
                       **({"renewal_provenance": renewed} if renewed else {}),
                       "user_message_verified": True,
                       "cwd_sha256": hashlib.sha256(str(Path(thread["cwd"]).resolve()).encode()).hexdigest(),
                       "purpose": "request-provenance-only;not-owner-approval"})
        return 0
    adapter._emit({"schema_version": "codex-request-verification/v1", "status": "UNVERIFIED", "read_only": True,
                   "thread_id": thread["thread_id"], "request_sha256": expected})
    return 2


def ensure(args: argparse.Namespace) -> int:
    from . import execution_policy_adapter as adapter

    if not args.thread_id:
        raise adapter.ExecutionPolicyAdapterError("ensure requires the exact current thread id")
    if os.environ.get("CODEX_THREAD_ID") and args.thread_id != os.environ["CODEX_THREAD_ID"]:
        raise adapter.ExecutionPolicyAdapterError("ensure cannot register a different thread from the current environment")
    root, config, paths, thread, journal = adapter._active_context(args)
    request_sha256 = hashlib.sha256(_checked_request(Path(args.request_file).expanduser())).hexdigest()
    from .execution_policy_authority import routing_record
    routing = routing_record(root, thread, request_sha256, args.task_mode,
                             args.success_criterion, args.required_evidence, args.open_items)
    routing_sha256 = hashlib.sha256(json.dumps(routing, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    goal_id = "task-" + routing_sha256[:24]
    decision_id = "routing-" + routing_sha256[:24]
    start_args = argparse.Namespace(**vars(args))
    start_args.goal_id = goal_id
    start_args.request_sha256 = request_sha256
    start_args.routing_decision_sha256 = routing_sha256
    start_args.authority_id = "codex-project-routing"
    start_args.source_id = "codex-project-routing"
    start_args.source_version = "v2"
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
