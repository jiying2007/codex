"""Exact native Codex CLI receipt parsing and no-model capability checks."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from typing import Tuple

from .models import IntakeRejected


def parse_exec_turn(stdout: str) -> Tuple[str, str]:
    """Read native codex exec --json receipts without exposing tool logs.

    A canonical persistent thread ID and one successful terminal turn are
    required; an incomplete or failed receipt must never trigger a retry.
    """
    if not isinstance(stdout, str) or not stdout or len(stdout) > 16 * 1024 * 1024:
        raise IntakeRejected("Codex JSONL receipt is missing or exceeds the limit")
    thread_id = ""
    started = completed = False
    final_text = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError) as exc:
            raise IntakeRejected("invalid Codex JSONL receipt") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise IntakeRejected("invalid Codex JSONL event")
        kind = event["type"]
        if completed or kind in ("error", "turn.failed"):
            raise IntakeRejected("Codex JSONL turn is failed or ambiguous")
        if not thread_id and kind != "thread.started":
            raise IntakeRejected("Codex thread identity must precede turn events")
        if kind == "thread.started":
            value = event.get("thread_id")
            if thread_id or not isinstance(value, str):
                raise IntakeRejected("ambiguous Codex thread identity")
            try:
                if str(uuid.UUID(value)) != value:
                    raise ValueError("non-canonical UUID")
            except (ValueError, AttributeError) as exc:
                raise IntakeRejected("invalid native Codex thread ID") from exc
            thread_id = value
        elif kind == "turn.started":
            if started:
                raise IntakeRejected("multiple Codex turns in one receipt")
            started = True
        elif kind == "turn.completed":
            if not started:
                raise IntakeRejected("Codex turn completed without start")
            completed = True
        elif kind == "item.completed":
            item = event.get("item")
            if (started and isinstance(item, dict)
                    and item.get("type") == "agent_message"
                    and isinstance(item.get("text"), str)):
                final_text = item["text"]
    if not (thread_id and started and completed):
        raise IntakeRejected("Codex JSONL terminal receipt is incomplete")
    return thread_id, final_text


def probe_local_cli(executable: str = "codex", timeout: int = 5) -> dict:
    """Read installed CLI help/version only; never start a thread or turn."""
    if not isinstance(executable, str) or not executable or "/" in executable:
        raise IntakeRejected("probe requires a PATH executable name")
    if not 1 <= timeout <= 10:
        raise IntakeRejected("probe timeout out of bounds")
    results = {}
    for key, argv in (
        ("version", [executable, "--version"]),
        ("exec_help", [executable, "exec", "--help"]),
        ("exec_resume_help", [executable, "exec", "resume", "--help"]),
    ):
        try:
            process = subprocess.run(
                argv, check=False, capture_output=True, text=True,
                timeout=timeout,
                env={k: v for k, v in os.environ.items()
                     if k in ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE",
                              "TERM", "CODEX_HOME")},
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            return {"available": False, "failed_step": key,
                    "reason": type(exc).__name__}
        if process.returncode != 0:
            return {"available": False, "failed_step": key,
                    "reason": "nonzero_exit"}
        results[key] = process.stdout[:512] or process.stderr[:512]
    return {"available": True, "details": results,
            "qualified_for_model_calls": False}
