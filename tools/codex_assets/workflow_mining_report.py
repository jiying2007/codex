from __future__ import annotations

import argparse
import json
import re
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
    ("goal_convergence", ("goal", "长任务", "重规划", "续行"),
     ("adk-planning-execution-loop", "adk-context-compress-handoff")),
    ("skill_distribution", ("技能分发", "skill分发", "skill 分发", "skill 安装", "应用adk", "应用 adk", "source-to-live"),
     ("skill-asset-manager",)),
    ("verification_rework", ("验证返工", "全量回归", "重复验证", "回归门禁", "ci门禁", "ci 门禁"),
     ("adk-verification-before-completion", "adk-test-flakiness-triage")),
    ("team_delivery", ("团队交付", "团队技能", "团队仓库", "runtime bundle", "独立试点"),
     ("adk-pilot-framework",)),
)

LOCAL_TIME = timezone(timedelta(hours=8))
PROJECT_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,95}\Z")
THREAD_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")


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


def _main_thread(thread: str, parents: dict[str, str | None]) -> str | None:
    seen = set()
    while thread and thread in parents and thread not in seen:
        parent = parents[thread]
        if parent is None:
            return thread
        seen.add(thread)
        thread = parent
    return None


def make_report(rows: list[dict[str, str]], start: date, end: date, limit: int, *,
                parents: dict[str, str | None] | None = None, include_examples: bool = False,
                include_thread_refs: bool = False) -> dict[str, Any]:
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
        anchored = ([_main_thread(row.get("thread_id", ""), parents) for row in matched]
                    if parents is not None else None)
        main_threads = set(anchored or ()) - {None}
        clusters.append(
            {
                "name": name,
                "count": len(matched),
                "identified_threads": sum(bool(row.get("thread_id")) for row in matched),
                "days": len(by_day),
                "coverage_hints": list(coverage),
                "examples": sorted({term for term in terms if any(term in row["title"].casefold()
                                    for row in matched)})[:limit] if include_examples else [],
                "mapped_main_threads": len(main_threads) if anchored is not None else None,
                "unmapped_title_rows": anchored.count(None) if anchored is not None else None,
                "source": "session_index_title_only",
                "decision": "review-current-coverage",
            }
        )
        if include_thread_refs:
            clusters[-1]["main_thread_refs"] = sorted(
                thread for thread in main_threads if THREAD_ID.fullmatch(thread)
            )[:min(limit, 20)]
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


def metadata_coverage(root: Path, start: date, end: date, *,
                      parents: dict[str, str | None] | None = None) -> dict[str, Any]:
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
            identity = meta.get("id")
            if not isinstance(identity, str) or not identity:
                raise ValueError("missing thread id")
            source = meta.get("source")
            if parents is not None:
                if isinstance(source, str):
                    parents[identity] = None
                elif isinstance(source, dict) and isinstance(source.get("subagent"), dict):
                    spawn = source["subagent"].get("thread_spawn")
                    parent = spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
                    parents[identity] = parent if isinstance(parent, str) else ""
            if not start <= day <= end:
                continue
            files += 1
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


