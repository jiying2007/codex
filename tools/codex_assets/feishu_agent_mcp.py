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
import sqlite3
import sys
from typing import Any, Mapping, Optional

from .feishu_codex_bot import (
    AgentInputPersistError, BotConfig, BotJob, FeishuCodexError, StateStore,
    merged_environment, open_workitem_service, resolve_worker_resume,
)
from .feishu_task_spool import TaskSpool, SpoolError


PROTOCOL_VERSION = "2025-06-18"
REQUEST_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\Z")
MAX_LINE_BYTES = 65536


class AgentTaskIntake:
    def __init__(self, config: BotConfig, billing_source: Optional[str] = None, *,
                 github_read_token: Optional[str] = None, qa_reviewer: str = "",
                 qa_key_hex: str = "") -> None:
        self.config = config
        self.store = StateStore(config.state_db)
        self.spool = TaskSpool(config.state_db.parent / "feishu-pending-jobs")
        self.sender = f"agent:{os.getuid()}"
        source = config.agent_billing_source if billing_source is None else billing_source
        self.billing_source = str(source or "unapproved").strip().lower()
        self.github_read_token = (
            config.agent_github_read_token if github_read_token is None else github_read_token
        )
        self.qa_reviewer = qa_reviewer
        self.qa_key_hex = qa_key_hex

    def _enabled(self) -> None:
        if not self.config.agent_intake_enabled:
            raise FeishuCodexError("可信本机 Agent 入口未获允许")

    def _require_billing_source(self) -> None:
        self.config.validate_agent_runtime()
        if (self.billing_source not in (
                "external_api_key", "external_gateway", "self_hosted")
                or self.billing_source != self.config.agent_billing_source):
            raise FeishuCodexError(
                "本机 Agent 任务必须使用服务私有配置中的独立非共享计费身份"
            )

    def _manual_store(self):
        return open_workitem_service(self.config, self.store).store

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
        if (not task.strip() or len(task) > self.config.max_prompt_chars
                or "\x00" in task):
            raise FeishuCodexError("Agent 任务为空、包含 NUL 或超出提示预算")
        digest = hashlib.sha256(json.dumps(
            {"repo": repo, "mode": mode, "task": task},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        message_id = "agent:" + hashlib.sha256(
            (self.sender + "\0" + idempotency_key).encode("utf-8")
        ).hexdigest()
        def publish(task_id: int) -> None:
            job = BotJob(task_id, message_id, self.config.target_chat_id, self.sender,
                         "task", repo, mode, task)
            self.spool.put(task_id, dataclasses.asdict(job))

        try:
            task_id, created = self.store.create_agent_task(
                message_id, self.sender, repo, mode, digest, self.config.queue_size,
                agent_run_id=agent_run_id, publish_payload=publish,
            )
        except AgentInputPersistError:
            if agent_run_id:
                self._mark_workitem_run_unknown(agent_run_id)
            raise
        if agent_run_id and not created:
            existing_link = self.store.agent_run_link_for_task(task_id)
            if (existing_link is None
                    or existing_link["agent_run_id"] != agent_run_id
                    or existing_link["unix_uid"] != os.getuid()):
                # Legacy orphan: only invalidate an unlinked queued row.
                # Never modify another WorkItem or an already running task.
                if existing_link is None:
                    self.store.mark_queued_unknown(task_id, "AgentRunLinkMissingOrConflict")
                self._mark_workitem_run_unknown(agent_run_id)
                raise FeishuCodexError(
                    "existing task has no matching AgentRun receipt; marked UNKNOWN, reconcile manually, never rebind"
                )
            detail = self.store.agent_task_detail(task_id, self.sender)
            if detail is None:
                raise FeishuCodexError("existing local Agent task is not owned by this Unix user")
            if detail["status"] == "queued":
                try:
                    self.spool.get(task_id)
                except (FileNotFoundError, OSError, SpoolError):
                    # The worker may have claimed or completed it after the
                    # snapshot. Only a still-queued row is invalidated.
                    if self.store.mark_queued_unknown(task_id, "AgentQueuedPayloadUnavailable"):
                        self._mark_workitem_run_unknown(agent_run_id)
                        raise FeishuCodexError("既有任务缺少可信输入，状态已置为 UNKNOWN，禁止重放") from None
        result = self.get_task(task_id)
        result["created"] = created
        return result

    def submit_task(self, repo: str, mode: str, task: str, idempotency_key: str) -> dict[str, Any]:
        self._enabled()
        self._require_billing_source()
        if isinstance(idempotency_key, str) and idempotency_key.startswith("workitem-"):
            raise FeishuCodexError("workitem- 幂等键仅供精确 WorkItem 入口使用")
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
        self._require_billing_source()
        if (not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id)
                or not isinstance(task, str) or not task.strip()
                or len(task) > self.config.max_prompt_chars or "\x00" in task):
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
            (run_id + "\0" + self.sender).encode("utf-8")
        ).hexdigest()[:32]
        event = InboundEvent(
            "feishu_message", record["tenant"], record["chat"],
            record["actor"], event_id, task,
        )
        policy_sha256 = local_agent_policy_digest(
            os.getuid(), record["repo"], run_mode, self.billing_source,
            repository.agent_allowed_modes, repository.edit_strategy,
            repository.commit_enabled,
            repo_path=str(repository.path),
            base_ref=repository.base_ref,
            worktree_root=str(repository.worktree_root or ""),
            branch_prefix=repository.branch_prefix,
            allowed_modes=repository.allowed_modes,
            verification_commands=repository.verification_commands,
            agent_codex_home=str(self.config.agent_codex_home or ""),
            openai_base_url=self.config.agent_openai_base_url,
            credential_fingerprint=hashlib.sha256(
                self.config.agent_openai_api_key.encode("utf-8")
            ).hexdigest(),
            codex_bin=self.config.codex_bin,
            isolation_bin=str(self.config.isolation_bin),
            deny_push_hooks_path=str(self.config.deny_push_hooks_path),
            deny_read_paths=(str(path) for path in self.config.deny_read_paths),
            isolation_write_paths=(str(path) for path in self.config.isolation_write_paths),
            codex_timeout_sec=self.config.codex_timeout_sec,
            max_prompt_chars=self.config.max_prompt_chars,
        )
        workflow = EngineeringWorkflow(store)
        # Repeated submissions of already-linked continuations are receipt
        # lookups, not new dispatches. New continuation tasks must resolve
        # the preceding successful local result before queue admission.
        if self.store.agent_run_link_for_run(run_id) is None:
            resolve_worker_resume(self.config, self.store, store, run_id, policy_sha256)
        workflow.authorize_local_agent_queue(
            run_id, event, os.getuid(), {record["repo"]}, repository.agent_allowed_modes,
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
        repository = self.config.repositories.get(record["repo"])
        if (repository is None or record["chat"] != self.config.target_chat_id
                or not self.config.sender_allowed(record["actor"], repository)):
            raise FeishuCodexError("WorkItem owner or repository access changed")
        link = self.store.agent_run_link_for_run(run_id)
        task = None
        if link is not None:
            if link["unix_uid"] != os.getuid():
                raise FeishuCodexError("WorkItem task link owner mismatch")
            task = self.store.agent_task_detail(link["task_id"], self.sender)
            if task is None:
                raise FeishuCodexError("linked Agent task is not owned by this local Unix user")
        from .feishu_engineering_agent.sessions import SessionRegistry
        sessions = SessionRegistry(store)
        session = sessions.receipt(run_id)
        from .feishu_engineering_agent.delivery import DeliveryCoordinator
        from .feishu_engineering_agent.models import InboundEvent
        event = InboundEvent("feishu_message", record["tenant"], record["chat"],
                             record["actor"], "local-delivery-status", "read delivery status")
        return {"agent_run_id": run_id, "run_status": record["status"],
                "task": task, "billing_source": approval["billing_source"],
                "session": session, "lineage": sessions.lineage(run_id),
                "delivery": DeliveryCoordinator(store).snapshot(run_id, event)}

    def _delivery_context(self, run_id: str):
        """Resolve the exact existing local result; callers cannot supply a SHA."""
        from .feishu_engineering_agent.delivery import DeliveryCoordinator
        from .feishu_engineering_agent.github_adapter import GitHubForge, GitHubTransport
        from .feishu_engineering_agent.models import InboundEvent
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise FeishuCodexError("invalid exact WorkItem Run ID")
        detail = self.get_workitem_task(run_id)
        store = self._manual_store()
        run = store.get_run(run_id)
        repository = self.config.repository(run["repo"])
        task = detail["task"]
        if (run["mode"] != "edit" or run["status"] not in ("waiting_ci", "waiting_qa", "completed")
                or task is None or task["status"] != "completed" or task["mode"] != "edit"
                or task["repository"] != run["repo"] or detail["session"] is None
                or not re.fullmatch(r"[a-f0-9]{40}", task["commit_hash"])
                or not task["branch_name"]):
            raise FeishuCodexError("delivery requires an exact completed local edit receipt")
        if not repository.github_repository or not repository.github_required_workflows:
            raise FeishuCodexError("该仓库未配置 GitHub 交付核验")
        event = InboundEvent("feishu_message", run["tenant"], run["chat"], run["actor"],
                             "local-delivery", "verify exact local delivery")
        forge = GitHubForge(
            run["repo"], repository.github_repository,
            GitHubTransport(repository.github_repository, self.github_read_token),
            base_branch=repository.github_base_branch,
        )
        return DeliveryCoordinator(store), event, repository, task, forge

    def verify_workitem_delivery(self, run_id: str, pr_number: int,
                                 ci_run_ids: list[int]) -> dict[str, Any]:
        """Observe an existing PR and every configured required workflow; GET only."""
        delivery, event, repository, task, forge = self._delivery_context(run_id)
        return delivery.verify_github_delivery(
            run_id, event, task["commit_hash"], task["branch_name"], forge,
            pr_number, ci_run_ids, repository.github_required_workflows,
        )

    def accept_workitem_qa(self, run_id: str, reviewer: str, evidence_ref: str,
                           attested_at: int, signature: str) -> dict[str, Any]:
        """Verify an out-of-band QA signature; never mint it in the MCP server."""
        delivery, event, repository, task, forge = self._delivery_context(run_id)
        if not self.qa_reviewer or reviewer != self.qa_reviewer or reviewer == event.actor:
            raise FeishuCodexError("需要配置的独立 QA 审核人")
        try:
            key = bytes.fromhex(self.qa_key_hex)
        except (ValueError, TypeError):
            raise FeishuCodexError("私有 QA 验证凭据未配置") from None
        if len(key) < 32 or type(attested_at) is not int:
            raise FeishuCodexError("私有 QA 验证凭据或时间无效")
        proof = delivery.snapshot(run_id, event)
        if proof["run_status"] != "waiting_qa" or proof["head_sha"] != task["commit_hash"]:
            raise FeishuCodexError("需要已核验的本地提交、PR 和 CI；QA 完成后请查询状态")
        # Re-observe the same immutable proof references, not a replacement set
        # supplied by the caller. Reject a PR whose head changed since CI.
        root = "https://github.com/" + repository.github_repository
        pr_refs = [row["reference"] for row in proof["evidence"] if row["evidence_type"] == "pr"]
        ci_refs = [row["reference"] for row in proof["evidence"] if row["evidence_type"] == "ci"]
        pr_match = re.fullmatch(re.escape(root) + r"/pull/([1-9][0-9]{0,12})", pr_refs[0]) if len(pr_refs) == 1 else None
        ci_matches = [re.fullmatch(re.escape(root) + r"/actions/runs/([1-9][0-9]{0,12})", ref)
                      for ref in ci_refs]
        if pr_match is None or any(match is None for match in ci_matches):
            raise FeishuCodexError("已记录的 GitHub 证据不符合当前仓库配置")
        delivery.verify_github_delivery(
            run_id, event, task["commit_hash"], task["branch_name"], forge,
            int(pr_match.group(1)), [int(match.group(1)) for match in ci_matches],
            repository.github_required_workflows,
        )
        delivery.accept_manual_qa(
            run_id, event, task["commit_hash"], reviewer, evidence_ref,
            attested_at, signature, key,
        )
        delivery.complete_engineering_only(run_id, event)
        from .feishu_engineering_agent.feedback import SourceFeedback
        result = delivery.snapshot(run_id, event)
        result["feedback"] = SourceFeedback(delivery.store).draft(run_id, event)
        return result

    def cancel_queued_task(self, task_id: int) -> dict[str, Any]:
        self.get_task(task_id)
        canceled = self.store.cancel_agent_queued(task_id, self.sender)
        if canceled:
            spool_error = None
            try:
                self.spool.discard(task_id)
            except OSError as exc:
                spool_error = exc
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
            if spool_error is not None:
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
        "name": "verify_workitem_delivery",
        "description": "Read-only verification of an existing GitHub PR and every configured required workflow against the exact local edit commit; advances to waiting_qa, not product closure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
                "pr_number": {"type": "integer", "minimum": 1},
                "ci_run_ids": {"type": "array", "minItems": 1, "maxItems": 8,
                               "uniqueItems": True, "items": {"type": "integer", "minimum": 1}},
            },
            "required": ["run_id", "pr_number", "ci_run_ids"],
            "additionalProperties": False,
        },
    },
    {
        "name": "accept_workitem_qa",
        "description": "Verify configured independent reviewer HMAC for the exact verified delivery head, recheck GitHub proof, and complete only the engineering Run. No signer or external workitem write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"},
                "reviewer": {"type": "string"},
                "evidence_ref": {"type": "string"},
                "attested_at": {"type": "integer", "minimum": 1},
                "signature": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
            "required": ["run_id", "reviewer", "evidence_ref", "attested_at", "signature"],
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
                "verify_workitem_delivery": {"run_id", "pr_number", "ci_run_ids"},
                "accept_workitem_qa": {"run_id", "reviewer", "evidence_ref", "attested_at", "signature"},
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
            elif name == "verify_workitem_delivery":
                value = intake.verify_workitem_delivery(**args)
            elif name == "accept_workitem_qa":
                value = intake.accept_workitem_qa(**args)
            elif name == "get_task":
                value = intake.get_task(**args)
            else:
                value = intake.cancel_queued_task(**args)
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
        except (FeishuCodexError, OSError, ValueError, sqlite3.DatabaseError) as exc:
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
        qa_reviewer=values.get("FEISHU_AGENT_QA_REVIEWER", ""),
        qa_key_hex=values.get("FEISHU_AGENT_QA_KEY_HEX", ""),
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
