"""Live, no-model link/topic intake on the existing private Bot SQLite.

A context owns source references and message digests, not an external ticket.
The old execution ledger remains during the verified cutover; this service does
not synthesize a local-MCP approval or launch a model.
"""
from __future__ import annotations

import dataclasses
import re
import time
import uuid
from typing import Iterable, Mapping, Optional, Sequence, Tuple

from .models import InboundEvent, IntakeRejected, EventConflict, _check_id, check_repo_alias
from .sources import MAX_SOURCES, EngineeringSource, candidate_urls, parse_sources

_CONTROL = {
    "/status", "status", "状态", "当前进度", "查看进度", "查看状态",
    "/help", "help", "帮助", "/cancel", "cancel", "取消", "停止任务",
    "/new", "/repo", "当前项目",
}
_REPO = re.compile(r"\A(?:/repo\s+|repo=)([a-z][a-z0-9_-]{0,31})(?=\s|\Z)", re.I)


@dataclasses.dataclass(frozen=True)
class IntakeResult:
    consumed: bool
    reply: Optional[str] = None
    context_id: str = ""
    repo: str = ""
    intent: str = ""
    scope_text: str = ""
    topic: str = ""


def intent_for(body: str) -> Tuple[str, str]:
    """Bounded, deterministic action recognition; never use a model for routing."""
    text = body.strip()
    for url in candidate_urls(text):
        text = text.replace(url, "")
    text = _REPO.sub("", text, count=1).strip()
    text = re.sub(r"\A(?:请帮我|麻烦帮我|帮我|请|麻烦|帮忙)\s*", "", text, count=1)
    explicit = re.match(r"\Amode=(explain|review|edit)(?=\s|\Z)", text)
    if explicit:
        return explicit.group(1), text[explicit.end():].strip()
    if re.match(r"\A(?:发布|上线|部署|合并|烧录|刷写|删除|push|merge|release)", text, re.I):
        return "", ""
    if text in ("继续", "继续推进", "继续研发", "继续处理", "继续分析", "继续修复", "继续开发"):
        return "resume", ""
    for mode, pattern in (
            ("review", r"\A(?:代码审查|审查|review)"),
            ("edit", r"\A(?:按方案修复|按方案开发|按方案实现|修复|实现|开发|重构|修改|补充回归测试|增加回归测试|fix|implement)"),
            ("explain", r"\A(?:全面分析|分析|检查|解释|定位|调查|评估|说明|给出方案)")):
        match = re.match(pattern, text, re.I)
        if match:
            scope = text[match.end():].strip(" \t\r\n，。:：、;；")
            if scope in ("一下","这个","这个缺陷","这个需求","这个文档","该缺陷","该需求","该文档","问题","缺陷","需求","按方案"):
                scope = ""
            return mode, scope
    return "", text


def topic_key(message_id: str, root_id: str = "", thread_id: str = "",
              parent_id: str = "") -> str:
    """Never infer a conversation from the last task or an unverified parent."""
    _check_id(message_id, "message_id")
    if root_id:
        return "root:" + _check_id(root_id, "root_id")
    if thread_id:
        return "thread:" + _check_id(thread_id, "thread_id")
    if parent_id:
        raise IntakeRejected("reply lacks reliable root/thread identity")
    return "root:" + message_id


