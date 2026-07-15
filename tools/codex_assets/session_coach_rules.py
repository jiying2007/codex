from __future__ import annotations

import pathlib
from typing import Any

from .core import Repo, diff_build_live, live_drift
from .session_coach_checks import archive_quality_notices, event_policy_notices, evidence_notices, git_remote_notices
from .session_coach_config import default_value
from .session_coach_core import Notice, make_notice
from .usage_dashboard import latest_token_count, load_threads


def usage_notices(codex_home: pathlib.Path, config: dict[str, Any], warn_thread_tokens: int | None) -> tuple[list[Notice], bool]:
    threshold = int(warn_thread_tokens or default_value(config, "warn_thread_tokens", 50_000_000))
    state_db = codex_home / "state_5.sqlite"
    if not state_db.is_file():
        return [make_notice(
            "INFO", "USAGE_UNAVAILABLE", "steady", 10,
            "未找到 Codex state_5.sqlite，跳过 token 状态判断。",
            "需要 token 诊断时运行 `rtk bash scripts/usage-report.sh --json`。",
            state_db=str(state_db),
        )], False
    try:
        threads = load_threads(state_db, 1)
    except Exception as exc:  # pragma: no cover
        return [make_notice(
            "INFO", "USAGE_UNAVAILABLE", "steady", 10,
            "读取 Codex token 状态失败。",
            "需要时直接运行 `rtk bash scripts/usage-report.sh --json` 查看详情。",
            error=str(exc),
        )], False
    if not threads:
        return [], False
    notices = thread_notices(threads[0], config, threshold)
    return notices, any(notice.code in {"THREAD_LONG", "CTX_PRESSURE"} for notice in notices)


def thread_notices(active: Any, config: dict[str, Any], warn_thread_tokens: int) -> list[Notice]:
    notices: list[Notice] = []
    if active.tokens_used >= warn_thread_tokens:
        notices.append(make_notice(
            "CRITICAL", "THREAD_LONG", "handoff", 100,
            f"当前活跃线程累计约 {active.tokens_used / 1_000_000:.1f}M tokens，已进入长线程高风险区。",
            "优先收口并新开会话，避免继续扩大上下文。",
            ["rtk bash scripts/context-preflight.sh", "session-wrap", "rtk bash scripts/curate-memory.sh --dry-run"],
            stable_key=f"THREAD_LONG:{active.thread_id}",
            thread_id=active.thread_id, tokens_used=active.tokens_used, warn_thread_tokens=warn_thread_tokens,
        ))
    if not active.rollout_path:
        return notices
    return notices + rollout_notices(pathlib.Path(active.rollout_path), config)


def rollout_notices(rollout_path: pathlib.Path, config: dict[str, Any]) -> list[Notice]:
    info = (latest_token_count(rollout_path).get("info") or {})
    last = info.get("last_token_usage", {}) or {}
    total = int(last.get("total_tokens") or 0)
    input_tokens = int(last.get("input_tokens") or 0)
    window = int(info.get("model_context_window") or 0)
    notices: list[Notice] = []
    pressure_ratio = float(default_value(config, "context_pressure_ratio", 0.5))
    large_delta = int(default_value(config, "large_delta_tokens", 100_000))
    if window and input_tokens / window >= pressure_ratio:
        notices.append(make_notice(
            "HIGH", "CTX_PRESSURE", "handoff", 90,
            f"最近一次输入约占 context window 的 {input_tokens / window:.0%}。",
            "停止继续堆背景；改成窄问题、关键片段读取，必要时新开会话。",
            ["rtk bash scripts/session-coach.sh --deep", "rtk bash scripts/usage-report.sh --json"],
            stable_key="CTX_PRESSURE",
            input_tokens=input_tokens, context_window=window,
        ))
    if total >= large_delta:
        notices.append(make_notice(
            "MEDIUM", "LARGE_DELTA", "handoff", 60,
            f"最近一次 token delta 约 {total / 1_000_000:.1f}M，可能读入了过大的日志、diff 或 JSON。",
            "下一步先用 `--stat`、关键字段、定向窗口或 `rg` 缩小读取范围。",
            stable_key="LARGE_DELTA",
            last_delta_tokens=total, threshold=large_delta,
        ))
    return notices


