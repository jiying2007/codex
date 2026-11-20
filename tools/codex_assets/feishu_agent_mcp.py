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
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.store = StateStore(config.state_db)
        self.spool = TaskSpool(config.state_db.parent / "feishu-pending-jobs")
        self.sender = f"agent:{os.getuid()}"

    def _enabled(self) -> None:
        if not self.config.agent_intake_enabled:
            raise FeishuCodexError("可信本机 Agent 入口未获允许")

    def submit_task(self, repo: str, mode: str, task: str, idempotency_key: str) -> dict[str, Any]:
        self._enabled()
        if not all(isinstance(value, str) for value in (repo, mode, task, idempotency_key)):
            raise FeishuCodexError("Agent 任务字段必须是字符串")
        if not REQUEST_KEY.fullmatch(idempotency_key):
            raise FeishuCodexError("幂等键必须是 8–128 字符的简单标识")
        repository = self.config.repositories.get(repo)
        if repository is None or mode not in repository.agent_allowed_modes:
            raise FeishuCodexError("仓库或 Agent 任务模式未获允许")
        if mode == "edit" and repository.edit_strategy != "worktree":
            raise FeishuCodexError("Agent 修改必须使用 worktree 隔离")
        if not task.strip() or len(task) > self.config.max_prompt_chars:
            raise FeishuCodexError("Agent 任务为空或超出提示预算")
        digest = hashlib.sha256(json.dumps(
            {"repo": repo, "mode": mode, "task": task},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        message_id = "agent:" + hashlib.sha256(
            (self.sender + "\0" + idempotency_key).encode("utf-8")
        ).hexdigest()
        task_id, created = self.store.create_agent_task(
            message_id, self.sender, repo, mode, digest, self.config.queue_size,
        )
        if created:
            job = BotJob(task_id, message_id, self.config.target_chat_id, self.sender,
                         "task", repo, mode, task)
            try:
                self.spool.put(task_id, dataclasses.asdict(job))
            except (OSError, SpoolError):
                self.store.update_task(task_id, "unknown", "AgentInputPersistFailed")
                raise FeishuCodexError("任务输入持久化失败，禁止自动重复执行") from None
        result = self.get_task(task_id)
        result["created"] = created
        return result

    def get_task(self, task_id: int) -> dict[str, Any]:
        self._enabled()
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise FeishuCodexError("无效 Agent 任务 ID")
        detail = self.store.agent_task_detail(task_id, self.sender)
        if detail is None:
            raise FeishuCodexError("任务不存在或不属于本机 Agent 用户")
        return detail

    def cancel_queued_task(self, task_id: int) -> dict[str, Any]:
        self.get_task(task_id)
        canceled = self.store.cancel_agent_queued(task_id, self.sender)
        if canceled:
            try:
                self.spool.discard(task_id)
            except OSError:
                raise FeishuCodexError("任务已取消，但私有输入清理失败，需人工核验") from None
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
                "get_task": {"task_id"}, "cancel_queued_task": {"task_id"},
            }
            if not isinstance(args, dict) or name not in known or set(args) != known[name]:
                raise FeishuCodexError("工具名称或参数不符合最小受控接口")
            if name == "submit_task":
                value = intake.submit_task(**args)
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
    return AgentTaskIntake(BotConfig.from_values(values, root))


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