class LinkContextService:
    def __init__(self, store):
        self.store = store
        with store._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS engineering_contexts (
                    context_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL, chat TEXT NOT NULL, actor TEXT NOT NULL,
                    topic TEXT NOT NULL, repo TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                    UNIQUE(tenant,chat,actor,topic)
                );
                CREATE TABLE IF NOT EXISTS engineering_context_sources (
                    context_id TEXT NOT NULL REFERENCES engineering_contexts(context_id),
                    url TEXT NOT NULL, provider TEXT NOT NULL, space TEXT NOT NULL,
                    url_type TEXT NOT NULL, kind TEXT NOT NULL, item_id TEXT NOT NULL,
                    source_level TEXT NOT NULL CHECK(source_level='link_unverified'),
                    PRIMARY KEY(context_id,url)
                );
                CREATE TABLE IF NOT EXISTS engineering_context_events (
                    event_key TEXT PRIMARY KEY,
                    context_id TEXT NOT NULL REFERENCES engineering_contexts(context_id),
                    message_id TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    has_context_note INTEGER NOT NULL CHECK(has_context_note IN (0,1)),
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS engineering_context_events_context
                    ON engineering_context_events(context_id,created_at);
                CREATE TABLE IF NOT EXISTS engineering_context_tasks (
                    task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
                    context_id TEXT NOT NULL REFERENCES engineering_contexts(context_id),
                    event_key TEXT NOT NULL UNIQUE REFERENCES engineering_context_events(event_key),
                    policy_sha256 TEXT NOT NULL, sources_sha256 TEXT NOT NULL,
                    previous_task_id INTEGER NOT NULL DEFAULT 0,
                    root_task_id INTEGER NOT NULL DEFAULT 0,
                    thread_id TEXT NOT NULL DEFAULT '', cwd TEXT NOT NULL DEFAULT '',
                    host TEXT NOT NULL DEFAULT '', codex_home TEXT NOT NULL DEFAULT '',
                    branch TEXT NOT NULL DEFAULT '', commit_sha TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS engineering_context_tasks_context
                    ON engineering_context_tasks(context_id,task_id);
            """)

    def exists(self, event: InboundEvent, topic: str) -> bool:
        with self.store._connect() as db:
            return db.execute(
                "SELECT 1 FROM engineering_contexts WHERE tenant=? AND chat=? AND actor=? AND topic=?",
                (event.tenant,event.chat,event.actor,topic),
            ).fetchone() is not None

    @staticmethod
    def _choose_repo(existing: str, explicit: str, primary: Optional[EngineeringSource],
                     allowed: frozenset, routes: Mapping[str, Sequence[str]]) -> str:
        if explicit:
            if explicit not in allowed:
                raise IntakeRejected("repository not authorized")
            return explicit
        if existing:
            if existing not in allowed:
                raise IntakeRejected("previous repository no longer authorized")
            return existing
        if primary is not None:
            # A lone configured repository is not necessarily the product's repository.
            candidates = set(routes.get(primary.route_key, ())) & allowed
        else:
            candidates = set(allowed)
        return next(iter(candidates)) if len(candidates) == 1 else ""

    def handle(self, event: InboundEvent, topic: str, allowed_repos: Iterable[str],
               routes: Mapping[str, Sequence[str]]) -> IntakeResult:
        allowed = frozenset(check_repo_alias(repo) for repo in allowed_repos)
        if not allowed:
            raise IntakeRejected("no authorized repositories")
        if not re.fullmatch(r"(?:root|thread):[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", topic):
            raise IntakeRejected("invalid topic identity")
        body = event.text.strip()
        control = body.lower() in _CONTROL
        match = _REPO.match(body)
        explicit = match.group(1).lower() if match else ""
        if body.startswith("/") and not control and not (match and body.startswith("/repo ") and match.end() == len(body)):
            raise IntakeRejected("unknown control in engineering topic")
        incoming = parse_sources(body)
        intent, scope_text = intent_for(body)
        if control or body.startswith("/"):
            intent = ""
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            scope = (event.tenant,event.chat,event.actor,topic)
            previous = db.execute(
                "SELECT context_id,content_sha256 FROM engineering_context_events WHERE event_key=?",
                (event.event_key,),
            ).fetchone()
            ctx = db.execute(
                "SELECT context_id,repo FROM engineering_contexts WHERE tenant=? AND chat=? AND actor=? AND topic=?",
                scope,
            ).fetchone()
            if previous is not None:
                if (ctx is None or previous["context_id"] != ctx["context_id"]
                        or previous["content_sha256"] != event.content_digest
                        or (ctx["repo"] and ctx["repo"] not in allowed)):
                    raise EventConflict("same event changed or no longer authorized")
                return IntakeResult(True)
            if ctx is None and not incoming and not (intent and scope_text):
                return IntakeResult(False)
            cid = ctx["context_id"] if ctx else uuid.uuid4().hex
            existing = tuple(EngineeringSource(r["provider"],r["space"],r["url_type"],
                            r["kind"],r["item_id"],r["url"]) for r in db.execute(
                "SELECT * FROM engineering_context_sources WHERE context_id=? ORDER BY url", (cid,)))
            merged = tuple(dict.fromkeys(existing + incoming))
            primary = [s for s in merged if s.is_workitem]
            if len(primary) > 1:
                raise IntakeRejected("different primary work item; start a new topic")
            if len(merged) > MAX_SOURCES:
                raise IntakeRejected("source limit exceeded")
            repo = self._choose_repo(ctx["repo"] if ctx else "", explicit,
                                    primary[0] if primary else None, allowed, routes)
            if ctx and repo != ctx["repo"] and db.execute(
                    "SELECT 1 FROM engineering_context_tasks WHERE context_id=? LIMIT 1", (cid,)
            ).fetchone():
                raise IntakeRejected("repository already bound to execution; start a new topic")
            now = int(time.time())
            if ctx is None:
                db.execute(
                    "INSERT INTO engineering_contexts(context_id,tenant,chat,actor,topic,repo,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (cid,*scope,repo,now,now),
                )
            else:
                db.execute("UPDATE engineering_contexts SET repo=?,updated_at=? WHERE context_id=?",
                           (repo,now,cid))
            for source in incoming:
                db.execute(
                    "INSERT OR IGNORE INTO engineering_context_sources(context_id,url,provider,space,url_type,kind,item_id,source_level) VALUES (?,?,?,?,?,?,?,'link_unverified')",
                    (cid,source.url,source.provider,source.space,source.url_type,source.kind,source.item_id),
                )
            has_note = bool(scope_text.strip(" \r\n\t，。:：、;；")) and not control and not body.startswith("/")
            db.execute(
                "INSERT INTO engineering_context_events(event_key,context_id,message_id,content_sha256,has_context_note,created_at) VALUES (?,?,?,?,?,?)",
                (event.event_key,cid,event.event_id,event.content_digest,int(has_note),now),
            )
            notes = db.execute(
                "SELECT COUNT(*) FROM engineering_context_events WHERE context_id=? AND has_context_note=1",
                (cid,),
            ).fetchone()[0]
            if body.lower() == "/new":
                return IntakeResult(True, "请在新话题发送研发链接；不会覆盖当前事项。")
            if body.lower() in ("/cancel","cancel","取消","停止任务"):
                latest = db.execute(
                    "SELECT t.status FROM engineering_context_tasks c JOIN tasks t ON t.id=c.task_id WHERE c.context_id=? ORDER BY t.id DESC LIMIT 1", (cid,),
                ).fetchone()
                if latest is None:
                    return IntakeResult(True, "当前链接事项没有关联的执行任务；未取消其他话题的任务。")
                return IntakeResult(True, "", cid, repo, "cancel", "", topic)
            lines = ["已关联当前话题的研发事项（未启动 Codex）。"]
            if primary:
                source = primary[0]
                lines.extend([
                    ("缺陷" if source.kind == "defect" else "需求") + " #" + source.item_id,
                    "项目空间：" + source.space,
                    "工单链接：" + source.url,
                    "来源：链接解析，原系统正文和类型尚未核验。",
                ])
            elif merged:
                lines.append("文档驱动研发事项；尚未读取文档正文。")
            else:
                lines.append("独立研发事项，不依赖外部工单。")
            documents = [s for s in merged if s.kind == "document"]
            if documents:
                lines.append("关联文档：" + str(len(documents)) + " 份（尚未读取）")
            lines.append("研发仓库：" + (repo or "待定位；请在本话题发送 /repo <已授权别名>"))
            lines.append("补充消息引用：" + str(notes) + " 条；仅留消息标识和摘要哈希，未读取正文。")
            latest = db.execute(
                "SELECT t.id,t.status,t.mode FROM engineering_context_tasks c JOIN tasks t ON t.id=c.task_id WHERE c.context_id=? ORDER BY t.id DESC LIMIT 1", (cid,),
            ).fetchone()
            if latest:
                lines.append("最近执行：#" + str(latest["id"]) + " " + latest["mode"] + " " + latest["status"])
            lines.append("可在同一话题补充资料、明确要求分析/修复/开发，或 /status 查看关联。")
            return IntakeResult(True, "\n".join(lines), cid, repo, intent, scope_text, topic)
