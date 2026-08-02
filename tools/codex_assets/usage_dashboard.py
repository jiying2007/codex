from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import sqlite3
import sys
import termios
import time
import tty
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence


UTC = timezone.utc


@dataclass
class ThreadRow:
    thread_id: str
    cwd: str
    title: str
    model: str
    reasoning_effort: str
    tokens_used: int
    updated_at: int
    rollout_path: str


@dataclass
class GoalRow:
    thread_id: str
    status: str
    token_budget: int | None
    tokens_used: int
    time_used_seconds: int


def base_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    parser.add_argument("--state-db", default="")
    parser.add_argument("--sessions-root", default="")
    parser.add_argument("--view", default="summary", choices=["summary", "threads", "trends", "auto"])
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--top-models", type=int, default=5)
    parser.add_argument("--top-repos", type=int, default=5)
    parser.add_argument("--thread-sort", default="updated", choices=["updated", "tokens", "model", "repo"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--warn-thread-tokens", type=int, default=50_000_000)
    return parser


def connect_ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    codex_home = Path(args.codex_home).expanduser().resolve()
    state_db = Path(args.state_db).expanduser() if args.state_db else codex_home / "state_5.sqlite"
    sessions_root = Path(args.sessions_root).expanduser() if args.sessions_root else codex_home / "sessions"
    return state_db.resolve(), sessions_root.resolve()


def load_threads(state_db: Path, limit: int) -> list[ThreadRow]:
    with connect_ro(state_db) as db:
        rows = db.execute(
            """
            select id, title, coalesce(model, ''), coalesce(reasoning_effort, ''),
                   tokens_used, updated_at, rollout_path, cwd
            from threads
            where archived = 0
            order by updated_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return [
        ThreadRow(
            thread_id=row[0],
            title=row[1],
            model=row[2],
            reasoning_effort=row[3],
            tokens_used=int(row[4] or 0),
            updated_at=int(row[5] or 0),
            rollout_path=row[6] or "",
            cwd=row[7] or "",
        )
        for row in rows
    ]


def load_goals(state_db: Path) -> tuple[dict[str, GoalRow], bool]:
    with connect_ro(state_db) as db:
        table = db.execute(
            "select 1 from sqlite_master where type = 'table' and name = ?",
            ("thread_goals",),
        ).fetchone()
        if table is None:
            return {}, False
        rows = db.execute(
            """
            select thread_id, status, token_budget, tokens_used, time_used_seconds
            from thread_goals
            order by updated_at_ms desc
            """
        ).fetchall()
    out: dict[str, GoalRow] = {}
    for row in rows:
        thread_id = row[0]
        if thread_id in out:
            continue
        out[thread_id] = GoalRow(
            thread_id=thread_id,
            status=row[1],
            token_budget=row[2],
            tokens_used=int(row[3] or 0),
            time_used_seconds=int(row[4] or 0),
        )
    return out, True


def latest_token_count(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        buf = bytearray()
        pos = size
        while pos > 0:
            step = min(65536, pos)
            pos -= step
            fh.seek(pos)
            buf[:0] = fh.read(step)
            text = buf.decode("utf-8", errors="replace")
            for line in reversed(text.splitlines()):
                if '"type":"token_count"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload", {})
                if payload.get("type") == "token_count":
                    return {
                        "timestamp": record.get("timestamp", ""),
                        "info": payload.get("info", {}),
                        "rate_limits": payload.get("rate_limits", {}),
                    }
    return {}


def day_session_paths(root: Path, day: datetime) -> list[Path]:
    base = root / day.strftime("%Y") / day.strftime("%m") / day.strftime("%d")
    return sorted(base.glob("*.jsonl")) if base.is_dir() else []


def recent_rollout_paths(state_db: Path, cutoff_epoch: int) -> list[Path]:
    with connect_ro(state_db) as db:
        rows = db.execute(
            """
            select rollout_path
            from threads
            where archived = 0 and updated_at >= ?
            order by updated_at desc
            """,
            (cutoff_epoch,),
        ).fetchall()
    return [Path(row[0]) for row in rows if row[0]]


def session_delta_rows(root: Path, state_db: Path, days: int) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days - 1)
    candidates = {
        path
        for offset in range(days)
        for path in day_session_paths(root, now - timedelta(days=offset))
    }
    candidates.update(recent_rollout_paths(state_db, int(cutoff.timestamp())))

    rows: list[dict[str, Any]] = []
    for path in sorted(candidates):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"type":"token_count"' not in line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = record.get("payload", {})
                    if payload.get("type") != "token_count":
                        continue
                    ts = record.get("timestamp", "")
                    if not ts:
                        continue
                    event_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
                    if event_dt < cutoff:
                        continue
                    delta = (((payload.get("info") or {}).get("last_token_usage") or {}).get("total_tokens"))
                    if delta is None:
                        continue
                    rows.append(
                        {
                            "date": event_dt.strftime("%Y-%m-%d"),
                            "path": str(path),
                            "delta_tokens": int(delta),
                        }
                    )
        except OSError:
            continue
    return rows


def summarize_sessions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, int] = {}
    for row in rows:
        by_day[row["date"]] = by_day.get(row["date"], 0) + row["delta_tokens"]
    ordered_days = sorted(by_day.items(), reverse=True)
    return {
        "today_total": ordered_days[0][1] if ordered_days else 0,
        "week_total": sum(value for _, value in ordered_days[:7]),
        "by_day": ordered_days,
    }


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_tokens_m(value: int) -> str:
    return f"{value / 1_000_000:.1f}M"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def short_text(value: str, width: int = 96) -> str:
    text = (value or "").strip()
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def sparkline(values: Sequence[int]) -> str:
    if not values:
        return "-"
    levels = " .:-=+*#%@"
    peak = max(values)
    if peak <= 0:
        return levels[0] * len(values)
    chars: list[str] = []
    last = len(levels) - 1
    for value in values:
        idx = round((value / peak) * last)
        chars.append(levels[max(0, min(last, idx))])
    return "".join(chars)


def short_repo(value: str) -> str:
    path = normalize_repo_path(value)
    if not path:
        return "-"
    parts = [part for part in path.split("/") if part]
    if len(parts) <= 3:
        return path
    return "/".join(parts[-3:])


def normalize_repo_path(value: str) -> str:
    path = (value or "").strip().replace("\\", "/")
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) >= 2 and path[1] == ":":
        path = path[0].lower() + path[1:]
    return path.rstrip("/") if path not in {"/", ""} else path


def fmt_ts(epoch_seconds: int) -> str:
    if not epoch_seconds:
        return "-"
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def term_size() -> os.terminal_size:
    return shutil.get_terminal_size((120, 32))


def effective_view(view: str, rows: int) -> str:
    if view != "auto":
        return view
    if rows < 26:
        return "summary"
    if rows < 38:
        return "trends"
    return "threads"


def snapshot_metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    active = snapshot.get("active_thread") or {}
    token = snapshot.get("active_token_count") or {}
    info = token.get("info") or {}
    total_usage = info.get("total_token_usage") or {}
    last_usage = info.get("last_token_usage") or {}
    context_window = int(info.get("model_context_window") or 0)
    input_tokens = int(total_usage.get("input_tokens") or 0)
    cached_tokens = int(total_usage.get("cached_input_tokens") or 0)
    total_tokens = int(total_usage.get("total_tokens") or active.get("tokens_used") or 0)
    last_input_tokens = int(last_usage.get("input_tokens") or 0)
    output_tokens = int(total_usage.get("output_tokens") or 0)
    reasoning_tokens = int(total_usage.get("reasoning_output_tokens") or 0)
    return {
        "active_total_tokens": total_tokens,
        "last_delta_tokens": int(last_usage.get("total_tokens") or 0),
        "last_input_tokens": last_input_tokens,
        "cache_hit_ratio": (cached_tokens / input_tokens) if input_tokens > 0 else 0.0,
        "context_window": context_window,
        "last_input_ratio": (last_input_tokens / context_window) if context_window > 0 else 0.0,
        "reasoning_ratio": (reasoning_tokens / output_tokens) if output_tokens > 0 else 0.0,
    }


def aggregate_threads(threads: list[dict[str, Any]], key: str, fallback: str = "-") -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in threads:
        raw = (row.get(key) or "").strip()
        name = raw if raw else fallback
        if key == "cwd":
            name = short_repo(name)
        item = grouped.setdefault(name, {"name": name, "tokens_used": 0, "threads": 0})
        item["tokens_used"] += int(row.get("tokens_used") or 0)
        item["threads"] += 1
    return sorted(grouped.values(), key=lambda item: item["tokens_used"], reverse=True)


def sort_threads(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    items = list(rows)
    if mode == "tokens":
        return sorted(items, key=lambda row: (-(int(row.get("tokens_used") or 0)), row.get("updated_at_text", "")))
    if mode == "model":
        return sorted(items, key=lambda row: ((row.get("model") or "-"), -(int(row.get("tokens_used") or 0))))
    if mode == "repo":
        return sorted(items, key=lambda row: (short_repo(row.get("cwd") or "-"), -(int(row.get("tokens_used") or 0))))
    return sorted(items, key=lambda row: row.get("updated_at_text", ""), reverse=True)


def fixed_context_projection(codex_home: Path, cwd: Path | None) -> dict[str, Any]:
    candidates: list[tuple[str, Path]] = [("global-instructions", codex_home / "AGENTS.md")]
    if cwd is not None:
        resolved = cwd.expanduser().resolve()
        candidates.extend(("workspace-instructions", parent / "AGENTS.md") for parent in reversed((resolved, *resolved.parents)))
    seen: set[Path] = set()
    components: list[dict[str, Any]] = []
    for kind, path in candidates:
        resolved_path = path.resolve()
        if resolved_path in seen or not resolved_path.is_file():
            continue
        seen.add(resolved_path)
        byte_count = resolved_path.stat().st_size
        components.append(
            {
                "kind": kind,
                "path": str(resolved_path),
                "bytes": byte_count,
                "estimated_tokens": (byte_count + 3) // 4,
            }
        )
    total_bytes = sum(int(item["bytes"]) for item in components)
    return {
        "schema_version": 1,
        "projection": "fixed-context-cost-v1",
        "status": "estimate",
        "estimation_method": "utf8-bytes-ceil-div-4",
        "components": components,
        "total_bytes": total_bytes,
        "estimated_tokens": (total_bytes + 3) // 4,
        "excluded_variable_costs": [
            "conversation-history",
            "tool-results",
            "knowledge-hub-payloads",
            "loaded-skill-bodies",
        ],
    }


def current_snapshot(state_db: Path, sessions_root: Path, limit: int, top_models: int, top_repos: int) -> dict[str, Any]:
    threads = load_threads(state_db, limit)
    goals, goals_available = load_goals(state_db)
    active = threads[0] if threads else None
    token = latest_token_count(Path(active.rollout_path)) if active and active.rollout_path else {}
    summary = summarize_sessions(session_delta_rows(sessions_root, state_db, 7))
    snapshot = {
        "state_db": str(state_db),
        "sessions_root": str(sessions_root),
        "capabilities": {
            "thread_goals": {
                "available": goals_available,
                "source": "state-db",
            }
        },
        "active_thread": active.__dict__ if active else None,
        "active_goal": goals.get(active.thread_id).__dict__ if active and active.thread_id in goals else None,
        "active_token_count": token,
        "context_cost_projection": fixed_context_projection(
            state_db.parent, Path(active.cwd) if active and active.cwd else None
        ),
        "threads": [
            {
                **row.__dict__,
                "updated_at_text": fmt_ts(row.updated_at),
                "goal": goals.get(row.thread_id).__dict__ if row.thread_id in goals else None,
            }
            for row in threads
        ],
        "session_summary": summary,
    }
    snapshot["derived"] = snapshot_metrics(snapshot)
    snapshot["top_models"] = aggregate_threads(snapshot["threads"], "model")[:top_models]
    snapshot["top_repos"] = aggregate_threads(snapshot["threads"], "cwd")[:top_repos]
    return snapshot


def recent_window_summary(root: Path, state_db: Path, minutes: int = 30, top_models: int = 5, top_repos: int = 5) -> dict[str, Any]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    candidates = recent_rollout_paths(state_db, int(cutoff.timestamp()))
    total = 0
    by_model: dict[str, int] = {}
    by_repo: dict[str, int] = {}
    thread_meta: dict[str, tuple[str, str]] = {}
    for row in load_threads(state_db, 200):
        thread_meta[row.rollout_path] = (row.model or "-", short_repo(row.cwd))
    for path in candidates:
        if not path.is_file():
            continue
        model, repo = thread_meta.get(str(path), ("-", "-"))
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"type":"token_count"' not in line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = record.get("payload", {})
                    if payload.get("type") != "token_count":
                        continue
                    ts = record.get("timestamp", "")
                    if not ts:
                        continue
                    event_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
                    if event_dt < cutoff:
                        continue
                    delta = int((((payload.get("info") or {}).get("last_token_usage") or {}).get("total_tokens")) or 0)
                    total += delta
                    by_model[model] = by_model.get(model, 0) + delta
                    by_repo[repo] = by_repo.get(repo, 0) + delta
        except OSError:
            continue
    return {
        "minutes": minutes,
        "total_tokens": total,
        "rate_per_min": (total / minutes) if minutes > 0 else 0.0,
        "top_models": [{"name": name, "tokens": value} for name, value in sorted(by_model.items(), key=lambda item: item[1], reverse=True)[:top_models]],
        "top_repos": [{"name": name, "tokens": value} for name, value in sorted(by_repo.items(), key=lambda item: item[1], reverse=True)[:top_repos]],
    }


def recent_windows_summary(root: Path, state_db: Path, windows: Sequence[int], top_models: int, top_repos: int) -> dict[str, Any]:
    return {
        str(minutes): recent_window_summary(root, state_db, minutes=minutes, top_models=top_models, top_repos=top_repos)
        for minutes in windows
    }


def recent_bucket_series(root: Path, state_db: Path, minutes: int = 30, bucket_minutes: int = 5) -> dict[str, Any]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    candidates = recent_rollout_paths(state_db, int(cutoff.timestamp()))
    bucket_count = max(1, minutes // bucket_minutes)
    values = [0 for _ in range(bucket_count)]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"type":"token_count"' not in line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = record.get("payload", {})
                    if payload.get("type") != "token_count":
                        continue
                    ts = record.get("timestamp", "")
                    if not ts:
                        continue
                    event_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
                    if event_dt < cutoff:
                        continue
                    age_minutes = (now - event_dt).total_seconds() / 60.0
                    idx = bucket_count - 1 - int(age_minutes // bucket_minutes)
                    if idx < 0 or idx >= bucket_count:
                        continue
                    delta = int((((payload.get("info") or {}).get("last_token_usage") or {}).get("total_tokens")) or 0)
                    values[idx] += delta
        except OSError:
            continue
    return {
        "minutes": minutes,
        "bucket_minutes": bucket_minutes,
        "values": values,
        "sparkline": sparkline(values),
    }


def add_alert(
    items: list[dict[str, Any]],
    severity: str,
    code: str,
    summary: str,
    action: str,
    evidence: dict[str, Any],
) -> None:
    items.append(
        {
            "severity": severity,
            "code": code,
            "summary": summary,
            "action": action,
            "evidence": evidence,
        }
    )


def alert_severity_rank(value: str) -> int:
    return {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "INFO": 0}.get(value, 0)


def status_from_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "STABLE"
    top = max(alert_severity_rank(item["severity"]) for item in alerts)
    return {3: "CRITICAL", 2: "HOT", 1: "WATCH", 0: "INFO"}.get(top, "WATCH")


def advisory_lines(snapshot: dict[str, Any], warn_thread_tokens: int, tail_rate_per_min: float = 0.0, warn_rate_per_min: int = 120_000) -> list[dict[str, Any]]:
    derived = snapshot.get("derived") or snapshot_metrics(snapshot)
    recent = snapshot.get("recent_window") or {}
    recent_windows = snapshot.get("recent_windows") or {}
    top_repos = snapshot.get("top_repos") or []
    top_models = snapshot.get("top_models") or []
    lines: list[dict[str, Any]] = []
    active_total = int(derived.get("active_total_tokens") or 0)
    last_delta = int(derived.get("last_delta_tokens") or 0)
    last_input_ratio = float(derived.get("last_input_ratio") or 0.0)
    cache_hit_ratio = float(derived.get("cache_hit_ratio") or 0.0)
    recent_total = int(recent.get("total_tokens") or 0)
    rate_5 = float((recent_windows.get("5") or {}).get("rate_per_min") or 0.0)
    rate_15 = float((recent_windows.get("15") or {}).get("rate_per_min") or 0.0)
    rate_30 = float((recent_windows.get("30") or {}).get("rate_per_min") or 0.0)
    if active_total >= warn_thread_tokens:
        add_alert(
            lines,
            "CRITICAL" if active_total >= warn_thread_tokens * 2 else "HIGH",
            "THREAD_LONG",
            f"当前线程已累计 {fmt_tokens_m(active_total)}，属于长线程高风险区。",
            "立即收口：context-preflight -> session-wrap -> archive-note -> memory-curator --dry-run，然后新开线程。",
            {
                "active_total_tokens": active_total,
                "warn_thread_tokens": warn_thread_tokens,
            },
        )
    if tail_rate_per_min >= warn_rate_per_min:
        add_alert(
            lines,
            "HIGH",
            "RATE_SPIKE",
            f"当前增速约 {fmt_tokens_m(int(tail_rate_per_min))}/min，已进入高增速区。",
            "暂停扩范围操作；不要新增并行 agent，只保留定向读取和局部 diff。",
            {
                "tail_rate_per_min": tail_rate_per_min,
                "warn_rate_per_min": warn_rate_per_min,
                "rate_5_per_min": rate_5,
                "rate_15_per_min": rate_15,
                "rate_30_per_min": rate_30,
            },
        )
    elif last_delta >= warn_rate_per_min:
        add_alert(
            lines,
            "MEDIUM",
            "DELTA_LARGE",
            f"最近一次 delta={fmt_tokens_m(last_delta)}，存在单次读入过大风险。",
            "回看最近命令，优先检查长日志、大 diff、大 JSON、全仓扫描结果。",
            {
                "last_delta_tokens": last_delta,
                "warn_rate_per_min": warn_rate_per_min,
            },
        )
    if rate_5 > 0 and rate_15 > 0 and rate_5 >= rate_15 * 1.5:
        add_alert(
            lines,
            "HIGH" if rate_5 >= warn_rate_per_min else "MEDIUM",
            "ACCELERATING",
            f"近 5 分钟速率 {fmt_tokens_m(int(rate_5))}/min，明显高于 15 分钟均值 {fmt_tokens_m(int(rate_15))}/min，处于加速态。",
            "先停新增上下文，再判断是否需要拆线程或降模型/降推理强度。",
            {
                "rate_5_per_min": rate_5,
                "rate_15_per_min": rate_15,
                "rate_30_per_min": rate_30,
                "acceleration_ratio": (rate_5 / rate_15) if rate_15 > 0 else None,
            },
        )
    if last_input_ratio >= 0.25:
        add_alert(
            lines,
            "HIGH" if last_input_ratio >= 0.40 else "MEDIUM",
            "CTX_PRESSURE",
            f"最近一次输入已占 context window 的 {fmt_pct(last_input_ratio)}。",
            "不要继续往同线程堆背景；改成更窄的问题陈述，必要时切新线程。",
            {
                "last_input_ratio": last_input_ratio,
                "last_input_tokens": int(derived.get("last_input_tokens") or 0),
                "context_window": int(derived.get("context_window") or 0),
            },
        )
    if cache_hit_ratio < 0.70:
        add_alert(
            lines,
            "MEDIUM",
            "CACHE_LOW",
            f"Cache Hit 仅 {fmt_pct(cache_hit_ratio)}，重复上下文复用偏低。",
            "减少重复叙述和大段工具输出，尽量用更小的增量问题推进。",
            {
                "cache_hit_ratio": cache_hit_ratio,
            },
        )
    if recent_total > 0 and top_repos:
        top_repo = top_repos[0]
        repo_tokens = int(top_repo.get("tokens_used") or 0)
        if repo_tokens > 0:
            add_alert(
                lines,
                "INFO",
                "HOT_REPO",
                f"当前主要消耗集中在 repo `{top_repo.get('name', '-')}`。",
                "如果这不是当前最重要的问题，立刻拆线程，避免继续把 token 烧在错误工作流上。",
                {
                    "top_repo": top_repo.get("name", "-"),
                    "top_repo_tokens": repo_tokens,
                },
            )
    if recent_total > 0 and top_models:
        top_model = top_models[0]
        add_alert(
            lines,
            "INFO",
            "HOT_MODEL",
            f"当前累计最高的是 `{top_model.get('name', '-')}`（{fmt_tokens_m(int(top_model.get('tokens_used') or 0))}）。",
            "如果只是整理/归档/总结，考虑切到更省的模型或更低推理强度。",
            {
                "top_model": top_model.get("name", "-"),
                "top_model_tokens": int(top_model.get("tokens_used") or 0),
            },
        )
    lines.sort(key=lambda item: (-alert_severity_rank(item["severity"]), item["code"]))
    return lines


def output_trim_playbook(alerts: list[dict[str, Any]]) -> list[str]:
    codes = {item.get("code", "") for item in alerts}
    steps: list[str] = []
    if "THREAD_LONG" in codes or "CTX_PRESSURE" in codes:
        steps.append("先收口当前线程；新问题改为新线程，不继续堆背景。")
    if "RATE_SPIKE" in codes or "ACCELERATING" in codes:
        steps.append("暂停扩范围读取；只保留定向 rg、局部 sed -n、短窗口 tail。")
    if "DELTA_LARGE" in codes:
        steps.append("大日志只看错误窗口；大 diff 先看 --stat；大 JSON 只筛关键字段。")
    if "CACHE_LOW" in codes:
        steps.append("减少重复解释和工具输出复述；下一轮只提交增量问题。")
    if not steps:
        steps.append("默认先缩范围再展开：先摘要、后片段、最后才看全文。")
    deduped: list[str] = []
    for item in steps:
        if item not in deduped:
            deduped.append(item)
    return deduped[:3]


def likely_operation_causes(snapshot: dict[str, Any], alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    derived = snapshot.get("derived") or snapshot_metrics(snapshot)
    recent = snapshot.get("recent_window") or {}
    recent_windows = snapshot.get("recent_windows") or {}
    top_repos = snapshot.get("top_repos") or []
    codes = {item.get("code", "") for item in alerts}
    causes: list[dict[str, Any]] = []
    active_total = int(derived.get("active_total_tokens") or 0)
    last_delta = int(derived.get("last_delta_tokens") or 0)
    cache_hit_ratio = float(derived.get("cache_hit_ratio") or 0.0)
    last_input_ratio = float(derived.get("last_input_ratio") or 0.0)
    rate_5 = float((recent_windows.get("5") or {}).get("rate_per_min") or 0.0)
    rate_15 = float((recent_windows.get("15") or {}).get("rate_per_min") or 0.0)
    recent_total = int(recent.get("total_tokens") or 0)

    def add(cause: str, confidence: str, summary: str, evidence: dict[str, Any]) -> None:
        causes.append(
            {
                "cause": cause,
                "confidence": confidence,
                "summary": summary,
                "evidence": evidence,
            }
        )

    if "THREAD_LONG" in codes and active_total > 0:
        add(
            "long_thread_rollup",
            "high",
            "主要消耗来自长线程持续滚大上下文，而不是单次异常读入。",
            {"active_total_tokens": active_total},
        )
    if "DELTA_LARGE" in codes:
        add(
            "large_read_payload",
            "medium",
            "最近一次读入偏大，常见于长日志、大 diff 或大 JSON 直接进入上下文。",
            {"last_delta_tokens": last_delta},
        )
    if "RATE_SPIKE" in codes or "ACCELERATING" in codes:
        add(
            "repo_wide_scan_or_broad_read",
            "medium",
            "短时间内速率明显抬升，常见于扩范围搜索、批量读文件或大输出工具结果。",
            {"rate_5_per_min": rate_5, "rate_15_per_min": rate_15},
        )
    if "CTX_PRESSURE" in codes and "CACHE_LOW" in codes:
        add(
            "repeated_background_restatement",
            "medium",
            "上下文压力和低缓存命中同时出现，说明重复背景和重复解释占比偏高。",
            {"last_input_ratio": last_input_ratio, "cache_hit_ratio": cache_hit_ratio},
        )
    if recent_total > 0 and top_repos:
        top_repo = top_repos[0]
        top_repo_tokens = int(top_repo.get("tokens_used") or 0)
        if top_repo_tokens > 0 and top_repo_tokens >= max(recent_total, 1):
            add(
                "single_repo_concentration",
                "low",
                "消耗高度集中在单一 repo，可能在错误工作流上持续投入了读取和解释成本。",
                {"top_repo": top_repo.get("name", "-"), "top_repo_tokens": top_repo_tokens, "recent_total_tokens": recent_total},
            )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in causes:
        key = str(item.get("cause"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:3]


def render_summary(snapshot: dict[str, Any], warn_thread_tokens: int, tail_rate_per_min: float = 0.0) -> str:
    active = snapshot.get("active_thread") or {}
    goal = snapshot.get("active_goal") or {}
    token = snapshot.get("active_token_count") or {}
    info = token.get("info") or {}
    total_usage = info.get("total_token_usage") or {}
    rates = token.get("rate_limits") or {}
    primary = rates.get("primary") or {}
    secondary = rates.get("secondary") or {}
    summary = snapshot.get("session_summary") or {}
    derived = snapshot.get("derived") or snapshot_metrics(snapshot)
    recent = snapshot.get("recent_window") or {}
    buckets = snapshot.get("recent_buckets") or {}
    recent_windows = snapshot.get("recent_windows") or {}
    top_models = snapshot.get("top_models") or []
    top_repos = snapshot.get("top_repos") or []
    model_line = " | ".join(
        f"{item.get('name', '-')}: {fmt_tokens_m(int(item.get('tokens_used') or 0))}"
        for item in top_models[:2]
    ) or "-"
    repo_line = " | ".join(
        f"{item.get('name', '-')}: {fmt_tokens_m(int(item.get('tokens_used') or 0))}"
        for item in top_repos[:2]
    ) or "-"
    rate_chunks = []
    for key in ["5", "15", "30"]:
        item = recent_windows.get(key)
        if item:
            rate_chunks.append(f"{key}m {fmt_tokens_m(int(item.get('rate_per_min') or 0))}/min")
    advisories = advisory_lines(snapshot, warn_thread_tokens, tail_rate_per_min=tail_rate_per_min)
    status = status_from_alerts(advisories)
    playbook = output_trim_playbook(advisories)
    causes = likely_operation_causes(snapshot, advisories)
    lines = [
        "Codex Usage Dashboard",
        f"Status        : {status}",
        f"Active Thread : {active.get('thread_id', '-')}",
        f"Title         : {short_text(active.get('title', '-'))}",
        f"Model/Reason  : {(active.get('model', '-') or '-')} / {(active.get('reasoning_effort', '-') or '-')} / {fmt_ts(int(active.get('updated_at') or 0))}",
        f"Session/Delta : {fmt_tokens_m(int(derived.get('active_total_tokens') or 0))} / {fmt_tokens_m(int(derived.get('last_delta_tokens') or 0))}",
        f"Rate Limits   : P {primary.get('used_percent', '-') if primary else '-'}% | S {secondary.get('used_percent', '-') if secondary else '-'}%",
        f"Input/Cached  : {fmt_tokens_m(int(total_usage.get('input_tokens') or 0))} / {fmt_tokens_m(int(total_usage.get('cached_input_tokens') or 0))}",
        f"Output/Think  : {fmt_tokens_m(int(total_usage.get('output_tokens') or 0))} / {fmt_tokens_m(int(total_usage.get('reasoning_output_tokens') or 0))}",
        f"Cache/Ctx/Live: {fmt_pct(float(derived.get('cache_hit_ratio') or 0.0))} / {fmt_pct(float(derived.get('last_input_ratio') or 0.0))} / {(fmt_tokens_m(int(tail_rate_per_min)) + '/min') if tail_rate_per_min > 0 else '-'}",
        f"Think Ratio   : {fmt_pct(float(derived.get('reasoning_ratio') or 0.0))}",
        f"Today/7d/30m  : {fmt_tokens_m(int(summary.get('today_total') or 0))} / {fmt_tokens_m(int(summary.get('week_total') or 0))} / {fmt_tokens_m(int(recent.get('total_tokens') or 0))}",
        f"Trend 30m     : {buckets.get('sparkline', '-')}",
        f"Top Models    : {short_text(model_line, 100)}",
        f"Top Repos     : {short_text(repo_line, 100)}",
        f"Rates         : {' | '.join(rate_chunks) if rate_chunks else '-'}",
    ]
    if advisories:
        first = advisories[0]
        lines.append(f"Alerts        : [{first['severity']}] {short_text(first['summary'], 100)}")
    if len(advisories) > 1:
        second = advisories[1]
        lines.append(f"Next Action   : [{second['severity']}] {short_text(second['action'], 100)}")
    if causes:
        lines.append(f"Likely Cause  : {short_text(' | '.join(item['cause'] for item in causes), 110)}")
    if playbook:
        lines.append(f"Trim Mode     : {short_text(' | '.join(playbook), 110)}")
    return "\n".join(lines)


def render_threads(snapshot: dict[str, Any], thread_sort: str) -> str:
    lines = [f"Codex Usage Dashboard - Threads [{thread_sort}]", ""]
    lines.extend(["Top Threads", "-----------"])
    for row in sort_threads(snapshot.get("threads") or [], thread_sort):
        lines.append(
            f"{fmt_tokens_m(int(row.get('tokens_used') or 0)).rjust(8)}  "
            f"{(row.get('model') or '-'):12}  "
            f"{row.get('updated_at_text', '-'):19}  "
            f"{short_text(row.get('title') or '-', 68)}"
        )
    top_models = snapshot.get("top_models") or []
    if top_models:
        lines.extend(["", "Top Models", "----------"])
        for item in top_models:
            lines.append(f"{fmt_tokens_m(int(item.get('tokens_used') or 0)).rjust(8)}  x{item.get('threads', 0):<2}  {item.get('name', '-')}")
    top_repos = snapshot.get("top_repos") or []
    if top_repos:
        lines.extend(["", "Top Repos", "---------"])
        for item in top_repos:
            lines.append(f"{fmt_tokens_m(int(item.get('tokens_used') or 0)).rjust(8)}  x{item.get('threads', 0):<2}  {item.get('name', '-')}")
    return "\n".join(lines)


def render_trends(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("session_summary") or {}
    recent = snapshot.get("recent_window") or {}
    recent_windows = snapshot.get("recent_windows") or {}
    buckets = snapshot.get("recent_buckets") or {}
    lines = ["Codex Usage Dashboard - Trends", ""]
    lines.append(f"Trend 30m : {buckets.get('sparkline', '-')}")
    lines.extend(["", "Rates", "-----"])
    for key in ["5", "15", "30"]:
        item = recent_windows.get(key)
        if not item:
            continue
        lines.append(
            f"{str(key).rjust(2)}m  {fmt_tokens_m(int(item.get('total_tokens') or 0)).rjust(8)}  {fmt_tokens_m(int(item.get('rate_per_min') or 0))}/min"
        )
    by_day = summary.get("by_day") or []
    if by_day:
        lines.extend(["", "Daily Totals", "-----------"])
        for date_text, total in by_day[:7]:
            lines.append(f"{date_text}  {fmt_tokens_m(int(total))}")
    recent_models = recent.get("top_models") or []
    if recent_models:
        lines.extend(["", f"Recent {recent.get('minutes', 30)}m Models", "------------------"])
        for item in recent_models[:5]:
            lines.append(f"{fmt_tokens_m(int(item.get('tokens') or 0)).rjust(8)}  {item.get('name', '-')}")
    recent_repos = recent.get("top_repos") or []
    if recent_repos:
        lines.extend(["", f"Recent {recent.get('minutes', 30)}m Repos", "-----------------"])
        for item in recent_repos[:5]:
            lines.append(f"{fmt_tokens_m(int(item.get('tokens') or 0)).rjust(8)}  {item.get('name', '-')}")
    return "\n".join(lines)


def render_snapshot(snapshot: dict[str, Any], warn_thread_tokens: int, view: str, thread_sort: str, tail_rate_per_min: float = 0.0) -> str:
    resolved = effective_view(view, term_size().lines)
    if resolved == "threads":
        return render_threads(snapshot, thread_sort)
    if resolved == "trends":
        return render_trends(snapshot)
    return render_summary(snapshot, warn_thread_tokens, tail_rate_per_min=tail_rate_per_min)


def status_bar(snapshot: dict[str, Any], view: str, interval: float, paused: bool, help_visible: bool, tail_rate_per_min: float, thread_sort: str) -> str:
    status = snapshot.get("status", "STABLE")
    active = snapshot.get("active_thread") or {}
    model = active.get("model", "-") or "-"
    update_text = fmt_ts(int(active.get("updated_at") or 0))
    run_state = "paused" if paused else "live"
    help_state = "help:on" if help_visible else "help:off"
    resolved = effective_view(view, term_size().lines)
    rate_text = fmt_tokens_m(int(tail_rate_per_min)) + "/min" if tail_rate_per_min > 0 else "-"
    sort_text = f"[sort:{thread_sort}]" if resolved == "threads" else ""
    return f"[{resolved}] {sort_text} [{status}] [{run_state}] [{help_state}] [{interval:.1f}s] [{model}] [{rate_text}] [{update_text}]"


def help_bar() -> str:
    return "1/2/3 view  a auto  s sort  r refresh  p pause  +/- interval  j/k scroll  h help  q quit"


def render_interactive(snapshot: dict[str, Any], warn_thread_tokens: int, view: str, interval: float, paused: bool, help_visible: bool, tail_rate_per_min: float, scroll: int, thread_sort: str) -> str:
    size = term_size()
    header = status_bar(snapshot, view, interval, paused, help_visible, tail_rate_per_min, thread_sort)
    body = render_snapshot(snapshot, warn_thread_tokens, view, thread_sort, tail_rate_per_min=tail_rate_per_min).splitlines()
    footer = help_bar() if help_visible else ""
    content_rows = max(5, size.lines - 1 - (1 if footer else 0))
    clipped = body[scroll : scroll + content_rows]
    more_top = " ^ more ^" if scroll > 0 else ""
    more_bottom = " v more v" if scroll + content_rows < len(body) else ""
    lines = [header]
    if more_top:
        lines.append(more_top)
        clipped = clipped[: max(0, content_rows - 1)]
    lines.extend(clipped)
    if more_bottom and len(lines) < size.lines - (1 if footer else 0):
        lines.append(more_bottom)
    if footer:
        lines.append(footer)
    return "\n".join(lines[: size.lines])


class TerminalMode:
    def __enter__(self) -> "TerminalMode":
        self.tty = open("/dev/tty", "r", encoding="utf-8", errors="ignore", buffering=1)
        self.fd = self.tty.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
        self.tty.close()


def interactive_loop(args: argparse.Namespace, state_db: Path, sessions_root: Path) -> int:
    interval = max(float(args.interval), 1.0)
    view = args.view
    thread_sort = args.thread_sort
    paused = False
    help_visible = True
    scroll = 0
    force_refresh = True
    prev_total = -1
    prev_monotonic = 0.0
    rate_per_min = 0.0
    snapshot: dict[str, Any] = {}
    with TerminalMode() as term:
        while True:
            now_monotonic = time.monotonic()
            if force_refresh or (not paused and (prev_monotonic == 0.0 or now_monotonic - prev_monotonic >= interval)):
                snapshot = current_snapshot(state_db, sessions_root, args.limit, args.top_models, args.top_repos)
                snapshot["recent_window"] = recent_window_summary(sessions_root, state_db, minutes=30, top_models=args.top_models, top_repos=args.top_repos)
                snapshot["recent_windows"] = recent_windows_summary(sessions_root, state_db, windows=[5, 15, 30], top_models=args.top_models, top_repos=args.top_repos)
                snapshot["recent_buckets"] = recent_bucket_series(sessions_root, state_db, minutes=30, bucket_minutes=5)
                info = ((snapshot.get("active_token_count") or {}).get("info") or {})
                total_usage = info.get("total_token_usage") or {}
                current_total = int(total_usage.get("total_tokens") or 0)
                if prev_total >= 0 and current_total >= prev_total and prev_monotonic > 0 and now_monotonic > prev_monotonic:
                    rate_per_min = (current_total - prev_total) * 60.0 / (now_monotonic - prev_monotonic)
                prev_total = current_total
                prev_monotonic = now_monotonic
                snapshot["advisories"] = advisory_lines(snapshot, args.warn_thread_tokens, tail_rate_per_min=rate_per_min)
                snapshot["status"] = status_from_alerts(snapshot["advisories"])
                snapshot["attribution"] = likely_operation_causes(snapshot, snapshot["advisories"])
                snapshot["playbook"] = output_trim_playbook(snapshot["advisories"])
                force_refresh = False
                scroll = 0 if effective_view(view, term_size().lines) == "summary" else scroll
            print("\033[2J\033[H", end="")
            print(render_interactive(snapshot, args.warn_thread_tokens, view, interval, paused, help_visible, rate_per_min, scroll, thread_sort))
            sys.stdout.flush()
            ready, _, _ = select.select([term.fd], [], [], 0.25)
            if not ready:
                continue
            ch = os.read(term.fd, 1).decode("utf-8", errors="ignore")
            if ch == "q":
                print("\033[2J\033[H", end="")
                return 0
            if ch == "1":
                view = "summary"
                scroll = 0
            elif ch == "2":
                view = "threads"
                scroll = 0
            elif ch == "3":
                view = "trends"
                scroll = 0
            elif ch == "a":
                view = "auto"
                scroll = 0
            elif ch == "s":
                order = ["updated", "tokens", "model", "repo"]
                thread_sort = order[(order.index(thread_sort) + 1) % len(order)]
                scroll = 0
            elif ch == "r":
                force_refresh = True
            elif ch == "p":
                paused = not paused
            elif ch == "+":
                interval = min(interval + 1.0, 30.0)
            elif ch == "-":
                interval = max(interval - 1.0, 1.0)
            elif ch == "h":
                help_visible = not help_visible
            elif ch == "j":
                scroll += 1
            elif ch == "k":
                scroll = max(0, scroll - 1)


def cmd_report(args: argparse.Namespace) -> int:
    state_db, sessions_root = resolve_paths(args)
    snapshot = current_snapshot(state_db, sessions_root, args.limit, args.top_models, args.top_repos)
    snapshot["recent_window"] = recent_window_summary(sessions_root, state_db, minutes=30, top_models=args.top_models, top_repos=args.top_repos)
    snapshot["recent_windows"] = recent_windows_summary(sessions_root, state_db, windows=[5, 15, 30], top_models=args.top_models, top_repos=args.top_repos)
    snapshot["recent_buckets"] = recent_bucket_series(sessions_root, state_db, minutes=30, bucket_minutes=5)
    snapshot["advisories"] = advisory_lines(snapshot, args.warn_thread_tokens)
    snapshot["status"] = status_from_alerts(snapshot["advisories"])
    snapshot["attribution"] = likely_operation_causes(snapshot, snapshot["advisories"])
    snapshot["playbook"] = output_trim_playbook(snapshot["advisories"])
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(render_snapshot(snapshot, args.warn_thread_tokens, args.view, args.thread_sort))
        return 0


def cmd_tail(args: argparse.Namespace) -> int:
    state_db, sessions_root = resolve_paths(args)
    if args.interactive and not args.json:
        if not sys.stdout.isatty():
            print("[FATAL] --interactive 需要真实 TTY 输出。", file=sys.stderr)
            return 2
        try:
            with open("/dev/tty", "r", encoding="utf-8", errors="ignore"):
                pass
        except OSError:
            print("[FATAL] --interactive 无法访问 /dev/tty，当前环境不支持终端键位读取。", file=sys.stderr)
            return 2
        return interactive_loop(args, state_db, sessions_root)
    interval = max(float(args.interval), 1.0)
    remaining = int(args.iterations)
    prev_total = -1
    prev_monotonic = 0.0
    while True:
        snapshot = current_snapshot(state_db, sessions_root, args.limit, args.top_models, args.top_repos)
        snapshot["recent_window"] = recent_window_summary(sessions_root, state_db, minutes=30, top_models=args.top_models, top_repos=args.top_repos)
        snapshot["recent_windows"] = recent_windows_summary(sessions_root, state_db, windows=[5, 15, 30], top_models=args.top_models, top_repos=args.top_repos)
        snapshot["recent_buckets"] = recent_bucket_series(sessions_root, state_db, minutes=30, bucket_minutes=5)
        info = ((snapshot.get("active_token_count") or {}).get("info") or {})
        total_usage = info.get("total_token_usage") or {}
        current_total = int(total_usage.get("total_tokens") or 0)
        now_monotonic = time.monotonic()
        rate_per_min = 0.0
        if prev_total >= 0 and current_total >= prev_total and now_monotonic > prev_monotonic:
            rate_per_min = (current_total - prev_total) * 60.0 / (now_monotonic - prev_monotonic)
        prev_total = current_total
        prev_monotonic = now_monotonic
        snapshot["advisories"] = advisory_lines(snapshot, args.warn_thread_tokens, tail_rate_per_min=rate_per_min)
        snapshot["status"] = status_from_alerts(snapshot["advisories"])
        snapshot["attribution"] = likely_operation_causes(snapshot, snapshot["advisories"])
        snapshot["playbook"] = output_trim_playbook(snapshot["advisories"])
        if args.json:
            print(json.dumps(snapshot, ensure_ascii=False))
        else:
            print("\033[2J\033[H", end="")
            print(render_snapshot(snapshot, args.warn_thread_tokens, args.view, args.thread_sort, tail_rate_per_min=rate_per_min))
            sys.stdout.flush()
        if args.once:
            return 0
        if remaining > 0:
            remaining -= 1
            if remaining == 0:
                return 0
        time.sleep(interval)


def main(argv: Sequence[str] | None = None) -> int:
    root = argparse.ArgumentParser(prog="codex-usage")
    sub = root.add_subparsers(dest="command", required=True)

    report = sub.add_parser("report", parents=[base_parser()])
    report.set_defaults(func=cmd_report)

    tail = sub.add_parser("tail", parents=[base_parser()])
    tail.add_argument("--interval", type=float, default=3.0)
    tail.add_argument("--iterations", type=int, default=0)
    tail.add_argument("--once", action="store_true")
    tail.set_defaults(func=cmd_tail)

    args = root.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
