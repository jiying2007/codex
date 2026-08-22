from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .core import CodexAssetError


CLUSTERS = (
    (
        "low_power_wakeup",
        ("休眠", "唤醒", "shutdown", "重启", "看门狗", "deep sleep", "睡眠"),
        ("embedded-low-power-wakeup-triage", "adk-embedded-remote-debug-log-triage"),
    ),
    (
        "runtime_performance",
        ("高负载", "高占用", "耗时", "阻塞", "帧率", "性能", "cpu"),
        ("embedded-runtime-performance-triage", "adk-systematic-debugging"),
    ),
    (
        "core_crash",
        ("core", "崩溃", "sigsegv", "valgrind"),
        ("embedded-core-dump-triage", "adk-offline-core-dump-triage"),
    ),
    (
        "production_calibration",
        ("标定", "校准", "厂测", "老化", "product_test", "pcba"),
        ("embedded-production-test-lifecycle", "adk-embedded-diagnostic-harness"),
    ),
    (
        "audio_stream",
        ("音频", "audioplayer", "播放器", "音量", "声道"),
        ("embedded-audio-stream-triage",),
    ),
    (
        "release_ota",
        ("发布", "发版", "ota", "版本", "构建", "release"),
        ("sigmastar-release-app-flow", "adk-embedded-release-orchestration"),
    ),
)


def parse_day(value: str, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CodexAssetError(f"{option} 必须是 YYYY-MM-DD: {value}") from exc


def load_rows(path: Path, start: date, end: date) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            updated = str(item.get("updated_at", ""))
            updated_day = date.fromisoformat(updated[:10])
        except (json.JSONDecodeError, ValueError):
            continue
        title = str(item.get("thread_name", "")).strip()
        if title and start <= updated_day <= end:
            rows.append({"date": updated_day.isoformat(), "title": title})
    return rows


def make_report(rows: list[dict[str, str]], start: date, end: date, limit: int) -> dict[str, Any]:
    clusters: list[dict[str, Any]] = []
    for name, terms, coverage in CLUSTERS:
        matched = [row for row in rows if any(term in row["title"].casefold() for term in terms)]
        if not matched:
            continue
        by_day = Counter(row["date"] for row in matched)
        clusters.append(
            {
                "name": name,
                "count": len(matched),
                "days": len(by_day),
                "coverage_hints": list(coverage),
                "examples": [row["title"] for row in matched[:limit]],
                "source": "session_index_title_only",
                "decision": "review-current-coverage",
            }
        )
    clusters.sort(key=lambda item: (-item["count"], item["name"]))
    return {
        "schema_version": 1,
        "kind": "workflow-mining-title-report",
        "read_only": True,
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "source_coverage": {
            "session_index": "title-only",
            "raw_session_body": "not-read",
            "project_spread": "unknown; verify with governed receipts or Hub evidence",
        },
        "total_threads": len(rows),
        "clusters": clusters,
        "next_gate": "Verify recurrence, project spread, current coverage, and privacy boundary before create or extend decisions.",
    }


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--session-index", default=str(Path.home() / ".codex" / "session_index.jsonl"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")


def run(args: argparse.Namespace) -> int:
    start = parse_day(args.start, "--from")
    end = parse_day(args.end, "--to")
    if end < start:
        raise CodexAssetError("--to 不能早于 --from")
    if args.limit < 1:
        raise CodexAssetError("--limit 必须大于 0")
    path = Path(args.session_index).expanduser().resolve()
    if not path.is_file():
        raise CodexAssetError(f"session index 不存在: {path}")
    report = make_report(load_rows(path, start, end), start, end, args.limit)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"[INFO] window={start}..{end} threads={report['total_threads']} source=title-only")
    for cluster in report["clusters"]:
        print(f"[CLUSTER] {cluster['name']} count={cluster['count']} days={cluster['days']} coverage={','.join(cluster['coverage_hints'])}")
    print(f"[NEXT] {report['next_gate']}")
    return 0