def agent_notices(groups: dict[str, list[str]]) -> list[Notice]:
    if groups["agents"] and len(groups["agents"]) == 1:
        return [make_notice(
            "HIGH", "AGENTS_SYNC", "asset-update", 88,
            "只检测到一侧 AGENTS 变更，可能导致仓库规则与注入规则漂移。",
            "同步 `AGENTS.md` 与 `src/codex-home/AGENTS.md`，再 build/apply。",
            ["rtk bash scripts/build.sh", "rtk bash scripts/apply.sh"],
            stable_key="AGENTS_SYNC",
            paths=groups["agents"],
        )]
    if groups["agents"]:
        return [make_notice(
            "MEDIUM", "AGENTS_CHANGED", "asset-update", 66,
            "AGENTS 规则已变更，需要进入 Codex 资产闭环。",
            "运行 build/apply/check，确保常驻规则同步到 `~/.codex`。",
            ["rtk bash scripts/build.sh", "rtk bash scripts/check.sh"],
            stable_key="AGENTS_CHANGED",
            paths=groups["agents"],
        )]
    return []


def asset_notices(root: pathlib.Path, groups: dict[str, list[str]]) -> list[Notice]:
    notices: list[Notice] = []
    if groups["skills"]:
        notices.append(make_notice(
            "HIGH", "SKILL_ASSET_CHANGED", "asset-update", 84,
            f"检测到 {len(groups['skills'])} 个 skill 相关变更。",
            "确认 SKILL.md/README/LICENSE/openai.yaml 与 manifest 一致，并运行 skill 自检。",
            ["rtk bash scripts/check-skills.sh", "rtk bash scripts/check.sh"],
            stable_key="SKILL_ASSET_CHANGED",
            examples=groups["skills"][:8],
        ))
    if groups["agents_manifest"]:
        notices.append(make_notice(
            "HIGH", "AGENT_ASSET_CHANGED", "asset-update", 83,
            f"检测到 {len(groups['agents_manifest'])} 个 agent 相关变更。",
            "确认 agent manifest、openai.yaml、profile link 与 build 输出一致。",
            ["rtk bash scripts/doctor.sh --scope governance", "rtk bash scripts/check.sh"],
            stable_key="AGENT_ASSET_CHANGED",
            examples=groups["agents_manifest"][:8],
        ))
    if groups["mcp"]:
        notices.append(make_notice(
            "HIGH", "MCP_ASSET_CHANGED", "asset-update", 83,
            f"检测到 {len(groups['mcp'])} 个 MCP 相关变更。",
            "确认 MCP server 声明、权限边界和运行态配置一致；不要提交 secrets。",
            ["rtk bash scripts/doctor.sh --scope governance", "codex mcp list"],
            stable_key="MCP_ASSET_CHANGED",
            examples=groups["mcp"][:8],
        ))
    if groups["scripts"]:
        notices.append(make_notice(
            "HIGH", "SCRIPT_CHANGED", "asset-update", 82,
            f"检测到 {len(groups['scripts'])} 个脚本或工具入口变更。",
            "从非仓库 cwd 验证 help/dry-run，避免隐式依赖当前目录。",
            [f"rtk bash {root / 'scripts/session-coach.sh'} --help", "rtk python3 -m unittest discover -s tests -p 'test_*.py'"],
            stable_key="SCRIPT_CHANGED",
            examples=groups["scripts"][:8],
        ))
    return notices + governance_notices(groups)


def governance_notices(groups: dict[str, list[str]]) -> list[Notice]:
    examples = sorted(set(groups["workflows"] + groups["manifests"]))
    if not examples:
        return []
    return [make_notice(
        "HIGH", "GOVERNANCE_CHANGED", "asset-update", 80,
        f"检测到 {len(examples)} 个 manifest/workflow/schema 变更。",
        "运行 governance 检查并确认 workflow 引用的 profile、skill、agent 都存在。",
        ["rtk bash scripts/doctor.sh --scope governance", "rtk bash scripts/governance-report.sh --json"],
        stable_key="GOVERNANCE_CHANGED",
        examples=examples[:8],
    )]


