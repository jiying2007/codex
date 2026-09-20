"""Codex adapter for the canonical ADK Execution Policy v2 engine."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from .core import CodexAssetError
from .execution_policy.engine import (
    ExecutionPolicyError,
    evaluate,
    goal_intake_attestation_sha256,
    reduce_events,
    validate_policy,
)


UTC = timezone.utc
ENGINE_BASELINE = {
    "repository": "jiying2007/agent-dev-kit",
    "version": "7.0.4",
    "commit": "1d6c28e89eb98a4af5ac978707730783f0c84437",
    "engine_blob": "05dd80065ec4c58c342e48ff12d4cd53d3897740",
    "support_blob": "626af591141b2dda6302edbe4363637435066628",
}


class ExecutionPolicyAdapterError(CodexAssetError):
    """Raised when Codex runtime inputs or journal state violate Execution Policy."""


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_runtime_config(root: Path, config_path: str = "") -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve() if config_path else root / "manifests/execution_policy.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionPolicyAdapterError("unable to read runtime control manifest") from exc
    if not isinstance(value, dict) or set(value) != {"schema_version", "engine", "sources", "policy"}:
        raise ExecutionPolicyAdapterError("runtime control manifest fields are invalid")
    if value.get("schema_version") != 3:
        raise ExecutionPolicyAdapterError("unsupported runtime control manifest schema")
    engine = value.get("engine")
    expected_engine_fields = {"kind", "module", "contract", "behavior_baseline"}
    if not isinstance(engine, dict) or set(engine) != expected_engine_fields:
        raise ExecutionPolicyAdapterError("runtime control engine declaration is invalid")
    if engine.get("kind") != "codex-native":
        raise ExecutionPolicyAdapterError("runtime control engine must be codex-native")
    if engine.get("module") != "tools.codex_assets.execution_policy.engine":
        raise ExecutionPolicyAdapterError("runtime control native module drift")
    if engine.get("contract") != "runtime_control.policy/v2":
        raise ExecutionPolicyAdapterError("runtime control contract drift")
    if engine.get("behavior_baseline") != ENGINE_BASELINE:
        raise ExecutionPolicyAdapterError("runtime control behavior baseline drift")
    try:
        value["policy"] = validate_policy(value["policy"])
    except ExecutionPolicyError as exc:
        raise ExecutionPolicyAdapterError(str(exc)) from exc
    value["_path"] = str(path)
    value["_engine"] = "codex-native"
    return value


def _resolved_sources(config: Mapping[str, Any], codex_home: str = "") -> dict[str, Path]:
    sources = config.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"state_db", "sessions_root", "journal_dir"}:
        raise ExecutionPolicyAdapterError("runtime control sources are invalid")
    home = Path(codex_home).expanduser().resolve() if codex_home else Path("~/.codex").expanduser().resolve()

    def resolve(value: Any, default_name: str) -> Path:
        text = str(value or "")
        if text.startswith("~/.codex/"):
            return (home / text[len("~/.codex/"):]).resolve()
        if text == "~/.codex":
            return home
        if not text:
            return (home / default_name).resolve()
        return Path(text).expanduser().resolve()

    return {
        "state_db": resolve(sources.get("state_db"), "state_5.sqlite"),
        "sessions_root": resolve(sources.get("sessions_root"), "sessions"),
        "journal_dir": resolve(sources.get("journal_dir"), "execution-policy"),
    }


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ExecutionPolicyAdapterError("Codex state database is unavailable")
    return sqlite3.connect("file:{}?mode=ro".format(path), uri=True)


def active_thread(state_db: Path, thread_id: str = "") -> dict[str, Any]:
    try:
        with _connect_ro(state_db) as db:
            if thread_id:
                row = db.execute(
                    """
                    select id, coalesce(model, ''), rollout_path, cwd, updated_at
                    from threads where archived = 0 and id = ? limit 1
                    """,
                    (thread_id,),
                ).fetchone()
            else:
                row = db.execute(
                    """
                    select id, coalesce(model, ''), rollout_path, cwd, updated_at
                    from threads where archived = 0 order by updated_at desc limit 1
                    """
                ).fetchone()
    except sqlite3.Error as exc:
        raise ExecutionPolicyAdapterError("unable to read active Codex thread") from exc
    if row is None or not row[0] or not row[1] or not row[2] or not row[3]:
        raise ExecutionPolicyAdapterError("active Codex thread metadata is incomplete")
    return {
        "thread_id": str(row[0]),
        "model": str(row[1]),
        "rollout_path": str(row[2]),
        "cwd": str(row[3]),
        "updated_at": int(row[4] or 0),
    }


def latest_token_info(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ExecutionPolicyAdapterError("active rollout file is unavailable")
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        position = stream.tell()
        buffer = bytearray()
        while position > 0:
            step = min(position, 65536)
            position -= step
            stream.seek(position)
            buffer[:0] = stream.read(step)
            text = buffer.decode("utf-8", errors="replace")
            for line in reversed(text.splitlines()):
                if '"type":"token_count"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload") or {}
                if payload.get("type") == "token_count" and isinstance(payload.get("info"), dict):
                    return {"timestamp": record.get("timestamp"), "info": payload["info"]}
    raise ExecutionPolicyAdapterError("active rollout has no token_count record")


def usage_event(thread: Mapping[str, Any], *, rate_per_minute: float = 0.0) -> dict[str, Any]:
    token = latest_token_info(Path(str(thread["rollout_path"])))
    info = token.get("info") or {}
    total = info.get("total_token_usage") or {}
    last = info.get("last_token_usage") or {}
    input_tokens = int(total.get("input_tokens") or 0)
    output_tokens = int(total.get("output_tokens") or 0)
    total_tokens = int(total.get("total_tokens") or 0)
    if total_tokens != input_tokens + output_tokens:
        raise ExecutionPolicyAdapterError("Codex total token usage is inconsistent")
    now = _now()
    stable = "{}:{}:{}".format(thread["thread_id"], total_tokens, _iso(now))
    return {
        "schema_version": "runtime_control.event/v1",
        "event_id": "usage-{}".format(_sha256_text(stable)[:24]),
        "event_type": "usage.snapshot",
        "thread_id": thread["thread_id"],
        "observed_at": _iso(now),
        "payload": {
            "cwd_hash": _sha256_text(str(thread["cwd"])),
            "model": thread["model"],
            "input_tokens": input_tokens,
            "cached_input_tokens": int(total.get("cached_input_tokens") or 0),
            "output_tokens": output_tokens,
            "reasoning_tokens": int(total.get("reasoning_output_tokens") or 0),
            "total_tokens": total_tokens,
            "context_window": int(info.get("model_context_window") or 0),
            "last_input_tokens": int(last.get("input_tokens") or 0),
            "last_delta_tokens": int(last.get("total_tokens") or 0),
            "rate_per_minute": max(float(rate_per_minute), 0.0),
        },
    }


def _journal_path(journal_dir: Path, thread_id: str) -> Path:
    return journal_dir / ("thread-{}.jsonl".format(_sha256_text(thread_id)[:24]))


def load_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ExecutionPolicyAdapterError("journal line {} is not an object".format(line_number))
                events.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionPolicyAdapterError("runtime control journal is invalid") from exc
    return events


def _write_new_journal(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="." + path.name + ".", suffix=".tmp",
        dir=str(path.parent), delete=False,
    ) as stream:
        temp = Path(stream.name)
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp, 0o600)
    try:
        os.replace(str(temp), str(path))
    finally:
        temp.unlink(missing_ok=True)


def append_journal(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a+", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except OSError as exc:
        raise ExecutionPolicyAdapterError("unable to append runtime control journal") from exc


def control_event(kind: str, thread_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "runtime_control.event/v1",
        "event_id": "evt-{}".format(uuid.uuid4().hex),
        "event_type": kind,
        "thread_id": thread_id,
        "observed_at": _iso(_now()),
        "payload": dict(payload),
    }


def _goal_intake(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    artifact_mode = {
        "readonly": "readonly",
        "debugging": "readonly",
        "review": "readonly",
        "implementation": "implementation",
        "release": "release",
    }[args.task_mode]
    issued_at = args.issued_at or _iso(now)
    provenance = {
        "kind": "routing-decision",
        "source_id": args.source_id,
        "source_version": args.source_version,
        "decision_id": args.decision_id,
        "issued_at": issued_at,
    }
    intake = {
        "schema_version": "runtime_control.goal-intake/v1",
        "task_mode": args.task_mode,
        "artifact_mode": artifact_mode,
        "goal_id": args.goal_id,
        "request_sha256": args.request_sha256,
        "routing_decision_sha256": args.routing_decision_sha256,
        "authority_id": args.authority_id,
        "provenance": provenance,
    }
    intake["attestation_sha256"] = goal_intake_attestation_sha256(
        intake["task_mode"],
        intake["artifact_mode"],
        provenance,
        goal_id=intake["goal_id"],
        request_sha256=intake["request_sha256"],
        routing_decision_sha256=intake["routing_decision_sha256"],
        authority_id=intake["authority_id"],
    )
    return intake


def _engine_state(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    try:
        return reduce_events(events)
    except ExecutionPolicyError as exc:
        raise ExecutionPolicyAdapterError(str(exc)) from exc


def _decision(state: Mapping[str, Any], config: Mapping[str, Any], gate_event: str) -> dict[str, Any]:
    try:
        return evaluate(state, config["policy"], gate_event=gate_event)
    except ExecutionPolicyError as exc:
        raise ExecutionPolicyAdapterError(str(exc)) from exc


def snapshot(
    root: Path,
    config: Mapping[str, Any],
    *,
    codex_home: str = "",
    gate_event: str = "steady",
    rate_per_minute: float = 0.0,
    thread_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = _resolved_sources(config, codex_home)
    thread = active_thread(paths["state_db"], thread_id)
    journal = _journal_path(paths["journal_dir"], thread["thread_id"])
    events = load_journal(journal)
    events.append(usage_event(thread, rate_per_minute=rate_per_minute))
    state = _engine_state(events)
    return state, _decision(state, config, gate_event)


def _emit(value: Mapping[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _active_context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, Path], dict[str, Any], Path]:
    root = Path(args.root).expanduser().resolve()
    config = load_runtime_config(root, args.config)
    paths = _resolved_sources(config, args.codex_home)
    thread = active_thread(paths["state_db"], args.thread_id)
    journal = _journal_path(paths["journal_dir"], thread["thread_id"])
    return root, config, paths, thread, journal


def _append_action(args: argparse.Namespace, kind: str, payload: Mapping[str, Any]) -> int:
    root, config, _, thread, journal = _active_context(args)
    if not journal.is_file():
        raise ExecutionPolicyAdapterError("no active runtime control goal journal")
    append_journal(journal, control_event(kind, thread["thread_id"], payload))
    state, _ = snapshot(root, config, codex_home=args.codex_home, thread_id=args.thread_id)
    _emit(state)
    return 0


def run(args: argparse.Namespace) -> int:
    root, config, _, thread, journal = _active_context(args)
    action = args.runtime_action

    if action == "goal":
        if args.goal_action == "start":
            existing = load_journal(journal)
            if existing:
                state = _engine_state(existing + [usage_event(thread)])
                if state["goal"]["status"] == "active":
                    raise ExecutionPolicyAdapterError("one active goal already exists for this thread")
            baseline = usage_event(thread)["payload"]["total_tokens"]
            now = _now()
            started = {
                "schema_version": "runtime_control.event/v1",
                "event_id": "evt-{}".format(uuid.uuid4().hex),
                "event_type": "goal.started",
                "thread_id": thread["thread_id"],
                "observed_at": _iso(now),
                "payload": {
                    "goal_id": args.goal_id,
                    "token_budget": args.token_budget,
                    "time_budget_seconds": args.time_budget_seconds,
                    "usage_baseline_tokens": baseline,
                    "success_criteria": args.success_criterion,
                    "required_evidence": args.required_evidence,
                    "open_items_count": args.open_items,
                    "intake": _goal_intake(args, now),
                },
            }
            _write_new_journal(journal, started)
        elif args.goal_action == "update":
            payload = {
                key: value for key, value in {
                    "open_items_count": args.open_items,
                    "token_budget": args.token_budget,
                    "time_budget_seconds": args.time_budget_seconds,
                }.items() if value is not None
            }
            if not payload:
                raise ExecutionPolicyAdapterError("goal update requires at least one field")
            return _append_action(args, "goal.updated", payload)
        elif args.goal_action == "complete":
            return _append_action(args, "goal.completed", {})
        elif args.goal_action == "abort":
            return _append_action(args, "goal.aborted", {})
        state, _ = snapshot(root, config, codex_home=args.codex_home, thread_id=args.thread_id)
        _emit(state)
        return 0

    if action == "progress":
        return _append_action(args, "progress.advanced", {"revision": args.revision})
    if action == "heartbeat":
        return _append_action(args, "heartbeat.recorded", {})
    if action == "retry":
        return _append_action(args, "retry.recorded", {"reason_id": args.reason_id})
    if action == "evidence":
        return _append_action(args, "evidence.added", {"evidence_id": args.evidence_id, "sha256": args.sha256})
    if action == "checkpoint":
        return _append_action(args, "checkpoint.verified", {
            "revision": args.revision, "evidence_ids": args.evidence_id,
        })
    if action == "artifact":
        return _append_action(args, "artifact.verified", {
            "artifact_type": args.artifact_type, "evidence_id": args.evidence_id,
        })
    if action == "snapshot":
        _, decision = snapshot(
            root, config, codex_home=args.codex_home, gate_event=args.event, thread_id=args.thread_id
        )
        _emit(decision)
        return 0
    if action == "gate":
        _, decision = snapshot(root, config, codex_home=args.codex_home, gate_event=args.event, thread_id=args.thread_id)
        _emit(decision)
        return 0 if decision["gate_allowed"] else 3
    if action == "watch":
        previous_total: Optional[int] = None
        previous_time: Optional[float] = None
        iterations = args.iterations
        count = 0
        while iterations == 0 or count < iterations:
            started = time.monotonic()
            current = usage_event(thread)
            total = int(current["payload"]["total_tokens"])
            rate = 0.0
            if previous_total is not None and previous_time is not None and started > previous_time and total >= previous_total:
                rate = (total - previous_total) * 60.0 / (started - previous_time)
            _, decision = snapshot(
                root, config, codex_home=args.codex_home, gate_event=args.event, rate_per_minute=rate,
                thread_id=args.thread_id,
            )
            _emit(decision)
            previous_total = total
            previous_time = started
            count += 1
            if iterations == 0 or count < iterations:
                time.sleep(max(args.interval, 1.0))
        return 0
    raise ExecutionPolicyAdapterError("unsupported runtime-control action")


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="")
    parser.add_argument("--codex-home", default="~/.codex")
    parser.add_argument("--thread-id", default=os.environ.get("CODEX_THREAD_ID", ""))
    sub = parser.add_subparsers(dest="runtime_action", required=True)

    goal = sub.add_parser("goal")
    goal_sub = goal.add_subparsers(dest="goal_action", required=True)
    start = goal_sub.add_parser("start")
    start.add_argument("--goal-id", required=True)
    start.add_argument("--token-budget", type=int, required=True)
    start.add_argument("--time-budget-seconds", type=int, required=True)
    start.add_argument("--success-criterion", action="append", required=True)
    start.add_argument("--required-evidence", action="append", required=True)
    start.add_argument("--open-items", type=int, required=True)
    start.add_argument("--task-mode", choices=["readonly", "implementation", "debugging", "review", "release"], required=True)
    start.add_argument("--request-sha256", required=True)
    start.add_argument("--routing-decision-sha256", required=True)
    start.add_argument("--authority-id", required=True)
    start.add_argument("--decision-id", required=True)
    start.add_argument("--source-id", required=True)
    start.add_argument("--source-version", required=True)
    start.add_argument("--issued-at", default="")
    update = goal_sub.add_parser("update")
    update.add_argument("--open-items", type=int)
    update.add_argument("--token-budget", type=int)
    update.add_argument("--time-budget-seconds", type=int)
    goal_sub.add_parser("complete")
    goal_sub.add_parser("abort")
    goal_sub.add_parser("status")

    progress = sub.add_parser("progress")
    progress.add_argument("--revision", type=int, required=True)
    sub.add_parser("heartbeat")
    retry = sub.add_parser("retry")
    retry.add_argument("--reason-id", required=True)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--evidence-id", required=True)
    evidence.add_argument("--sha256", required=True)
    checkpoint = sub.add_parser("checkpoint")
    checkpoint.add_argument("--revision", type=int, required=True)
    checkpoint.add_argument("--evidence-id", action="append", required=True)
    artifact = sub.add_parser("artifact")
    artifact.add_argument("--artifact-type", required=True, choices=["repo", "build", "plan", "dry-run", "live", "review"])
    artifact.add_argument("--evidence-id", required=True)
    snapshot_parser = sub.add_parser("snapshot")
    snapshot_parser.add_argument("--event", default="steady", choices=["steady", "final", "commit", "apply", "release"])
    gate = sub.add_parser("gate")
    gate.add_argument("--event", required=True, choices=["final", "commit", "apply", "release"])
    watch = sub.add_parser("watch")
    watch.add_argument("--event", default="steady", choices=["steady", "final", "commit", "apply", "release"])
    watch.add_argument("--interval", type=float, default=3.0)
    watch.add_argument("--iterations", type=int, default=0)
