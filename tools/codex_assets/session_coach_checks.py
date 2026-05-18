from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from .session_coach_config import default_value, event_config
from .session_coach_core import Notice, make_notice, run_git
from .session_coach_evidence import age_minutes, latest_pass


def git_remote_notices(root: pathlib.Path, event: str) -> list[Notice]:
    proc = run_git(root, ["status", "-sb"])
    if proc.returncode != 0 or not proc.stdout:
        return []
    first = proc.stdout.splitlines()[0]
    ahead = _status_count(first, "ahead")
    behind = _status_count(first, "behind")
    notices: list[Notice] = []
    if behind:
        notices.append(make_notice(
            "HIGH", "REMOTE_BEHIND", "commit", 83,
            f"当前分支落后远端 {behind} 个提交。",
            "push 或继续提交前先同步远端，避免基于旧基线交付。",
            ["rtk git status -sb", "rtk git pull --ff-only"],
            stable_key="REMOTE_BEHIND",
            status_line=first, behind=behind,
        ))
    if ahead and event in {"final", "push"}:
        notices.append(make_notice(
            "HIGH", "REMOTE_AHEAD", "commit", 78,
            f"当前分支领先远端 {ahead} 个提交。",
            "收口前执行 push，或明确保留本地未推送提交。",
            ["rtk git status -sb", "rtk git push"],
            stable_key="REMOTE_AHEAD",
            status_line=first, ahead=ahead,
        ))
    if event == "push" and not ahead:
        notices.append(make_notice(
            "HIGH", "PUSH_NO_AHEAD", "commit", 79,
            "当前分支没有领先远端的提交。",
            "push 前应先产生本地提交；若只是确认状态，使用 `rtk git status -sb`。",
            ["rtk git status -sb"],
            stable_key="PUSH_NO_AHEAD",
            status_line=first,
        ))
    return notices + conflict_notices(root)


def event_policy_notices(root: pathlib.Path, groups: dict[str, list[str]], event: str) -> list[Notice]:
    changed = sorted(set(groups.get("all", [])))
    notices: list[Notice] = []
    if event == "commit" and not groups.get("staged"):
        notices.append(make_notice(
            "HIGH", "COMMIT_NOT_STAGED", "commit", 82,
            "commit 事件下尚无暂存文件。",
            "先暂存本次提交范围，再运行 commit-ready；不要把未确认文件混入提交。",
            ["rtk git status --short", "rtk git add <paths>"],
            stable_key="COMMIT_NOT_STAGED",
        ))
    if event == "push" and changed:
        notices.append(make_notice(
            "HIGH", "PUSH_DIRTY_WORKTREE", "commit", 84,
            f"push 事件下仍有 {len(changed)} 个未提交或未清理文件。",
            "先完成提交、放弃或明确保留本地变更，再 push。",
            ["rtk git status --short", "rtk git diff --stat"],
            stable_key="PUSH_DIRTY_WORKTREE",
            examples=changed[:8],
        ))
    if event == "final" and changed:
        notices.append(make_notice(
            "MEDIUM", "FINAL_DIRTY_WORKTREE", "handoff", 55,
            f"final 前仍有 {len(changed)} 个工作区变更。",
            "最终答复中明确已提交/未提交状态；需要交付闭环时先 commit/push/apply。",
            ["rtk git status --short"],
            stable_key="FINAL_DIRTY_WORKTREE",
            examples=changed[:8],
        ))
    return notices


def conflict_notices(root: pathlib.Path) -> list[Notice]:
    proc = run_git(root, ["status", "--porcelain=v1"])
    if proc.returncode != 0:
        return []
    conflicts = [line[3:] for line in proc.stdout.splitlines() if len(line) >= 3 and "U" in line[:2]]
    if not conflicts:
        return []
    return [make_notice(
        "CRITICAL", "MERGE_CONFLICT", "commit", 98,
        f"检测到 {len(conflicts)} 个冲突文件。",
        "先解决冲突并重新运行验证，再继续提交、push 或 apply。",
        ["rtk git status --short", "rtk git diff --check"],
        stable_key="MERGE_CONFLICT",
        examples=conflicts[:8],
    )]


def archive_quality_notices(root: pathlib.Path, groups: dict[str, list[str]], config: dict[str, Any]) -> list[Notice]:
    archive_paths = [root / path for path in groups.get("archive", []) if (root / path).is_file()]
    if not archive_paths:
        return []
    notices: list[Notice] = []
    notices += archive_meta_notices(root, archive_paths)
    notices += archive_size_notices(root, archive_paths, int(default_value(config, "archive_max_bytes", 262_144)))
    notices += archive_secret_notices(root, archive_paths, config.get("protected_archive_patterns", []))
    return notices


