"""WorkItem -> independently approved AgentRun attempts; no Agent Runtime rebuild.

A human-provided WorkItem reference does not authorize a model turn. An
isolated execution attempt must be created first, and an external trusted
policy/billing owner signs the exact repository/mode scope before queueing.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from typing import Iterable

from .models import EventConflict, InboundEvent, IntakeRejected, WorkItemKey, _check_id, check_repo_alias
from .sessions import RuntimeGrant
from .state import RunStore


@dataclasses.dataclass(frozen=True)
class ExecutionApproval:
    run_id: str
    actor: str
    tenant: str
    chat: str
    repo: str
    mode: str
    approval_ref: str
    billing_source: str
    expires_at: int
    sdd_reviewed: bool = False

    def __post_init__(self):
        for field in ("run_id", "actor", "tenant", "chat", "repo",
                      "approval_ref", "billing_source"):
            _check_id(getattr(self, field), field)
        if self.mode not in ("read", "review", "edit"):
            raise IntakeRejected("invalid approved mode")
        if self.billing_source in ("codex_shared", "work_shared", "unapproved"):
            raise IntakeRejected("disallowed billing source")

    def canonical(self) -> bytes:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=True,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")


def local_agent_policy_digest(
    unix_uid: int, repo: str, mode: str, billing_source: str,
    agent_allowed_modes: Iterable[str], edit_strategy: str,
    commit_enabled: bool, *, repo_path: str = "", base_ref: str = "",
    worktree_root: str = "", branch_prefix: str = "",
    allowed_modes: Iterable[str] = (),
    verification_commands: Iterable[Iterable[str]] = (),
    agent_codex_home: str = "", openai_base_url: str = "",
) -> str:
    """Canonical digest of the operator-controlled local MCP execution policy."""
    payload = {
        "unix_uid": int(unix_uid),
        "repo": check_repo_alias(repo),
        "mode": mode,
        "billing_source": billing_source,
        "repo_path": repo_path,
        "base_ref": base_ref,
        "worktree_root": worktree_root,
        "branch_prefix": branch_prefix,
        "allowed_modes": sorted(set(allowed_modes)),
        "agent_allowed_modes": sorted(set(agent_allowed_modes)),
        "edit_strategy": edit_strategy,
        "commit_enabled": bool(commit_enabled),
        "verification_commands": [list(command) for command in verification_commands],
        "agent_codex_home": str(agent_codex_home),
        "openai_base_url": str(openai_base_url),
    }
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


class EngineeringWorkflow:
    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_attempt_links (
                    event_key TEXT PRIMARY KEY,
                    content_digest TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    attempt_run_id TEXT NOT NULL UNIQUE,
                    scope_sha256 TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fea_run_approvals (
                    run_id TEXT PRIMARY KEY,
                    approval_ref TEXT NOT NULL,
                    signed_digest TEXT NOT NULL,
                    billing_source TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    authorized_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fea_local_agent_approvals (
                    run_id TEXT PRIMARY KEY,
                    unix_uid INTEGER NOT NULL,
                    repository TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    scope_sha256 TEXT NOT NULL,
                    billing_source TEXT NOT NULL,
                    policy_sha256 TEXT NOT NULL,
                    approved_at INTEGER NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute(
                "PRAGMA table_info(fea_attempt_links)"
            ).fetchall()}
            if "scope_sha256" not in columns:
                db.execute(
                    "ALTER TABLE fea_attempt_links "
                    "ADD COLUMN scope_sha256 TEXT NOT NULL DEFAULT ''"
                )

    def create_attempt(
        self, source_run_id: str, event: InboundEvent, mode: str,
        allowed_repos: Iterable[str], scope_sha256: str = "",
    ) -> dict:
        """One registered WorkItem can have many independent run attempts.

        Exact message replay is idempotent; no prompt text is stored, no model
        is queued, no new permission is granted.
        """
        if mode not in ("read", "review", "edit"):
            raise IntakeRejected("unsupported execution attempt mode")
        if (scope_sha256 and (
                not isinstance(scope_sha256, str) or len(scope_sha256) != 64
                or any(char not in "0123456789abcdef" for char in scope_sha256))):
            raise IntakeRejected("execution attempt scope digest must be SHA-256")
        parent = self.store.get_run(source_run_id, event)
        if not parent["workitem_fp"] or not parent["provider"]:
            raise IntakeRejected("source run lacks verified WorkItem linkage metadata")
        if parent["repo"] not in {check_repo_alias(x) for x in allowed_repos}:
            raise IntakeRejected("repository access revoked")
        if parent["status"] in ("unknown", "blocked", "canceled"):
            raise IntakeRejected("cannot attempt unknown/blocked/canceled source")
        child_id = uuid.uuid4().hex
        when = int(time.time())
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                previous = db.execute(
                    "SELECT content_digest,source_run_id,attempt_run_id,scope_sha256 "
                    "FROM fea_attempt_links WHERE event_key=?",
                    (event.event_key,),
                ).fetchone()
                if previous is not None:
                    if previous["content_digest"] != event.content_digest:
                        raise EventConflict("same event identity with changed scope")
                    if previous["source_run_id"] != source_run_id:
                        raise IntakeRejected("replayed event cannot change WorkItem source")
                    if previous["scope_sha256"] != scope_sha256:
                        raise IntakeRejected("replayed attempt cannot change approved scope")
                    row = db.execute(
                        "SELECT repo,mode FROM fea_runs WHERE run_id=?",
                        (previous["attempt_run_id"],),
                    ).fetchone()
                    if (row is None or row["repo"] != parent["repo"]
                            or row["mode"] != mode):
                        raise IntakeRejected("replayed attempt no longer matches scope")
                    db.rollback()
                    return {"run_id": previous["attempt_run_id"],
                            "created": False, "model_invoked": False}
                db.execute(
                    "INSERT INTO fea_runs "
                    "(run_id,tenant,chat,actor,repo,mode,provider,workspace,kind,"
                    "item_id,workitem_fp,status,revision,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,'proposed',0,?,?)",
                    (child_id, event.tenant, event.chat, event.actor,
                     parent["repo"], mode, parent["provider"], parent["workspace"],
                     parent["kind"], parent["item_id"], parent["workitem_fp"],
                     when, when),
                )
                db.execute(
                    "INSERT INTO fea_attempt_links "
                    "(event_key,content_digest,source_run_id,attempt_run_id,scope_sha256,created_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (event.event_key, event.content_digest, source_run_id, child_id,
                     scope_sha256, when),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"run_id": child_id, "created": True,
                "status": "proposed", "mode": mode, "model_invoked": False}

    def authorize_local_agent_queue(
        self, run_id: str, event: InboundEvent, unix_uid: int,
        allowed_repos: Iterable[str], allowed_modes: Iterable[str],
        scope_sha256: str, billing_source: str, policy_sha256: str,
        now: int = None,
    ) -> dict:
        """Authorize a same-UID local MCP handoff under the existing Bot policy.

        This is deliberately separate from the signed App Server grant path.
        It is available only when the operator has enabled the local Agent MCP,
        the repository's agent mode allowlist, and a non-shared billing source.
        The exact WorkItem attempt scope and policy snapshot are persisted.
        """
        when = int(time.time()) if now is None else int(now)
        if not isinstance(unix_uid, int) or isinstance(unix_uid, bool) or unix_uid < 0:
            raise IntakeRejected("invalid local Agent Unix identity")
        for name, value in (("scope_sha256", scope_sha256),
                            ("policy_sha256", policy_sha256)):
            if (not isinstance(value, str) or len(value) != 64
                    or any(char not in "0123456789abcdef" for char in value)):
                raise IntakeRejected("invalid " + name)
        if billing_source not in ("external_api_key", "external_gateway", "self_hosted"):
            raise IntakeRejected("WorkItem execution requires a non-shared approved billing source")
        record = self.store.get_run(run_id, event)
        allowed = {check_repo_alias(value) for value in allowed_repos}
        if record["repo"] not in allowed or record["mode"] not in set(allowed_modes):
            raise IntakeRejected("local Agent repository or mode is not authorized")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                link = db.execute(
                    "SELECT source_run_id,scope_sha256 FROM fea_attempt_links "
                    "WHERE attempt_run_id=?", (run_id,),
                ).fetchone()
                if link is None or link["scope_sha256"] != scope_sha256:
                    raise IntakeRejected("task text does not match the registered WorkItem attempt scope")
                source = db.execute(
                    "SELECT 1 FROM fea_manual_claims WHERE run_id=?",
                    (link["source_run_id"],),
                ).fetchone()
                if source is None:
                    raise IntakeRejected("local MCP bridge requires a manually registered WorkItem source")
                previous = db.execute(
                    "SELECT * FROM fea_local_agent_approvals WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if previous is not None:
                    expected = (unix_uid, record["repo"], record["mode"],
                                scope_sha256, billing_source, policy_sha256)
                    actual = tuple(previous[key] for key in (
                        "unix_uid", "repository", "mode", "scope_sha256",
                        "billing_source", "policy_sha256",
                    ))
                    if actual != expected:
                        raise IntakeRejected("local Agent approval conflicts with the existing Run")
                    current = db.execute(
                        "SELECT status FROM fea_runs WHERE run_id=?", (run_id,),
                    ).fetchone()
                    if current is None or current["status"] not in (
                            "queued", "running", "waiting_ci", "waiting_qa", "completed"):
                        raise IntakeRejected("previously authorized Run is no longer executable")
                    db.rollback()
                    return {"run_id": run_id, "authorized": False,
                            "status": current["status"], "unix_uid": unix_uid}
                current = db.execute(
                    "SELECT status FROM fea_runs WHERE run_id=?", (run_id,),
                ).fetchone()
                if current is None or current["status"] not in ("proposed", "ready"):
                    raise IntakeRejected("WorkItem attempt is not awaiting local execution")
                db.execute(
                    "INSERT INTO fea_local_agent_approvals "
                    "(run_id,unix_uid,repository,mode,scope_sha256,billing_source,"
                    "policy_sha256,approved_at) VALUES (?,?,?,?,?,?,?,?)",
                    (run_id, unix_uid, record["repo"], record["mode"],
                     scope_sha256, billing_source, policy_sha256, when),
                )
                revision_increment = 2 if current["status"] == "proposed" else 1
                db.execute(
                    "UPDATE fea_runs SET status='queued',revision=revision+?,updated_at=? "
                    "WHERE run_id=?",
                    (revision_increment, when, run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"run_id": run_id, "authorized": True,
                "status": "queued", "unix_uid": unix_uid}

    def local_agent_approval(self, run_id: str) -> dict:
        with contextlib.closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT * FROM fea_local_agent_approvals WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise IntakeRejected("local Agent execution approval not found")
        return dict(row)

    @staticmethod
    def sign_approval(approval: ExecutionApproval, secret: bytes) -> str:
        """Used only by the trusted external policy/billing issuer, not chat."""
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise IntakeRejected("private approval secret must be at least 32 bytes")
        return hmac.new(secret, approval.canonical(), hashlib.sha256).hexdigest()

    def authorize_queue(
        self, approval: ExecutionApproval, signature: str,
        secret: bytes, event: InboundEvent, allowed_repos: Iterable[str],
        now: int = None,
    ) -> RuntimeGrant:
        """Validate external approval, atomically queue only the exact attempt.

        Does not launch any Codex subprocess or model call. Queueing means
        prepared for the separately authorized effect boundary.
        """
        when = int(time.time()) if now is None else int(now)
        if (approval.expires_at <= when or approval.expires_at > when + 3600
                or not isinstance(signature, str)
                or not hmac.compare_digest(signature, self.sign_approval(approval, secret))):
            raise IntakeRejected("invalid/expired independently signed execution approval")
        record = self.store.get_run(approval.run_id, event)
        if (approval.tenant, approval.chat, approval.actor, approval.repo, approval.mode) != (
                event.tenant, event.chat, event.actor, record["repo"], record["mode"]):
            raise IntakeRejected("execution grant scope mismatch")
        if record["repo"] not in {check_repo_alias(x) for x in allowed_repos}:
            raise IntakeRejected("repository access changed")
        if approval.mode == "edit" and not approval.sdd_reviewed:
            raise IntakeRejected("edit requires independently reviewed SDD/scope")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                linked = db.execute(
                    "SELECT 1 FROM fea_attempt_links WHERE attempt_run_id=?",
                    (approval.run_id,),
                ).fetchone()
                if not linked:
                    raise IntakeRejected("only explicit WorkItem development attempts may queue")
                prior = db.execute(
                    "SELECT signed_digest FROM fea_run_approvals WHERE run_id=?",
                    (approval.run_id,),
                ).fetchone()
                digest = hashlib.sha256(approval.canonical()).hexdigest()
                if prior is not None:
                    if prior["signed_digest"] != digest:
                        raise IntakeRejected("conflicting execution approval")
                    active = db.execute(
                        "SELECT status FROM fea_runs WHERE run_id=?",
                        (approval.run_id,),
                    ).fetchone()
                    if active is None or active["status"] != "queued":
                        raise IntakeRejected("approved Run already started or ended")
                    db.rollback()
                    return RuntimeGrant(
                        approval.run_id, approval.actor, approval.repo, approval.mode,
                        approval.billing_source, approval.expires_at, approval.approval_ref,
                    )
                status = db.execute(
                    "SELECT status FROM fea_runs WHERE run_id=?",
                    (approval.run_id,),
                ).fetchone()
                if status is None or status["status"] != "proposed":
                    raise IntakeRejected("attempt not in proposed state")
                db.execute(
                    "INSERT INTO fea_run_approvals "
                    "(run_id,approval_ref,signed_digest,billing_source,"
                    "expires_at,authorized_at) VALUES (?,?,?,?,?,?)",
                    (approval.run_id, approval.approval_ref, digest,
                     approval.billing_source, approval.expires_at, when),
                )
                db.execute(
                    "UPDATE fea_runs SET status='queued',revision=revision+2,"
                    "updated_at=? WHERE run_id=?",
                    (when, approval.run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return RuntimeGrant(
            approval.run_id, approval.actor, approval.repo, approval.mode,
            approval.billing_source, approval.expires_at, approval.approval_ref,
        )

    def status_for_source(self, source_run_id: str, event: InboundEvent) -> dict:
        """Return source + all same-owner attempts, no raw user description."""
        source = self.store.get_run(source_run_id, event)
        with contextlib.closing(self.store._connect()) as db:
            links = db.execute(
                "SELECT a.attempt_run_id,r.mode,r.status,r.repo "
                "FROM fea_attempt_links a JOIN fea_runs r "
                "ON r.run_id=a.attempt_run_id "
                "WHERE a.source_run_id=? AND r.tenant=? AND r.chat=? AND r.actor=? "
                "ORDER BY a.created_at,a.attempt_run_id",
                (source_run_id, event.tenant, event.chat, event.actor),
            ).fetchall()
        return {"source_run_id": source_run_id,
                "workitem_fp": source["workitem_fp"],
                "attempts": [dict(r) for r in links],
                "workitem_closed": False}
