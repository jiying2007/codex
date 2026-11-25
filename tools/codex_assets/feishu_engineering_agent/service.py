"""Authenticated topic intake and atomic admission on the private Bot SQLite.

Only the worker launches a model. A paid message's context and queue receipt
are committed together; accepted user context is available without a second
Feishu message-history API call.
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
    "/new", "/repo", "当前项目", "/result", "查看结果", "获取结果",
    "检查 ci", "检查ci", "检查交付", "交付反馈", "生成研发反馈", "查看交付",
    "检查联合交付",
}
# Note bodies are private input, not audit output. Old hashes remain after
# expiry; an incomplete context is rejected rather than silently reconstructed.
NOTE_RETENTION_SECONDS = 7 * 24 * 60 * 60
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
    # Continue the exact existing thread; the suffix remains task context.
    continuation = re.fullmatch(r"(?:继续推进|继续研发|继续处理|继续分析|继续修复|继续开发|继续)(?:[\s，,。；;：:]+(.*))?", text, re.S)
    if continuation:
        return "resume", (continuation.group(1) or "").strip()
    if text == "全面推进":
        return "resume", ""
    if re.match(r"\A(?:按建议|按方案)(?:全部|全面)?(?:优化|推进|完成|落地)", text):
        return "edit", text
    for mode, pattern in (
            ("review", r"\A(?:全面深度审查|深度审查|全面审查|代码审查|审查|review)"),
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
                CREATE TABLE IF NOT EXISTS engineering_context_event_targets (
                    event_key TEXT PRIMARY KEY REFERENCES engineering_context_events(event_key),
                    repository TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS engineering_context_events_context
                    ON engineering_context_events(context_id,created_at);
                CREATE TABLE IF NOT EXISTS engineering_context_note_inputs (
                    event_key TEXT PRIMARY KEY REFERENCES engineering_context_events(event_key),
                    body TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS engineering_context_note_expiry
                    ON engineering_context_note_inputs(expires_at);
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
                -- Backfill former single-repository contexts without rewriting targets.
                INSERT OR IGNORE INTO engineering_context_event_targets(event_key,repository)
                    SELECT e.event_key,COALESCE(t.repository,c.repo)
                    FROM engineering_context_events e JOIN engineering_contexts c ON c.context_id=e.context_id
                    LEFT JOIN engineering_context_tasks x ON x.event_key=e.event_key
                    LEFT JOIN tasks t ON t.id=x.task_id;
                CREATE TABLE IF NOT EXISTS engineering_context_delivery (
                    task_id INTEGER PRIMARY KEY REFERENCES engineering_context_tasks(task_id),
                    head_sha TEXT NOT NULL, repository TEXT NOT NULL,
                    pr_number INTEGER NOT NULL, proof_json TEXT NOT NULL,
                    verified_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS engineering_context_joint_delivery (
                    context_id TEXT NOT NULL REFERENCES engineering_contexts(context_id),
                    head_set_sha256 TEXT NOT NULL, proof_json TEXT NOT NULL,
                    verified_at INTEGER NOT NULL,
                    PRIMARY KEY(context_id,head_set_sha256)
                );
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
               routes: Mapping[str, Sequence[str]], *, admit=None) -> IntakeResult:
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
        shared_note = body.startswith(("共享上下文：","共享上下文:"))
        if shared_note:
            scope_text = body[6:].strip()
            intent = ""
            if not scope_text:
                raise IntakeRejected("shared context requires concrete text")
        if control or body.startswith("/"):
            intent = ""
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM engineering_context_note_inputs WHERE expires_at<=?", (int(time.time()),))
            scope = (event.tenant,event.chat,event.actor,topic)
            previous = db.execute(
                "SELECT e.context_id,e.content_sha256,v.repository FROM engineering_context_events e "
                "JOIN engineering_context_event_targets v ON v.event_key=e.event_key WHERE e.event_key=?",
                (event.event_key,),
            ).fetchone()
            ctx = db.execute(
                "SELECT context_id,repo FROM engineering_contexts WHERE tenant=? AND chat=? AND actor=? AND topic=?",
                scope,
            ).fetchone()
            if previous is not None:
                if (ctx is None or previous["context_id"] != ctx["context_id"]
                        or previous["content_sha256"] != event.content_digest
                        or (previous["repository"] and previous["repository"] not in allowed)):
                    raise EventConflict("same event changed or no longer authorized")
                return IntakeResult(True)
            # Do not reinterpret a pre-cutover Feishu event as a new paid turn.
            if db.execute("SELECT 1 FROM messages WHERE message_id=?",(event.event_id,)).fetchone():
                return IntakeResult(True)
            if (db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='engineering_legacy_events'").fetchone()
                    and db.execute("SELECT 1 FROM engineering_legacy_events WHERE message_id=?",(event.event_id,)).fetchone()):
                return IntakeResult(True)
            if shared_note and ctx is None:
                raise IntakeRejected("共享上下文必须属于已建立的研发话题")
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
            db.execute("INSERT INTO engineering_context_event_targets(event_key,repository) VALUES (?,?)",
                       (event.event_key,"" if shared_note else repo))
            if has_note:
                db.execute("INSERT INTO engineering_context_note_inputs VALUES (?,?,?)",
                           (event.event_key,event.text,now + NOTE_RETENTION_SECONDS))
            notes = db.execute(
                "SELECT COUNT(*) FROM engineering_context_events e JOIN engineering_context_event_targets v "
                "ON v.event_key=e.event_key WHERE e.context_id=? AND e.has_context_note=1 AND v.repository IN ('',?)",
                (cid,repo),
            ).fetchone()[0]
            if body.lower() == "/new":
                return IntakeResult(True, "请在新话题发送研发链接；不会覆盖当前事项。")
            if body.lower() in ("/cancel","cancel","取消","停止任务"):
                latest = db.execute(
                    "SELECT t.status FROM engineering_context_tasks c JOIN tasks t ON t.id=c.task_id "
                    "WHERE c.context_id=? AND t.repository=? ORDER BY t.id DESC LIMIT 1", (cid,repo),
                ).fetchone()
                if latest is None:
                    return IntakeResult(True, "当前链接事项没有关联的执行任务；未取消其他话题的任务。")
                return IntakeResult(True, "", cid, repo, "cancel", "", topic)
            if body.lower() in ("/result","查看结果","获取结果"):
                return IntakeResult(True,"",cid,repo,"result","",topic)
            if body == "检查联合交付":
                return IntakeResult(True,"",cid,repo,"joint_delivery","",topic)
            if body.lower() in ("检查 ci","检查ci","检查交付","查看交付","交付反馈","生成研发反馈"):
                return IntakeResult(True,"",cid,repo,
                    "feedback" if body.lower() in ("交付反馈","生成研发反馈") else "delivery","",topic)
            lines = ["已关联当前话题的研发事项（未启动 Codex）。"]
            if primary:
                source = primary[0]
                lines.extend([
                    ("缺陷" if source.kind == "defect" else "需求") + " #" + source.item_id,
                    "项目空间：" + source.space,
                    "工单链接：" + source.url,
                    "来源：链接解析，原系统正文和类型尚未核验。",
                ])
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='engineering_legacy_runs'").fetchone():
                    historic=db.execute(
                        "SELECT COUNT(*) FROM engineering_legacy_runs WHERE tenant=? AND chat=? AND actor=? AND provider=? AND workspace=? AND kind=? AND item_id=?",
                        (event.tenant,event.chat,event.actor,source.provider,source.space,source.kind,source.item_id),
                    ).fetchone()[0]
                    if historic:
                        lines.append("关联历史归档记录："+str(historic)+" 条；未自动恢复旧会话或执行。")
            elif merged:
                lines.append("文档驱动研发事项；尚未读取文档正文。")
            else:
                lines.append("独立研发事项，不依赖外部工单。")
            documents = [s for s in merged if s.kind == "document"]
            if documents:
                lines.append("关联文档：" + str(len(documents)) + " 份（尚未读取）")
            lines.append("研发仓库：" + (repo or "待定位；请在本话题发送 /repo <已授权别名>"))
            lines.append("补充消息引用：" + str(notes) + " 条；必要正文在私有状态中有期限保留。")
            latest = db.execute(
                "SELECT t.id,t.repository,t.status,t.mode FROM engineering_context_tasks c JOIN tasks t ON t.id=c.task_id "
                "WHERE c.context_id=? AND t.id IN (SELECT MAX(y.task_id) FROM engineering_context_tasks y "
                "JOIN tasks q ON q.id=y.task_id WHERE y.context_id=? GROUP BY q.repository) ORDER BY t.repository", (cid,cid),
            ).fetchall()
            for task in latest:
                if task["repository"] in allowed:
                    lines.append("最近执行："+task["repository"]+" #"+str(task["id"])+" "+task["mode"]+" "+task["status"])
            lines.append("可用 /repo 切换已授权仓库；共享上下文：<接口或联调事实> 供同事项各仓使用；/cancel 仅取消当前仓库；检查联合交付核验多仓精确版本。")
            result = IntakeResult(True, "\n".join(lines), cid, repo, intent, scope_text, topic)
            if admit is not None and intent in ("explain", "review", "edit", "resume"):
                from ..feishu_codex_bot import FeishuCodexError
                try:
                    reply = admit(event, result, connection=db)
                except FeishuCodexError as exc:
                    # Expected refusal (or an explicitly persisted UNKNOWN)
                    # is terminal for this event; retain the accepted context.
                    reply = str(exc)
                except IntakeRejected:
                    reply = "研发资格或输入核验未通过；未启动模型。"
                return dataclasses.replace(result, reply=result.reply+"\n"+reply, intent="")
            return result
