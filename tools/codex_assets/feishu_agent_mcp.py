"""Trusted same-user MCP stdio intake for the existing Feishu Codex service.

No new runner, no network listener, no model call from this process. Jobs are
validated, queued in the Bot's SQLite and private spool, and picked up by the
already running service. Do not expose this same-UID interface to untrusted users.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any, Mapping, Optional

from .feishu_codex_bot import (
    BotConfig, BotJob, FeishuCodexError, StateStore, merged_environment,
)
from .feishu_task_spool import TaskSpool, SpoolError


PROTOCOL_VERSION = "2025-06-18"
REQUEST_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\Z")
MAX_LINE_BYTES = 65536


class AgentTaskIntake:
    def __init__(self, config: BotConfig, billing_source: Optional[str] = None) -> None:
        self.config = config
        self.store = StateStore(config.state_db)
        self.spool = TaskSpool(config.state_db.parent / "feishu-pending-jobs")
        self.sender = f"agent:{os.getuid()}"
        source = config.agent_billing_source if billing_source is None else billing_source
        self.billing_source = str(source or "unapproved").strip().lower()

    def _enabled(self) -> None:
        if not self.config.agent_intake_enabled:
            raise FeishuCodexError("可信本机 Agent 入口未获允许")

    def _manual_store(self):
        if not self.config.manual_workitems_enabled:
            raise FeishuCodexError("WorkItem AgentRun bridge is disabled")
        from .feishu_engineering_agent.manual_items import ManualWorkItemService
        manual_db = self.config.state_db.with_name("feishu-engineering-agent.sqlite3")
        if manual_db == self.config.state_db:
            raise FeishuCodexError("AgentRun DB must be separate from legacy Bot state")
        return ManualWorkItemService(manual_db).store

    def _mark_workitem_run_unknown(self, run_id: str) -> None:
        try:
            store = self._manual_store()
            record = store.get_run(run_id)
            if record["status"] in ("queued", "running"):
                store.transition(run_id, record["revision"], "unknown", record["actor"])
        except Exception:
            # The old task receipt remains UNKNOWN even if the second ledger is unavailable.
            pass

    def _queue_task(
        self, repo: str, mode: str, task: str, idempotency_key: str,
        agent_run_id: str = "",
    ) -> dict[str, Any]:
        if not all(isinstance(value, str) for value in (repo, mode, task, idempotency_key)):
            raise FeishuCodexError("Agent 任务字段必须是字符串")
        if not REQUEST_KEY.fullmatch(idempotency_key):
            raise FeishuCodexError("幂等键必须是 8–128 字符的简单标识")
        repository = self.config.repositories.get(repo)
        if repository is None or mode not in repository.agent_allowed_modes:
            raise FeishuCodexError("仓库或 Agent 任务模式未获允许")
        if mode == "edit" and (
                repository.edit_strategy != "worktree" or not repository.commit_enabled):
            raise FeishuCodexError("Agent 修改必须使用可提交的 worktree 隔离")
        if not task.strip() or len(task) > self.config.max_prompt_chars:
            raise FeishuCodexError("Agent 任务为空或超出提示预算")
        digest = hashlib.sha256(json.dumps(
            {"repo": repo, "mode": mode, "task": task},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        message_id = "agent:" + hashlib.sha256(
            (self.sender + "\\0" + idempotency_key).encode("utf-8")
        ).hexdigest()
        task_id, created = self.store.create_agent_task(
            message_id, self.sender, repo, mode, digest, self.config.queue_size,
        )
        if agent_run_id:
            if not created:
                existing_link = self.store.agent_run_link_for_task(task_id)
                if (existing_link is None
                        or existing_link["agent_run_id"] != agent_run_id
                        or existing_link["unix_uid"] != os.getuid()):
                    raise FeishuCodexError(
                        "existing task has no matching AgentRun receipt; reconcile manually, never rebind"
                    )
            else:
                try:
                    self.store.link_agent_run_task(agent_run_id, task_id, os.getuid())
                except Exception:
                    self.store.update_task(task_id, "unknown", "AgentRunLinkFailed")
                    self._mark_workitem_run_unknown(agent_run_id)
                    raise
        if created:
            job = BotJob(task_id, message_id, self.config.target_chat_id, self.sender,
                         "task", repo, mode, task)
            try:
                self.spool.put(task_id, dataclasses.asdict(job))
            except (OSError, SpoolError):
                self.store.update_task(task_id, "unknown", "AgentInputPersistFailed")
                if agent_run_id:
                    self._mark_workitem_run_unknown(agent_run_id)
                raise FeishuCodexError("任务输入持久化失败，禁止自动重复执行") from None
        elif agent_run_id:
            detail = self.store.agent_task_detail(task_id, self.sender)
            if detail is None:
                raise FeishuCodexError("existing local Agent task is not owned by this Unix user")
            if detail["status"] == "queued":
                try:
                    self.spool.get(task_id)
                except (FileNotFoundError, OSError, SpoolError):
                    self.store.update_task(task_id, "unknown", "AgentQueuedPayloadUnavailable")
                    self._mark_workitem_run_unknown(agent_run_id)
                    raise FeishuCodexError("既有任务缺少可信输入，状态已置为 UNKNOWN，禁止重放") from None
        result = self.get_task(task_id)
        result["created"] = created
        return result

    def submit_task(self, repo: str, mode: str, task: str, idempotency_key: str) -> dict[str, Any]:
        self._enabled()
        return self._queue_task(repo, mode, task, idempotency_key)

    def submit_workitem_task(self, run_id: str, task: str) -> dict[str, Any]:
        """Queue an exact manual WorkItem attempt through the existing Bot worker.

        This local-MCP lane is separate from Feishu chat and from App Server
        HMAC grants. It requires the same Unix UID, both operator feature flags,
        the repo's agent mode allowlist, a scope hash match, and an explicitly
        declared non-shared billing source.
        """
        self._enabled()
        store = self._manual_store()
        if self.billing_source not in ("external_api_key", "external_gateway", "self_hosted"):
            raise FeishuCodexError(
                "WorkItem execution needs FEISHU_AGENT_BILLING_SOURCE="
                "external_api_key|external_gateway|self_hosted; shared quota is denied"
            )
        if (not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id)
                or not isinstance(task, str) or not task.strip()
                or len(task) > self.config.max_prompt_chars or "\\x00" in task):
            raise FeishuCodexError("invalid WorkItem Run ID or bounded task text")
        record = store.get_run(run_id)
        repository = self.config.repositories.get(record["repo"])
        if repository is None or not self.config.sender_allowed(record["actor"], repository):
            raise FeishuCodexError("WorkItem owner or repository access is no longer authorized")
        run_mode = record["mode"]
        bot_mode = {"read": "explain", "review": "review", "edit": "edit"}.get(run_mode)
        if (bot_mode is None or bot_mode not in repository.allowed_modes
                or bot_mode not in repository.agent_allowed_modes):
            raise FeishuCodexError("WorkItem execution mode is not allowed by the current repository policy")
        if run_mode == "edit" and (
                repository.edit_strategy != "worktree" or not repository.commit_enabled):
            raise FeishuCodexError("WorkItem edit requires an isolated, locally committable worktree")
        scope_sha256 = hashlib.sha256(task.encode("utf-8")).hexdigest()
        from .feishu_engineering_agent.models import InboundEvent
        from .feishu_engineering_agent.workflow import (
            EngineeringWorkflow, local_agent_policy_digest,
        )
        event_id = "local-agent-" + hashlib.sha256(
            (run_id + "\\0" + self.sender).encode("utf-8")
        ).hexdigest()[:32]
        event = InboundEvent(
            "feishu_message", record["tenant"], record["chat"],
            record["actor"], event_id, task,
        )
        policy_sha256 = local_agent_policy_digest(
            os.getuid(), record["repo"], run_mode, self.billing_source,
            repository.agent_allowed_modes, repository.edit_strategy,
            repository.commit_enabled,
        )
        workflow = EngineeringWorkflow(store)
        workflow.authorize_local_agent_queue(
            run_id, event, os.getuid(), {record["repo"]}, {run_mode},
            scope_sha256, self.billing_source, policy_sha256,
        )
        try:
            result = self._queue_task(
                record["repo"], bot_mode, task, "workitem-" + run_id,
                agent_run_id=run_id,
            )
        except FeishuCodexError:
            current = store.get_run(run_id)
            if current["status"] == "queued":
                try:
                    store.transition(run_id, current["revision"], "blocked", current["actor"])
                except Exception:
                    pass
            raise
        result["agent_run_id"] = run_id
        result["run_status"] = store.get_run(run_id)["status"]
        return result

    def get_task(self, task_id: int) -> dict[str, Any]:
        self._enabled()
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise FeishuCodexError("无效 Agent 任务 ID")
        detail = self.store.agent_task_detail(task_id, self.sender)
        if detail is None:
            raise FeishuCodexError("任务不存在或不属于本机 Agent 用户")
        return detail

    def get_workitem_task(self, run_id: str) -> dict[str, Any]:
        self._enabled()
        store = self._manual_store()
        from .feishu_engineering_agent.workflow import EngineeringWorkflow
        approval = EngineeringWorkflow(store).local_agent_approval(run_id)
        if approval["unix_uid"] != os.getuid():
            raise FeishuCodexError("AgentRun belongs to another local Unix user")
        record = store.get_run(run_id)
        link = self.store.agent_run_link_for_run(run_id)
        task = None
        if link is not None:
            task = self.store.agent_task_detail(link["task_id"], self.sender)
            if task is None:
                raise FeishuCodexError("linked Agent task is not owned by this local Unix user")
        return {"agent_run_id": run_id, "run_status": record["status"],
                "task": task, "billing_source": approval["billing_source"]}

    def cancel_queued_task(self, task_id: int) -> dict[str, Any]:
        self.get_task(task_id)
        canceled = self.store.cancel_agent_queued(task_id, self.sender)
        if canceled:
            try:
                self.spool.discard(task_id)
            except OSError:
                raise FeishuCodexError("任务已取消，但私有输入清理失败，需人工核验") from None
            link = self.store.agent_run_link_for_task(task_id)
            if link is not None:
                try:
                    store = self._manual_store()
                    record = store.get_run(link["agent_run_id"])
                    if record["status"] == "queued":
                        store.transition(
                            link["agent_run_id"], record["revision"],
                            "canceled", record["actor"],
                        )
                except Exception:
                    raise FeishuCodexError("任务已取消，但 AgentRun 状态未能同步，需人工核验") from None
        result = self.get_task(task_id)
        result["queued_cancelled"] = canceled
        result["running_cancel_requires_feishu"] = result["status"] == "running"
        return result


TOOLS = [
    {
        "name": "submit_task",
        "description": "Idempotently queue an allowed repo task for the existing Feishu Codex service. No model call in this MCP process.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "mode": {"type": "string", "enum": ["explain", "review", "edit"]},
                "task": {"type": "string"},
                "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 128},
            },
            "required": ["repo", "mode", "task", "idempotency_key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "submit_workitem_task",
        "description": "Bind an exact manually registered Feishu/TAPD WorkItem AgentRun to the existing Bot queue. Requires the same Unix UID, manual WorkItem mode, repo agent allowlist, exact scope hash and a declared non-shared billing source.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
                "task": {"type": "string", "minLength": 1, "maxLength": 12000},
            },
            "required": ["run_id", "task"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_workitem_task",
        "description": "Read the AgentRun status and its linked existing-Bot task status without returning the prompt or model output.",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_task",
        "description": "Read bounded status / Git result metadata for this local user's submitted task, not prompt or model output.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer", "minimum": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "cancel_queued_task",
        "description": "Cancel a queued task. This cannot cancel running Codex or unknown external effects.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer", "minimum": 1}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
]


def handle_request(request: Any, intake: AgentTaskIntake) -> Optional[dict[str, Any]]:
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    ident, method = request.get("id"), request.get("method")
    if not isinstance(method, str):
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32600, "message": "Invalid Method"}}
    if ident is None:
        return None  # notifications/initialized, cancellations etc. never execute tools
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}},
            "serverInfo": {"name": "feishu-codex-agent-tasks", "version": "0.1.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name") if isinstance(params, dict) else None
        args = params.get("arguments", {}) if isinstance(params, dict) else None
        try:
            known = {
                "submit_task": {"repo", "mode", "task", "idempotency_key"},
                "submit_workitem_task": {"run_id", "task"},
                "get_workitem_task": {"run_id"},
                "get_task": {"task_id"}, "cancel_queued_task": {"task_id"},
            }
            if not isinstance(args, dict) or name not in known or set(args) != known[name]:
                raise FeishuCodexError("工具名称或参数不符合最小受控接口")
            if name == "submit_task":
                value = intake.submit_task(**args)
            elif name == "submit_workitem_task":
                value = intake.submit_workitem_task(**args)
            elif name == "get_workitem_task":
                value = intake.get_workitem_task(**args)
            elif name == "get_task":
                value = intake.get_task(**args)
            else:
                value = intake.cancel_queued_task(**args)
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
        except (FeishuCodexError, OSError, ValueError) as exc:
            note = str(exc)[:180] if isinstance(exc, FeishuCodexError) else "本机任务状态不可用"
            result = {"content": [{"type": "text", "text": note}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def load_intake() -> AgentTaskIntake:
    root = pathlib.Path(__file__).resolve().parents[2]
    env_file = pathlib.Path(os.environ.get(
        "FEISHU_AGENT_ENV_FILE", str(root / "mcp/secrets/feishu.env"),
    )).expanduser().resolve()
    values = merged_environment(env_file, os.environ)
    return AgentTaskIntake(
        BotConfig.from_values(values, root),
        billing_source=values.get("FEISHU_AGENT_BILLING_SOURCE", "unapproved"),
    )


def main() -> int:
    try:
        intake = load_intake()
        intake._enabled()
    except (FeishuCodexError, OSError, SpoolError):
        print("local Agent MCP is disabled or misconfigured", file=sys.stderr)
        return 2
    # Readline is bounded: no raw prompt or secret may be echoed to stdout.
    while True:
        line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not line:
            return 0
        if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
            print("MCP message exceeds bound", file=sys.stderr)
            return 2
        try:
            reply = handle_request(json.loads(line), intake)
        except (ValueError, UnicodeError):
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