def receipt_coverage(paths: list[Path], start: date, end: date, *,
                     project_id: str | None = None) -> dict[str, Any]:
    """Consume explicit sanitized Provider input files, without reading Hub internals."""
    if len(paths) > 32:
        raise CodexAssetError("too many activity receipt inputs (max 32)")
    if project_id is not None and not PROJECT_ID.fullmatch(project_id):
        raise CodexAssetError("activity project must be an explicit canonical project ID")
    items: dict[tuple[str, str, str], set[str]] = {}
    excluded: dict[str, set[tuple[str, str, str]]] = {
        "out_of_window": set(), "missing_project": set(), "different_project": set(),
    }
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise CodexAssetError("activity receipt must be a regular file")
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise CodexAssetError("activity receipt exceeds 1 MiB")
        try:
            receipt = json.loads(raw)
            if (receipt["schema_version"] != 2 or receipt["kind"] != "activity-session-receipt"
                    or receipt["raw_content_stored"] is not False or not isinstance(receipt["work_items"], list)):
                raise ValueError("wrong receipt schema")
            for item in receipt["work_items"]:
                if (item["schema_version"] != 2 or item["kind"] != "work-activity-item"
                        or item["raw_content_stored"] is not False):
                    raise ValueError("wrong work item schema")
                day = parse_day(item["activity_date"], "activity_date")
                fields = (item["subject_id"], item["project_id"], item["item_id"], item["title"])
                if not all(isinstance(value, str) for value in fields) or not all(fields[i] for i in (0, 2, 3)):
                    raise ValueError("wrong work item fields")
                key = fields[:3]
                if not start <= day <= end:
                    excluded["out_of_window"].add(key)
                elif project_id is not None and fields[1] != project_id:
                    reason = "different_project" if fields[1] else "missing_project"
                    excluded[reason].add(key)
                else:
                    items.setdefault(key, set()).update(
                        name for name, terms, _ in CLUSTERS if any(t in fields[3].casefold() for t in terms))
        except (KeyError, TypeError, ValueError) as exc:
            raise CodexAssetError("invalid activity receipt v2") from exc
    counts = Counter(name for themes in items.values() for name in themes)
    result = {"source": "caller-supplied-sanitized-activity-receipts", "window_basis": "activity-date",
            "receipts": len(paths), "distinct_work_items": len(items),
            "explicit_project_count": len({key[1] for key in items if key[1]}),
            "theme_counts": dict(sorted(counts.items())), "independent_sessions_verified": False}
    if project_id is not None:
        result["project_filter"] = {
            "project_id": project_id,
            "status": "matched" if items else "zero-hit",
            "excluded_distinct_items_by_reason": {
                reason: len(keys) for reason, keys in excluded.items()
            },
        }
    return result


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--session-index", default=str(Path.home() / ".codex" / "session_index.jsonl"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--session-root", help="optional session_meta-only inventory; no body access")
    parser.add_argument("--activity-receipt", action="append", default=[], type=Path,
                        help="sanitized activity-session-receipt v2 input; repeatable")
    parser.add_argument("--activity-project", help="filter receipts by exact Provider project ID")
    parser.add_argument("--include-thread-refs", action="store_true",
                        help="include bounded main thread IDs from session headers; requires --session-root")
    parser.add_argument("--include-match-terms", action="store_true", help="include matching vocabulary, never raw titles")


def run(args: argparse.Namespace) -> int:
    start = parse_day(args.start, "--from")
    end = parse_day(args.end, "--to")
    if end < start:
        raise CodexAssetError("--to 不能早于 --from")
    if args.limit < 1:
        raise CodexAssetError("--limit 必须大于 0")
    if args.activity_project and not args.activity_receipt:
        raise CodexAssetError("--activity-project requires --activity-receipt")
    if args.include_thread_refs and not (args.session_root and args.json):
        raise CodexAssetError("--include-thread-refs requires --session-root and --json")
    path = Path(args.session_index).expanduser().resolve()
    if not path.is_file():
        raise CodexAssetError(f"session index 不存在: {path}")
    receipts = (receipt_coverage(args.activity_receipt, start, end, project_id=args.activity_project)
                if args.activity_receipt else None)
    parents: dict[str, str | None] | None = {} if args.session_root else None
    inventory = None
    if args.session_root:
        root = Path(args.session_root).expanduser().resolve()
        if not root.is_dir():
            raise CodexAssetError("session root 不存在")
        inventory = metadata_coverage(root, start, end, parents=parents)
    report = make_report(load_rows(path, start, end), start, end, args.limit,
                         parents=parents, include_examples=args.include_match_terms,
                         include_thread_refs=args.include_thread_refs)
    if inventory is not None:
        report["metadata_inventory"] = inventory
    if receipts is not None:
        report["activity_receipt_inventory"] = receipts
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"[INFO] window={start}..{end} threads={report['total_threads']} source=title-only")
    for cluster in report["clusters"]:
        print(f"[CLUSTER] {cluster['name']} count={cluster['count']} days={cluster['days']} coverage={','.join(cluster['coverage_hints'])}")
    print(f"[NEXT] {report['next_gate']}")
    return 0
