"""Exact Codex App Server thread bindings and side-effect-free request planner.

No Codex invocation is performed here. The target host must qualify the
installed app-server protocol and a separate privileged runner must own I/O.
"""
from __future__ import annotations

import contextlib
import dataclasses
import os
import pathlib
import subprocess
import time
from typing import Optional

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
            """)

    def bind(
        self, run_id: str, event: InboundEvent, host: str,
        repo_path: str, codex_home: str, thread_id: str,
    ) -> None:
        """Called ONLY after trusted runtime returns exact, persistent thread ID."""
        run = self.store.get_run(run_id, event)
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
                    expected = (event.tenant, event.chat, event.actor,
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
                        (run_id, event.tenant, event.chat, event.actor, run["repo"],
                         host, repo_path, codex_home, thread_id, run["mode"],
                         int(time.time())),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise

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
                "input": [{"type": "text", "text": prompt}],
                "cwd": _absolute_path(binding["repo_path"], "repo_path"),
                "approvalPolicy": "on-request",
                "sandboxPolicy": (
                    {"type": "workspaceWrite",
                     "writableRoots": [binding["repo_path"]], "networkAccess": False}
                    if grant.mode == "edit" else {"type": "readOnly"}
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
                timeout=timeout, env=os.environ.copy(),
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
