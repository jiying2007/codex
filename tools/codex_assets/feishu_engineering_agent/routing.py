"""Deterministic Chinese ingress. Never interpret free text as execution approval."""
from __future__ import annotations

import re
from typing import FrozenSet, Iterable

from .models import Decision, IntakeRejected, check_repo_alias


_SWITCH = re.compile(
    r"\A(?:/repo\s+|/project\s+|切换到\s*|切换项目\s*|项目切换到\s*)"
    r"(?P<repo>[a-z][a-z0-9_-]{0,31})\s*(?:项目|仓库)?\Z",
    re.IGNORECASE,
)
_TASK_ID = re.compile(
    r"\A(?:/task\s+|任务\s*#?\s*|查看任务\s*#?\s*)"
    r"(?P<id>[1-9][0-9]{0,12})(?:\s*(?:状态|进度))?\Z",
    re.IGNORECASE,
)
_CANCEL = re.compile(
    r"\A(?:/cancel\s+|取消任务\s*#?\s*)(?P<id>[1-9][0-9]{0,12})\Z",
    re.IGNORECASE,
)
_CONTINUE = re.compile(
    r"\A(?:/resume\s+|继续(?:分析|处理)?任务\s*#?\s*)"
    r"(?P<id>[1-9][0-9]{0,12})\Z",
    re.IGNORECASE,
)
_PREFIX = re.compile(r"\A(?:请帮我|麻烦帮我|帮我|请|麻烦|帮忙)\s*")
_READ = ("分析", "检查", "解释", "查看", "定位", "调查", "评估", "了解", "说明")
_REVIEW = ("代码审查", "审查", "review")
_EDIT = ("修复", "修改", "实现", "开发", "重构", "增加", "添加", "fix", "implement")
_HIGH_RISK = ("发布", "上线", "部署", "合并", "刷写", "烧录", "删除仓库", "删除数据")


def route_message(
    text: str, selected_repo: str, allowed_repos: Iterable[str],
) -> Decision:
    """Only produces a decision. No model, network, Git or filesystem writes."""
    aliases: FrozenSet[str] = frozenset(check_repo_alias(a) for a in allowed_repos)
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise IntakeRejected("message text must be nonempty and bounded")
    message = " ".join(text.split()).strip()
    if not message:
        raise IntakeRejected("message text must be nonempty")
    if selected_repo and selected_repo not in aliases:
        selected_repo = ""  # stale preference cannot grant access

    if message.lower() in ("/help", "help", "帮助"):
        return Decision("help", reason="control_only")
    if message.lower() in ("/status", "status", "状态", "查看状态"):
        return Decision("status", reason="control_only")
    if message.lower() in ("/repo", "/project", "当前项目", "我的项目"):
        return Decision("show_project", repo=selected_repo, reason="control_only")
    if message.lower() in ("/repo reset", "/project reset", "清除项目", "重置项目"):
        return Decision("reset_project", reason="control_only")

    match = _SWITCH.fullmatch(message)
    if match:
        alias = match.group("repo").lower()
        if alias not in aliases:
            return Decision("blocked", reason="repository_not_allowlisted")
        return Decision("switch_project", repo=alias, reason="control_only")

    match = _TASK_ID.fullmatch(message)
    if match:
        return Decision("task_status", task_id=int(match.group("id")), reason="read_only_control")

    match = _CANCEL.fullmatch(message)
    if match:
        return Decision("cancel_proposal", task_id=int(match.group("id")),
                        requires_approval=True, reason="requires_task_owner_check")

    match = _CONTINUE.fullmatch(message)
    if match:
        if not selected_repo:
            return Decision("need_project", reason="select_authorized_repository")
        return Decision("resume_proposal", repo=selected_repo, task_id=int(match.group("id")),
                        requires_approval=True, reason="requires_exact_session_and_budget_gate")

    if message.startswith(("/cancel", "取消任务", "取消", "/resume", "继续", "/task", "任务")):
        return Decision("clarify", reason="explicit_task_id_required")
    if message.startswith(("/repo", "/project", "切换", "项目切换")):
        return Decision("clarify", reason="exact_repository_alias_required")
    if message.startswith("/"):
        return Decision("clarify", reason="unsupported_control_command")

    intent = _PREFIX.sub("", message, count=1).lstrip()
    if any(intent.lower().startswith(verb) for verb in _HIGH_RISK):
        return Decision("blocked", reason="privileged_operation_not_in_chat_intake")
    if not selected_repo:
        return Decision("need_project", reason="select_authorized_repository")
    if any(intent.lower().startswith(verb) for verb in _REVIEW):
        return Decision("review_proposal", repo=selected_repo,
                        reason="no_model_executed")
    if any(intent.lower().startswith(verb) for verb in _EDIT):
        return Decision("write_proposal", repo=selected_repo,
                        requires_approval=True, reason="explicit_edit_and_budget_approval_required")
    if any(intent.lower().startswith(verb) for verb in _READ):
        return Decision("read_proposal", repo=selected_repo, reason="no_model_executed")
    return Decision("clarify", reason="intent_not_derived_from_free_text")
