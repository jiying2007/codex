from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Any

from .core import Repo, diff_build_live, live_drift
from .usage_dashboard import latest_token_count, load_threads


@dataclass
class Notice:
    severity: str
    code: str
    summary: str
    action: str
    evidence: dict[str, Any]


def run_git(root: pathlib.Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, check=False)


def status_paths(root: pathlib.Path) -> list[str]:
    proc = run_git(root, ["status", "--porcelain=v1"])
    if proc.returncode != 0:
        return []
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def add(notices: list[Notice], severity: str, code: str, summary: str, action: str, **evidence: Any) -> None:
    notices.append(Notice(severity, code, summary, action, evidence))


def usage_notices(notices: list[Notice], codex_home: pathlib.Path, warn_thread_tokens: int) -> None:
    state_db = codex_home / "state_5.sqlite"
    if not state_db.is_file():
        add(notices, "INFO", "USAGE_UNAVAILABLE", "未找到 Codex state_5.sqlite，跳过 token 状态判断。", "需要 token 诊断时运行 `rtk bash scripts/usage-report.sh --json`。", state_db=str(state_db))
        return
    try:
        threads = load_threads(state_db, 1)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        add(notices, "INFO", "USAGE_UNAVAILABLE", "读取 Codex token 状态失败。", "需要时直接运行 `rtk bash scripts/usage-report.sh --json` 查看详情。", error=str(exc))
        return
    if not threads:
        return
    active = threads[0]
    if active.tokens_used >= warn_thread_tokens:
        add(
            notices,
            "CRITICAL",
            "THREAD_LONG",
            f"当前活跃线程累计约 {active.tokens_used / 1_000_000:.1f}M tokens，已进入长线程高风险区。",
            "优先执行 `context-preflight -> session-wrap -> knowledge-archive -> memory-curator --dry-run`，然后新开会话。",
            thread_id=active.thread_id,
            tokens_used=active.tokens_used,
            warn_thread_tokens=warn_thread_tokens,
        )
    if active.rollout_path:
        token_count = latest_token_count(pathlib.Path(active.rollout_path))
        info = token_count.get("info", {}) if token_count else {}
        last = info.get("last_token_usage", {}) or {}
        total = int(last.get("total_tokens") or 0)
        input_tokens = int(last.get("input_tokens") or 0)
        window = int(info.get("model_context_window") or 0)
        if window and input_tokens / window >= 0.50:
            add(
                notices,
                "HIGH",
                "CTX_PRESSURE",
                f"最近一次输入约占 context window 的 {input_tokens / window:.0%}。",
                "停止继续堆背景；改为窄问题、关键片段读取，必要时新开会话。",
                input_tokens=input_tokens,
                context_window=window,
            )
        if total >= 100_000:
            add(
                notices,
                "MEDIUM",
                "LARGE_DELTA",
                f"最近一次 token delta 约 {total / 1_000_000:.1f}M，可能读入了过大的日志、diff 或 JSON。",
                "下一步先用 `--stat`、关键字段、定向窗口或 `rg` 缩小读取范围。",
                last_delta_tokens=total,
            )


def repo_notices(notices: list[Notice], root: pathlib.Path) -> None:
    paths = status_paths(root)
    if not paths:
        return
    source_prefixes = (
        "AGENTS.md",
        "README.md",
        "manifests/",
        "schemas/",
        "scripts/",
        "src/codex-home/",
        "tools/",
        "docs/codex-asset-management.md",
        "docs/design.md",
    )
    archive = [p for p in paths if p.startswith("docs/archive/")]
    source = [p for p in paths if p.startswith(source_prefixes)]
    if source:
        add(
            notices,
            "HIGH",
            "SOURCE_DIRTY",
            f"检测到 {len(source)} 个 Codex 声明式源或治理文件变更。",
            "提交前运行 `build -> doctor -> plan/dry-run -> apply -> diff/drift -> check`；涉及 AGENT/SKILL/DOC/SCRIPT 时同步 manifest、文档和验证。",
            count=len(source),
            examples=source[:8],
        )
    if archive:
        add(
            notices,
            "MEDIUM",
            "ARCHIVE_REVIEW",
            f"检测到 {len(archive)} 个 docs/archive 归档变更。",
            "将归档与交付代码分开提交；只把稳定、脱敏、可复用材料提升为 AGENTS、memory 或 skill。",
            count=len(archive),
            examples=archive[:8],
        )


def live_notices(notices: list[Notice], root: pathlib.Path, target: pathlib.Path) -> None:
    try:
        repo = Repo.from_path(root)
        ignored = repo.policies.get("allowed_live_drift_paths", [])
        drift = live_drift(repo.build, target, ignored)
        changed = len(drift.get("changed", []))
        stale = len(drift.get("stale", []))
        unmanaged = len(drift.get("unmanaged", []))
        if changed or stale or unmanaged:
            add(
                notices,
                "HIGH",
                "LIVE_DRIFT",
                f"运行态存在漂移：changed={changed} stale={stale} unmanaged={unmanaged}。",
                "先判断是本机私有改动还是源资产遗漏；需要收敛时重新 apply，旧版本残留应删除。",
                changed=changed,
                stale=stale,
                unmanaged=unmanaged,
            )
        same, diff, missing = diff_build_live(repo.build, target, ignored)
        if diff or missing:
            add(
                notices,
                "HIGH",
                "BUILD_LIVE_DIFF",
                f"build 与 live 不一致：same={same} diff={diff} missing={missing}。",
                "运行 `rtk bash scripts/apply.sh --profile team-collab` 后复查 `diff.sh` 与 `drift.sh`。",
                same=same,
                diff=diff,
                missing=missing,
            )
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        add(notices, "INFO", "LIVE_CHECK_SKIPPED", "live 深度检查未完成。", "需要时手动运行 `rtk bash scripts/drift.sh && rtk bash scripts/diff.sh`。", error=str(exc))


def overall_status(notices: list[Notice]) -> str:
    severities = {n.severity for n in notices}
    if "CRITICAL" in severities:
        return "CRITICAL"
    if "HIGH" in severities:
        return "HOT"
    if "MEDIUM" in severities:
        return "WATCH"
    return "STABLE"


def emit_markdown(status: str, notices: list[Notice], deep: bool) -> None:
    print("# Session Coach")
    print(f"status: {status}")
    print(f"deep: {int(deep)}")
    print()
    if not notices:
        print("- [INFO] STABLE: 暂无会话连续性提醒。")
        print("  next: 聚焦当前用户目标；收口前再次运行 `rtk bash scripts/session-coach.sh --deep`。")
        return
    for notice in notices:
        print(f"- [{notice.severity}] {notice.code}: {notice.summary}")
        print(f"  next: {notice.action}")
        if notice.evidence:
            compact = json.dumps(notice.evidence, ensure_ascii=False, sort_keys=True)
            print(f"  evidence: {compact}")


def run(args: argparse.Namespace) -> int:
    root = pathlib.Path(args.root).expanduser().resolve()
    codex_home = pathlib.Path(args.codex_home).expanduser().resolve()
    target = pathlib.Path(args.target).expanduser().resolve()
    notices: list[Notice] = []
    usage_notices(notices, codex_home, args.warn_thread_tokens)
    repo_notices(notices, root)
    if args.deep:
        live_notices(notices, root, target)
    status = overall_status(notices)
    payload = {
        "schema_version": 1,
        "status": status,
        "deep": bool(args.deep),
        "notices": [notice.__dict__ for notice in notices],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        emit_markdown(status, notices, args.deep)
    return 0