def delivery_notices(groups: dict[str, list[str]], phase: str) -> list[Notice]:
    notices: list[Notice] = []
    if groups["delivery"]:
        notices.append(make_notice(
            "HIGH", "DELIVERY_LOOP", phase, 76,
            f"检测到 {len(groups['delivery'])} 个声明式交付文件变更。",
            "提交前完成 build -> doctor -> plan/dry-run -> apply -> diff/drift -> check。",
            ["rtk bash scripts/build.sh", "rtk bash scripts/check.sh"],
            stable_key="DELIVERY_LOOP",
            count=len(groups["delivery"]), examples=groups["delivery"][:8],
        ))
    if groups["staged"]:
        notices.append(make_notice(
            "HIGH", "STAGED_READY", "commit", 74,
            f"已有 {len(groups['staged'])} 个文件暂存，进入提交前状态。",
            "提交前确认验证证据、diff 范围和未暂存文件是否应排除。",
            ["rtk git diff --cached --check", "rtk git diff --cached --stat"],
            stable_key="STAGED_READY",
            examples=groups["staged"][:8],
        ))
    return notices


def repo_notices(
    root: pathlib.Path,
    groups: dict[str, list[str]],
    phase: str,
    event: str,
    config: dict[str, Any],
    evidence_file: pathlib.Path,
    deep: bool,
) -> list[Notice]:
    notices = agent_notices(groups) + asset_notices(root, groups) + delivery_notices(groups, phase)
    notices += event_policy_notices(root, groups, event)
    notices += git_remote_notices(root, event)
    notices += archive_quality_notices(root, groups, config)
    notices += evidence_notices(event, config, evidence_file)
    if groups["archive"]:
        notices.append(make_notice(
            "MEDIUM", "ARCHIVE_REVIEW", "archive", 44,
            f"检测到 {len(groups['archive'])} 个 Knowledge Hub Codex archive 归档变更。",
            "归档与交付代码分开提交；只把稳定、脱敏、可复用材料提升为 AGENTS、memory 或 skill。",
            stable_key="ARCHIVE_REVIEW",
            examples=groups["archive"][:8], count=len(groups["archive"]),
        ))
    return notices


def live_notices(root: pathlib.Path, target: pathlib.Path) -> tuple[list[Notice], bool]:
    try:
        repo = Repo.from_path(root)
        ignored = repo.policies.get("allowed_live_drift_paths", [])
        drift = live_drift(repo.build, target, ignored)
        changed = len(drift.get("changed", []))
        stale = len(drift.get("stale", []))
        unmanaged = len(drift.get("unmanaged", []))
        same, diff, missing = diff_build_live(repo.build, target, ignored)
    except Exception as exc:  # pragma: no cover
        return [make_notice("INFO", "LIVE_CHECK_SKIPPED", "steady", 5, "live 深度检查未完成。", "需要时手动运行 `rtk bash scripts/drift.sh && rtk bash scripts/diff.sh`。", error=str(exc))], False
    notices = live_drift_notices(changed, stale, unmanaged)
    notices += build_live_notices(same, diff, missing)
    return notices, bool(changed or stale or unmanaged or diff or missing)


def live_drift_notices(changed: int, stale: int, unmanaged: int) -> list[Notice]:
    if not (changed or stale or unmanaged):
        return []
    return [make_notice(
        "HIGH", "LIVE_DRIFT", "apply", 86,
        f"运行态存在漂移：changed={changed} stale={stale} unmanaged={unmanaged}。",
        "先判断是本机私有改动还是源资产遗漏；需要收敛时重新 apply，旧版本残留应删除。",
        ["rtk bash scripts/drift.sh --target ~/.codex", "rtk bash scripts/apply.sh"],
        stable_key="LIVE_DRIFT",
        changed=changed, stale=stale, unmanaged=unmanaged,
    )]


def build_live_notices(same: int, diff: int, missing: int) -> list[Notice]:
    if not (diff or missing):
        return []
    return [make_notice(
        "HIGH", "BUILD_LIVE_DIFF", "apply", 85,
        f"build 与 live 不一致：same={same} diff={diff} missing={missing}。",
        "重新 apply 后复查 diff/drift。",
        ["rtk bash scripts/apply.sh", "rtk bash scripts/diff.sh --target ~/.codex"],
        stable_key="BUILD_LIVE_DIFF",
        same=same, diff=diff, missing=missing,
    )]
