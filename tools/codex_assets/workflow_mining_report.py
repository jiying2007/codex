from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .core import CodexAssetError


CLUSTERS = (
    ("speech_wakeup", ("唤醒词", "语音唤醒", "误唤醒", "kws", "qivw"),
     ("adk-test-strategy", "embedded-product-readiness-gate")),
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
    ("resource_leak", ("内存泄漏", "内存泄露", "资源泄漏", "fd 耗尽", "无界容器"),
     ("resource-leak-triage",)),
    ("safe_sync", ("多仓", "保留本地", "保留修改", "合并冲突", "同步仓库"),
     ("skill-asset-manager",)),
    ("build_isolation", ("增量构建", "构建目录", "输出目录", "多板构建", "构建输入"),
     ("embedded-build-release-check",)),
    ("hardware_contract", ("原理图", "引脚", "pinmux", "飞线", "gpio"),
     ("adk-driver-bringup-checklist",)),
)

LOCAL_TIME = timezone(timedelta(hours=8))


def observed_time(value: str) -> datetime:
    # Python 3.8 accepts only selected fractional widths; index timestamps can
    # contain nanoseconds. Keep timezone information and trim only precision.
    import re
    value = re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return result.astimezone(LOCAL_TIME)


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
            if not isinstance(item, dict):
                continue
            updated = str(item.get("updated_at", ""))
            observed = observed_time(updated)
            updated_day = observed.date()
        except (json.JSONDecodeError, ValueError):
            continue
        title = str(item.get("thread_name", "")).strip()
        if title and start <= updated_day <= end:
            identity = item.get("id")
            rows.append({"date": updated_day.isoformat(), "title": title,
                         "thread_id": identity.strip() if isinstance(identity, str) else "",
                         "observed_at": observed.isoformat()})
    return rows


def make_report(rows: list[dict[str, str]], start: date, end: date, limit: int) -> dict[str, Any]:
    latest: dict[str, dict[str, str]] = {}
    unidentified = []
    for row in rows:
        key = row.get("thread_id", "")
        if not key:
            unidentified.append(row)
        elif key not in latest or row.get("observed_at", row["date"]) >= latest[key].get("observed_at", latest[key]["date"]):
            latest[key] = row
    unique_rows = list(latest.values())
    # Missing IDs remain discovery evidence, never fabricated distinct threads.
    discovery_rows = unique_rows + unidentified
    clusters: list[dict[str, Any]] = []
    for name, terms, coverage in CLUSTERS:
        matched = [row for row in discovery_rows if any(term in row["title"].casefold() for term in terms)]
        if name == "low_power_wakeup":
            speech_terms = CLUSTERS[0][1]
            power_terms = ("休眠", "deep sleep", "suspend", "tcpka", "掉电", "低功耗", "rtc")
            matched = [row for row in matched if not any(t in row["title"].casefold() for t in speech_terms)
                       or any(t in row["title"].casefold() for t in power_terms)]
        if not matched:
            continue
        by_day = Counter(row["date"] for row in matched)
        clusters.append(
            {
                "name": name,
                "count": len(matched),
                "identified_threads": sum(bool(row.get("thread_id")) for row in matched),
                "days": len(by_day),
                "coverage_hints": list(coverage),
                "examples": [" ".join(row["title"].split())[:100] for row in matched[:limit]],
                "source": "session_index_title_only",
                "decision": "review-current-coverage",
            }
        )
    clusters.sort(key=lambda item: (-item["count"], item["name"]))
    return {
        "schema_version": 2,
        "kind": "workflow-mining-title-report",
        "read_only": True,
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "timezone": "Asia/Hong_Kong",
        "window_basis": "index-updated-at; not work activity date",
        "source_coverage": {
            "session_index": "title-only",
            "raw_session_body": "not-read",
            "project_spread": "unknown; verify with governed receipts or Hub evidence",
        },
        "total_rows": len(rows),
        "total_threads": len(unique_rows),
        "duplicate_rows": len(rows) - len(unique_rows) - len(unidentified),
        "unidentified_rows": len(unidentified),
        "clusters": clusters,
        "next_gate": "Verify recurrence, project spread, current coverage, and privacy boundary before create or extend decisions.",
    }


def metadata_coverage(root: Path, start: date, end: date) -> dict[str, Any]:
    """Read bounded session_meta headers only; never inspect session bodies."""
    main, children = set(), set()
    files = invalid = 0
    for path in root.glob("*/*/*/*.jsonl"):
        try:
            relative = path.relative_to(root)
            if any(root.joinpath(*relative.parts[:i]).is_symlink() for i in range(1, len(relative.parts) + 1)):
                raise ValueError("metadata symlink")
            path.resolve().relative_to(root.resolve())
            with path.open("rb") as stream:
                header = stream.readline(65537)
            if len(header) > 65536:
                raise ValueError("oversized metadata")
            record = json.loads(header)
            if not isinstance(record, dict) or record.get("type") != "session_meta":
                raise ValueError("missing metadata")
            meta = record["payload"]
            if not isinstance(meta, dict):
                raise ValueError("invalid metadata payload")
            day = observed_time(meta["timestamp"]).date()
            if not start <= day <= end:
                continue
            identity = meta.get("id")
            if not isinstance(identity, str) or not identity:
                raise ValueError("missing thread id")
            files += 1
            source = meta.get("source")
            if isinstance(source, str):
                main.add(identity)
            elif isinstance(source, dict) and "subagent" in source:
                children.add(identity)
            else:
                invalid += 1
        except (OSError, ValueError, TypeError, KeyError):
            invalid += 1
    return {"window_basis": "session-created-at", "valid_files": files,
            "main_threads": len(main), "subagent_threads": len(children),
            "invalid_or_unknown_headers": invalid, "raw_session_body": "not-read",
            "project_spread": "unknown; metadata paths do not identify Provider subjects",
            "coverage_ratio": None,
            "reason": "created-at inventory and updated-at index have different denominators"}


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--session-index", default=str(Path.home() / ".codex" / "session_index.jsonl"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--session-root", help="optional session_meta-only inventory; no body access")


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
    if args.session_root:
        root = Path(args.session_root).expanduser().resolve()
        if not root.is_dir():
            raise CodexAssetError("session root 不存在")
        report["metadata_inventory"] = metadata_coverage(root, start, end)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"[INFO] window={start}..{end} threads={report['total_threads']} source=title-only")
    for cluster in report["clusters"]:
        print(f"[CLUSTER] {cluster['name']} count={cluster['count']} days={cluster['days']} coverage={','.join(cluster['coverage_hints'])}")
    print(f"[NEXT] {report['next_gate']}")
    return 0
