"""Manual WorkItem registration without Feishu Project/TAPD enterprise APIs.

Only metadata and a digest of the user-supplied summary are persisted.
The original external system remains authoritative; no model call, remote
read/write, document scraping, or external-status verification occurs here.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import re
import sqlite3
import time
import uuid
from typing import Iterable, Optional

from .models import EventConflict, InboundEvent, IntakeRejected, WorkItemKey, check_repo_alias
from .state import RunStore

_PROVIDERS = {"tapd": "tapd", "feishu_project": "feishu_project", "飞书项目": "feishu_project"}
_KINDS = {
    "requirement": "requirement", "需求": "requirement", "story": "requirement",
    "defect": "defect", "缺陷": "defect", "bug": "defect",
}
_RUN_ID = re.compile(r"\A[a-f0-9]{32}\Z")
_HELP = (
    "不需要飞书项目/TAPD 企业 API 的工作项登记：\n"
    "/wi add tapd 缺陷 <空间ID> <工作项ID> [repo=仓库别名] | 问题与验收描述\n"
    "/wi add feishu_project 需求 <空间ID> <工作项ID> [repo=仓库别名] | 需求与验收描述\n"
    "/wi list 查看本人最近登记；/wi status <完整Run ID> 查询状态；/wi help\n"
    "仅登记来源声明与任务关联，不启动 Codex、不获取原系统内容、不关闭需求或缺陷。"
)


@dataclasses.dataclass(frozen=True)
class ManualCommand:
    action: str
    key: Optional[WorkItemKey] = None
    repo: str = ""
    summary: str = ""
    run_id: str = ""


def is_manual_command(text: str) -> bool:
    """Recognize only the reserved command, not similar paths such as /wiki."""
    return isinstance(text, str) and bool(re.match(r"\A/wi(?:\s|\Z)", text.strip(), re.I))


def parse_manual_command(text: str, tenant: str, default_repo: str) -> ManualCommand:
    """Strict explicit syntax; text and URLs are never treated as API proofs."""
    if not is_manual_command(text) or len(text) > 12000 or "\x00" in text:
        raise IntakeRejected("not an allowed /wi command")
    header, delimiter, summary = text.strip().partition("|")
    tokens = header.split()
    action = tokens[1].lower() if len(tokens) >= 2 else "help"
    if action in ("help", "帮助") and len(tokens) == 2 and not delimiter:
        return ManualCommand("help")
    if action == "list" and len(tokens) == 2 and not delimiter:
        return ManualCommand("list")
    if action == "status" and len(tokens) == 3 and not delimiter:
        if not _RUN_ID.fullmatch(tokens[2]):
            raise IntakeRejected("status requires an exact 32-hex Run ID")
        return ManualCommand("status", run_id=tokens[2])
    if action != "add" or len(tokens) not in (6, 7) or not delimiter:
        raise IntakeRejected("invalid /wi syntax; send /wi help")
    provider = _PROVIDERS.get(tokens[2].lower())
    kind = _KINDS.get(tokens[3].lower())
    if provider is None or kind is None:
        raise IntakeRejected("unsupported WorkItem source or kind")
    alias = default_repo
    if len(tokens) == 7:
        if not tokens[6].startswith("repo="):
            raise IntakeRejected("optional repository must be repo=<alias>")
        alias = tokens[6][5:]
    repo = check_repo_alias(alias)
    normalized_summary = summary.strip()
    if (not normalized_summary or len(normalized_summary) > 4000
            or any(ord(x) < 32 and x not in "\n\t" for x in normalized_summary)):
        raise IntakeRejected("a bounded user-supplied problem and acceptance summary is required")
    key = WorkItemKey(provider, tenant, tokens[4], kind, tokens[5])
    return ManualCommand("add", key=key, repo=repo, summary=normalized_summary)


class ManualWorkItemService:
    """A private no-API adapter. Existing Bot is the only possible chat consumer."""

    def __init__(self, db_path):
        self.store = RunStore(db_path)
        with contextlib.closing(self.store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_manual_claims (
                    event_key TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL,
                    run_id TEXT NOT NULL UNIQUE REFERENCES fea_runs(run_id),
                    origin_message_id TEXT NOT NULL,
                    summary_sha256 TEXT NOT NULL,
                    source_level TEXT NOT NULL CHECK (
                        source_level='user_supplied_unverified'
                    ),
                    created_at INTEGER NOT NULL
                );
            """)

    def handle(
        self, event: InboundEvent, default_repo: str,
        allowed_repos: Iterable[str],
    ) -> Optional[str]:
        """Return a bounded chat reply or None on exact duplicate delivery."""
        authorized = frozenset(check_repo_alias(x) for x in allowed_repos)
        cmd = parse_manual_command(event.text, event.tenant, default_repo)
        if cmd.action == "help":
            return _HELP
        if cmd.action == "status":
            record = self.store.get_run(cmd.run_id, event)
            if record["repo"] not in authorized:
                raise IntakeRejected("repository access has changed")
            return (
                "任务：" + record["run_id"] + "\n"
                "项目：" + record["repo"] + "\n"
                "状态：" + record["status"] + "\n"
                "工作项来源：用户提供，未通过原系统 API 核验\n"
                "执行授权：未由本命令授予；需求/缺陷仍在原系统验收。"
            )
        if cmd.action == "list":
            with contextlib.closing(self.store._connect()) as db:
                rows = db.execute(
                    "SELECT r.run_id,r.repo,r.status FROM fea_manual_claims c "
                    "JOIN fea_runs r ON r.run_id=c.run_id "
                    "WHERE r.tenant=? AND r.chat=? AND r.actor=? "
                    "ORDER BY c.created_at DESC,c.run_id DESC LIMIT 5",
                    (event.tenant, event.chat, event.actor),
                ).fetchall()
            visible = [r for r in rows if r["repo"] in authorized]
            return ("最近登记的工作项：\n" + "\n".join(
                r["run_id"] + " " + r["repo"] + " " + r["status"] for r in visible
            )) if visible else "尚无可访问的工作项登记。"
        if cmd.action != "add" or cmd.key is None:
            raise IntakeRejected("unsupported manual action")
        if cmd.repo not in authorized:
            raise IntakeRejected("repository not authorized")
        now = int(time.time())
        run_id = uuid.uuid4().hex
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT content_sha256,run_id FROM fea_manual_claims "
                    "WHERE event_key=?", (event.event_key,),
                ).fetchone()
                if existing is not None:
                    if existing["content_sha256"] != event.content_digest:
                        raise EventConflict("same message identity with changed content")
                    row = db.execute(
                        "SELECT repo FROM fea_runs WHERE run_id=?",
                        (existing["run_id"],),
                    ).fetchone()
                    if row is None or row["repo"] not in authorized:
                        raise IntakeRejected("previously registered repository is no longer authorized")
                    db.rollback()
                    return None
                key = cmd.key
                db.execute(
                    "INSERT INTO fea_runs "
                    "(run_id,tenant,chat,actor,repo,mode,provider,workspace,kind,"
                    "item_id,workitem_fp,status,revision,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,'read',?,?,?,?,?,'proposed',0,?,?)",
                    (run_id, event.tenant, event.chat, event.actor, cmd.repo,
                     key.provider, key.workspace, key.kind, key.item_id,
                     key.fingerprint, now, now),
                )
                db.execute(
                    "INSERT INTO fea_manual_claims "
                    "(event_key,content_sha256,run_id,origin_message_id,"
                    "summary_sha256,source_level,created_at) "
                    "VALUES (?,?,?,?,?,'user_supplied_unverified',?)",
                    (event.event_key, event.content_digest, run_id, event.event_id,
                     hashlib.sha256(cmd.summary.encode("utf-8")).hexdigest(), now),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return (
            "已登记工作项引用（用户提供，原系统未核验）：\n"
            + cmd.key.provider + " / " + cmd.key.kind + " / "
            + cmd.key.workspace + " / " + cmd.key.item_id + "\n"
            + "项目：" + cmd.repo + "\n"
            + "AgentRun：" + run_id + "\n"
            + "状态：proposed（未执行）\n"
            + "仅存摘要哈希与消息引用，不留存需求正文；继续研发时须重新提供当前需求/复现信息。\n"
            + "不会启动模型、执行 Git 写操作或改变飞书项目/TAPD 的原始状态。"
        )