def archive_meta_notices(root: pathlib.Path, paths: list[pathlib.Path]) -> list[Notice]:
    invalid: list[str] = []
    missing: list[str] = []
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".json":
            try:
                json.loads(path.read_text())
            except Exception:
                invalid.append(rel)
        if path.suffix == ".md" and path.name not in {"index.md", "README.md"}:
            meta = path.with_name(path.name + ".meta.json")
            if not meta.is_file():
                missing.append(rel)
    notices: list[Notice] = []
    if invalid:
        notices.append(make_notice(
            "HIGH", "ARCHIVE_META_INVALID", "archive", 72,
            f"检测到 {len(invalid)} 个无效 archive meta JSON。",
            "修复 JSON 后再归档或提交。",
            ["rtk python3 -m json.tool <meta-json>"],
            stable_key="ARCHIVE_META_INVALID",
            examples=invalid[:8],
        ))
    if missing:
        notices.append(make_notice(
            "MEDIUM", "ARCHIVE_META_MISSING", "archive", 50,
            f"检测到 {len(missing)} 个归档 Markdown 缺少 meta.json。",
            "需要长期检索的归档应补同名 `.meta.json`，临时材料应确认是否应归档。",
            stable_key="ARCHIVE_META_MISSING",
            examples=missing[:8],
        ))
    return notices


def archive_size_notices(root: pathlib.Path, paths: list[pathlib.Path], max_bytes: int) -> list[Notice]:
    large = [path.relative_to(root).as_posix() for path in paths if path.stat().st_size > max_bytes]
    if not large:
        return []
    return [make_notice(
        "MEDIUM", "ARCHIVE_LARGE_FILE", "archive", 46,
        f"检测到 {len(large)} 个归档文件超过 {max_bytes} bytes。",
        "确认没有误归档日志、构建产物或大段原始输出；必要时改为摘要。",
        stable_key="ARCHIVE_LARGE_FILE",
        examples=large[:8], max_bytes=max_bytes,
    )]


def archive_secret_notices(root: pathlib.Path, paths: list[pathlib.Path], patterns: list[str]) -> list[Notice]:
    compiled: list[re.Pattern[str]] = []
    invalid: list[str] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            invalid.append(f"{pattern}: {exc}")
    if invalid:
        return [make_notice(
            "HIGH", "SESSION_COACH_CONFIG_INVALID", "asset-update", 90,
            f"session-coach 敏感信息扫描配置中有 {len(invalid)} 个非法正则。",
            "修复 `manifests/session_coach.json` 后重新运行 governance 检查。",
            ["rtk bash scripts/doctor.sh --scope governance"],
            stable_key="SESSION_COACH_CONFIG_INVALID",
            examples=invalid[:8],
        )]
    matches: list[str] = []
    for path in paths:
        if path.suffix not in {".md", ".json", ".txt"}:
            continue
        text = path.read_text(errors="ignore")
        if any(pattern.search(text) for pattern in compiled):
            matches.append(path.relative_to(root).as_posix())
    if not matches:
        return []
    return [make_notice(
        "HIGH", "ARCHIVE_SECRET_PATTERN", "archive", 89,
        f"归档文件命中 {len(matches)} 个敏感信息模式。",
        "提交前人工确认是否为真实密钥；真实密钥必须删除并轮换。",
        ["rtk rg -n '<pattern>' docs/archive"],
        stable_key="ARCHIVE_SECRET_PATTERN",
        examples=matches[:8],
    )]


def evidence_notices(event: str, config: dict[str, Any], evidence_file: pathlib.Path) -> list[Notice]:
    required = event_config(config, event).get("required_evidence", "")
    if not required:
        return []
    fresh_minutes = int(default_value(config, "evidence_fresh_minutes", 240))
    record = latest_pass(evidence_file, required)
    phase = event_config(config, event).get("phase", "handoff")
    if not record:
        return [make_notice(
            "HIGH", "EVIDENCE_MISSING", phase, 81,
            f"`{event}` 缺少近期 `{required}` 验证证据。",
            "先运行对应 ready wrapper 或记录验证证据，再 final/commit/push/apply。",
            [f"rtk bash scripts/{required}.sh"],
            stable_key=f"EVIDENCE_MISSING:{required}",
            evidence_file=str(evidence_file),
        )]
    age = age_minutes(record)
    if age > fresh_minutes:
        return [make_notice(
            "MEDIUM", "EVIDENCE_STALE", phase, 58,
            f"`{required}` 验证证据已超过 {age} 分钟。",
            "重新运行对应 ready wrapper，避免用旧证据收口。",
            [f"rtk bash scripts/{required}.sh"],
            stable_key=f"EVIDENCE_STALE:{required}",
            age_minutes=age, fresh_minutes=fresh_minutes,
        )]
    return []


def _status_count(status_line: str, key: str) -> int:
    match = re.search(rf"{key} (\d+)", status_line)
    return int(match.group(1)) if match else 0
