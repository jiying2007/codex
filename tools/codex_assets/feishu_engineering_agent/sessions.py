"""Exact Codex App Server thread bindings and side-effect-free request planner.

No Codex invocation is performed here. The target host must qualify the
installed app-server protocol and a separate privileged runner must own I/O.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import pathlib
import subprocess
import time
import uuid
from typing import Optional, Tuple

from .models import InboundEvent, IntakeRejected, _check_id
from .state import RunStore

_TERMINAL_OR_UNCERTAIN = frozenset(
    ("unknown", "blocked", "failed", "completed", "canceled")
)


def _absolute_path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        raise IntakeRejected(name + " must be an explicit absolute POSIX path")
    parts = pathlib.PurePosixPath(value).parts
    if ".." in value.split("/") or not parts or len(value) > 1024:
        raise IntakeRejected(name + " may not traverse directories")
    normalized = str(pathlib.PurePosixPath(value))
    if normalized != value or normalized == "/":
        raise IntakeRejected(name + " must be canonical and non-root")
    return value


@dataclasses.dataclass(frozen=True)
class RuntimeGrant:
    """In-memory authorization from a trusted, separate policy/billing gate."""

    run_id: str
    actor: str
    repo: str
    mode: str
    billing_source: str
    expires_at: int
    authorization_ref: str

    def __post_init__(self):
        for field in ("run_id", "actor", "repo", "billing_source", "authorization_ref"):
            _check_id(getattr(self, field), field)
        if self.mode not in ("read", "review", "edit"):
            raise IntakeRejected("invalid runtime grant mode")
        if self.billing_source in ("codex_shared", "work_shared", "unapproved"):
            raise IntakeRejected("shared or unapproved model quota is denied")


def parse_exec_turn(stdout: str) -> Tuple[str, str]:
    """Read native codex exec --json receipts without exposing tool logs.

    A canonical persistent thread ID and one successful terminal turn are
    required; an incomplete or failed receipt must never trigger a retry.
    """
    if not isinstance(stdout, str) or not stdout or len(stdout) > 16 * 1024 * 1024:
        raise IntakeRejected("Codex JSONL receipt is missing or exceeds the limit")
    thread_id = ""
    started = completed = False
    final_text = ""
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError) as exc:
            raise IntakeRejected("invalid Codex JSONL receipt") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise IntakeRejected("invalid Codex JSONL event")
        kind = event["type"]
        if completed or kind in ("error", "turn.failed"):
            raise IntakeRejected("Codex JSONL turn is failed or ambiguous")
        if not thread_id and kind != "thread.started":
            raise IntakeRejected("Codex thread identity must precede turn events")
        if kind == "thread.started":
            value = event.get("thread_id")
            if thread_id or not isinstance(value, str):
                raise IntakeRejected("ambiguous Codex thread identity")
            try:
                if str(uuid.UUID(value)) != value:
                    raise ValueError("non-canonical UUID")
            except (ValueError, AttributeError) as exc:
                raise IntakeRejected("invalid native Codex thread ID") from exc
            thread_id = value
        elif kind == "turn.started":
            if started:
                raise IntakeRejected("multiple Codex turns in one receipt")
            started = True
        elif kind == "turn.completed":
            if not started:
                raise IntakeRejected("Codex turn completed without start")
            completed = True
        elif kind == "item.completed":
            item = event.get("item")
            if (started and isinstance(item, dict)
                    and item.get("type") == "agent_message"
                    and isinstance(item.get("text"), str)):
                final_text = item["text"]
    if not (thread_id and started and completed):
        raise IntakeRejected("Codex JSONL terminal receipt is incomplete")
    return thread_id, final_text


class SessionRegistry:
    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_sessions (
                    run_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL, chat TEXT NOT NULL, actor TEXT NOT NULL,
                    repo TEXT NOT NULL, host TEXT NOT NULL,
                    repo_path TEXT NOT NULL, codex_home TEXT NOT NULL,
                    thread_id TEXT NOT NULL, mode TEXT NOT NULL,
                    bound_at INTEGER NOT NULL,
                    UNIQUE(host,codex_home,thread_id)
                );
                CREATE TABLE IF NOT EXISTS fea_session_followups (
                    run_id TEXT PRIMARY KEY REFERENCES fea_runs(run_id),
                    previous_run_id TEXT NOT NULL UNIQUE REFERENCES fea_runs(run_id),
                    root_run_id TEXT NOT NULL REFERENCES fea_sessions(run_id),
                    completed_at INTEGER
                );
            """)

    @staticmethod
    def _binding_row(db, run_id: str):
        row = db.execute(
            "SELECT * FROM fea_sessions WHERE run_id=?", (run_id,),
        ).fetchone()
        if row is None:
            row = db.execute(
                "SELECT s.* FROM fea_session_followups f "
                "JOIN fea_sessions s ON s.run_id=f.root_run_id "
                "WHERE f.run_id=? AND f.completed_at IS NOT NULL", (run_id,),
            ).fetchone()
        return row

    @staticmethod
    def _check_scope(run, binding) -> None:
        keys = ("tenant", "chat", "actor", "repo", "mode")
        if tuple(run[k] for k in keys) != tuple(binding[k] for k in keys):
            raise IntakeRejected("session receipt scope mismatch")

    @staticmethod
    def require_no_successor(db, run_id: str) -> None:
        if db.execute(
                "SELECT 1 FROM fea_session_followups WHERE previous_run_id=?",
                (run_id,),
        ).fetchone() is not None:
            raise IntakeRejected("this Run has a reserved continuation; use the successor Run")

    @staticmethod
    def require_successful_predecessor(db, run_id: str):
        """Local completed read/review or unpublished local edit only."""
        previous = db.execute("SELECT * FROM fea_runs WHERE run_id=?", (run_id,)).fetchone()
        if previous is None or previous["status"] != (
                "waiting_ci" if previous["mode"] == "edit" else "completed"):
            raise IntakeRejected("continuation requires a successful previous local turn")
        binding = SessionRegistry._binding_row(db, run_id)
        if binding is None:
            raise IntakeRejected("previous Run lacks a completed native session receipt")
        SessionRegistry._check_scope(previous, binding)
        try:
            if str(uuid.UUID(binding["thread_id"])) != binding["thread_id"]:
                raise ValueError("non-canonical UUID")
        except (ValueError, AttributeError) as exc:
            raise IntakeRejected("continuation requires a canonical native thread ID") from exc
        if db.execute(
                "SELECT 1 FROM fea_local_agent_approvals WHERE run_id=?", (run_id,),
        ).fetchone() is None:
            raise IntakeRejected("continuation requires a previous local worker approval")
        if previous["mode"] == "edit":
            if db.execute(
                    "SELECT 1 FROM fea_evidence WHERE run_id=? "
                    "AND evidence_type='commit' AND verified=0", (run_id,),
            ).fetchone() is None:
                raise IntakeRejected("previous edit lacks a local commit receipt")
            # Tables are initialized on demand by the delivery coordinator.
            for table in ("fea_publications", "fea_delivery_heads"):
                if (db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                               (table,)).fetchone() is not None
                        and db.execute("SELECT 1 FROM " + table + " WHERE run_id=?",
                                       (run_id,)).fetchone() is not None):
                    raise IntakeRejected("previous edit has entered Git delivery; do not reuse its branch")
            if db.execute(
                    "SELECT 1 FROM fea_evidence WHERE run_id=? AND evidence_type IN ('pr','ci','qa')",
                    (run_id,),
            ).fetchone() is not None:
                raise IntakeRejected("previous edit has delivery evidence; do not reuse its branch")
        return previous, binding

    def reserve_followup(self, db, run_id: str, previous_run_id: str) -> None:
        """Part of the same transaction that creates a new proposed attempt."""
        previous, binding = self.require_successful_predecessor(db, previous_run_id)
        child = db.execute("SELECT * FROM fea_runs WHERE run_id=?", (run_id,)).fetchone()
        self._check_scope(child, binding)
        if child["workitem_fp"] != previous["workitem_fp"]:
            raise IntakeRejected("continuation WorkItem identity mismatch")
        self.require_no_successor(db, previous_run_id)
        db.execute(
            "INSERT INTO fea_session_followups (run_id,previous_run_id,root_run_id) "
            "VALUES (?,?,?)", (run_id, previous_run_id, binding["run_id"]),
        )

    def followup(self, run_id: str) -> Optional[dict]:
        """Return reserved lineage and exact root identity, not execution permission."""
        run = self.store.get_run(run_id)
        with contextlib.closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT * FROM fea_session_followups WHERE run_id=?", (run_id,),
            ).fetchone()
            if row is None:
                return None
            binding = db.execute(
                "SELECT * FROM fea_sessions WHERE run_id=?", (row["root_run_id"],),
            ).fetchone()
            if binding is None:
                raise IntakeRejected("continuation root receipt missing")
            self._check_scope(run, binding)
            if row["completed_at"] is None:
                previous, prior_binding = self.require_successful_predecessor(
                    db, row["previous_run_id"],
                )
                if (prior_binding["run_id"] != row["root_run_id"]
                        or previous["workitem_fp"] != run["workitem_fp"]):
                    raise IntakeRejected("continuation predecessor identity mismatch")
            result = dict(row)
            result.update({key: binding[key] for key in (
                "thread_id", "host", "repo_path", "codex_home", "mode",
            )})
            return result

    def bind(
        self, run_id: str, event: InboundEvent, host: str,
        repo_path: str, codex_home: str, thread_id: str,
    ) -> None:
        """Called ONLY after trusted runtime returns exact, persistent thread ID."""
        run = self.store.get_run(run_id, event)
        if self.followup(run_id) is not None:
            raise IntakeRejected("local continuation cannot use the App Server binding path")
        self._bind_record(run, host, repo_path, codex_home, thread_id)

    def bind_worker_result(
        self, run_id: str, host: str, repo_path: str,
        codex_home: str, thread_id: str,
    ) -> None:
        """Trusted local worker only: bind its already-linked running AgentRun."""
        run = self.store.get_run(run_id)
        if run["status"] != "running":
            raise IntakeRejected("worker receipt requires a running AgentRun")
        followup = self.followup(run_id)
        if followup is None:
            self._bind_record(run, host, repo_path, codex_home, thread_id)
            return
        if (host, repo_path, codex_home, thread_id) != tuple(
                followup[key] for key in ("host", "repo_path", "codex_home", "thread_id")):
            raise IntakeRejected("continuation returned a different native session identity")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM fea_runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "running":
                raise IntakeRejected("continuation is no longer running")
            db.execute(
                "UPDATE fea_session_followups SET completed_at=? "
                "WHERE run_id=? AND completed_at IS NULL", (int(time.time()), run_id),
            )
            db.commit()

    def _bind_record(
        self, run: dict, host: str, repo_path: str,
        codex_home: str, thread_id: str,
    ) -> None:
        run_id = run["run_id"]
        if run["status"] in _TERMINAL_OR_UNCERTAIN:
            raise IntakeRejected("cannot bind terminal/unknown run")
        _check_id(host, "host")
        _check_id(thread_id, "thread_id")
        _absolute_path(repo_path, "repo_path")
        _absolute_path(codex_home, "codex_home")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT * FROM fea_sessions WHERE run_id=?", (run_id,),
                ).fetchone()
                if existing is not None:
                    expected = (run["tenant"], run["chat"], run["actor"],
                                run["repo"], host, repo_path, codex_home, thread_id, run["mode"])
                    actual = tuple(existing[k] for k in (
                        "tenant", "chat", "actor", "repo", "host", "repo_path",
                        "codex_home", "thread_id", "mode"
                    ))
                    if actual != expected:
                        raise IntakeRejected("exact session binding cannot be replaced")
                else:
                    db.execute(
                        "INSERT INTO fea_sessions "
                        "(run_id,tenant,chat,actor,repo,host,repo_path,codex_home,"
                        "thread_id,mode,bound_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (run_id, run["tenant"], run["chat"], run["actor"], run["repo"],
                         host, repo_path, codex_home, thread_id, run["mode"],
                         int(time.time())),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise

    def receipt(
        self, run_id: str, event: Optional[InboundEvent] = None,
    ) -> Optional[dict]:
        """Read binding metadata, not permission to resume a terminal run."""
        run = self.store.get_run(run_id, event)
        with contextlib.closing(self.store._connect()) as db:
            row = self._binding_row(db, run_id)
        if row is None:
            return None
        self._check_scope(run, row)
        return {key: row[key] for key in (
            "thread_id", "host", "repo_path", "codex_home", "mode", "bound_at",
        )}

    def exact(
        self, run_id: str, event: InboundEvent, host: str,
        repo_path: str, codex_home: str,
    ) -> dict:
        """All scope dimensions must match; never use implicit --last session."""
        run = self.store.get_run(run_id, event)
        if run["status"] in _TERMINAL_OR_UNCERTAIN:
            raise IntakeRejected("cannot resume terminal or unknown run")
        _check_id(host, "host")
        _absolute_path(repo_path, "repo_path")
        _absolute_path(codex_home, "codex_home")
        with contextlib.closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT * FROM fea_sessions WHERE run_id=?", (run_id,),
            ).fetchone()
        if row is None:
            raise IntakeRejected("exact Codex thread missing")
        binding = dict(row)
        if (binding["tenant"], binding["chat"], binding["actor"], binding["repo"],
                binding["host"], binding["repo_path"], binding["codex_home"]) != (
                    event.tenant, event.chat, event.actor, run["repo"],
                    host, repo_path, codex_home):
            raise IntakeRejected("session scope mismatch")
        return binding

    @staticmethod
    def resume_request(binding: dict, rpc_id: int = 1) -> dict:
        if not isinstance(rpc_id, int) or rpc_id < 1:
            raise IntakeRejected("RPC id must be positive")
        return {
            "method": "thread/resume", "id": rpc_id,
            "params": {"threadId": _check_id(binding["thread_id"], "thread_id"),
                       "excludeTurns": True},
        }

    @staticmethod
    def interrupt_request(binding: dict, turn_id: str, rpc_id: int = 1) -> dict:
        return {
            "method": "turn/interrupt", "id": rpc_id,
            "params": {"threadId": _check_id(binding["thread_id"], "thread_id"),
                       "turnId": _check_id(turn_id, "turn_id")},
        }

    @staticmethod
    def turn_request(
        binding: dict, grant: Optional[RuntimeGrant], prompt: str,
        model_calls_enabled: bool = False, rpc_id: int = 1,
        now: Optional[int] = None,
    ) -> dict:
        """Construct request only with a fresh scoped grant AND deployment flag.

        Still does not send it. A trusted runtime must enforce approvalPolicy,
        sandbox and secrets exclusion independently at the effect boundary.
        """
        if not model_calls_enabled or grant is None:
            raise IntakeRejected("paid Codex model turns disabled")
        when = int(time.time()) if now is None else int(now)
        if grant.expires_at <= when:
            raise IntakeRejected("runtime grant expired")
        if (grant.run_id, grant.actor, grant.repo, grant.mode) != (
                binding["run_id"], binding["actor"], binding["repo"], binding["mode"]):
            raise IntakeRejected("runtime grant scope mismatch")
        if (not isinstance(prompt, str) or not prompt.strip()
                or len(prompt) > 12000 or "\x00" in prompt):
            raise IntakeRejected("invalid bounded runtime prompt")
        if not isinstance(rpc_id, int) or rpc_id < 1:
            raise IntakeRejected("invalid RPC id")
        # Do not log, store or persist prompt or grant. Treat WorkItem data as untrusted.
        return {
            "method": "turn/start", "id": rpc_id,
            "params": {
                "threadId": _check_id(binding["thread_id"], "thread_id"),
                # Codex App Server v2 UserInput.Text serializes text_elements
                # (snake_case), and SandboxPolicy has required booleans.
                # The CI fixture should match the public protocol schema.
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
                "cwd": _absolute_path(binding["repo_path"], "repo_path"),
                "approvalPolicy": "on-request",
                "sandboxPolicy": (
                    {"type": "workspaceWrite",
                     "writableRoots": [binding["repo_path"]],
                     "networkAccess": False,
                     "excludeTmpdirEnvVar": True, "excludeSlashTmp": True}
                    if grant.mode == "edit"
                    else {"type": "readOnly", "networkAccess": False}
                ),
            },
        }


def probe_local_app_server(executable: str = "codex", timeout: int = 5) -> dict:
    """Host-local NON-MODEL capability probe; does not start a Codex turn.

    Run on vstrong100 from an approved operational shell, not in CI as proof
    of that host. No version pin or login/token inspection.
    """
    if not isinstance(executable, str) or not executable or "/" in executable:
        raise IntakeRejected("probe requires a PATH executable name")
    if not 1 <= timeout <= 10:
        raise IntakeRejected("probe timeout out of bounds")
    results = {}
    for key, argv in (
        ("version", [executable, "--version"]),
        ("app_server_help", [executable, "app-server", "--help"]),
    ):
        try:
            process = subprocess.run(
                argv, check=False, capture_output=True, text=True,
                timeout=timeout,
                env={k: v for k, v in os.environ.items()
                     if k in ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE",
                              "TERM", "CODEX_HOME")},
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            return {"available": False, "failed_step": key,
                    "reason": type(exc).__name__}
        if process.returncode != 0:
            return {"available": False, "failed_step": key,
                    "reason": "nonzero_exit"}
        results[key] = process.stdout[:512] or process.stderr[:512]
    return {"available": True, "details": results,
            "qualified_for_model_calls": False}
