"""Private *preview-only* SQLite event receipts and project preferences.

This database is intentionally NOT the production Feishu Bot DB. A future
migration must qualify schema, backup, service ownership and one active writer.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import sqlite3
import stat
import time
from typing import FrozenSet, Iterable, Optional

from .models import Decision, EventConflict, InboundEvent, IntakeRejected, check_repo_alias
from .routing import route_message


class OfflineIntakeStore:
    """One event + preference transaction; never records prompt text."""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = pathlib.Path(path)
        if (not self.path.is_absolute() or not self.path.parent.is_dir()
                or self.path.is_symlink()
                or self.path.name == "feishu-codex-state.sqlite3"):
            raise IntakeRejected("offline preview DB needs a separate absolute safe path")
        if not self.path.exists():
            descriptor = os.open(
                str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
            )
            os.close(descriptor)
        info = self.path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise IntakeRejected("offline preview DB must be owned and private (0600)")
        with contextlib.closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS fea_preview_events (
                    event_key TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    task_id INTEGER,
                    requires_approval INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fea_preview_projects (
                    source TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    chat TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY(source, tenant, chat, actor)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def selected_project(self, event: InboundEvent) -> str:
        with contextlib.closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT repo FROM fea_preview_projects "
                "WHERE source=? AND tenant=? AND chat=? AND actor=?",
                event.scope,
            ).fetchone()
        return str(row["repo"]) if row else ""

    def ingest(
        self,
        event: InboundEvent,
        allowed_repos: Iterable[str],
        default_repo: str = "",
    ) -> Decision:
        aliases: FrozenSet[str] = frozenset(check_repo_alias(r) for r in allowed_repos)
        if default_repo and default_repo not in aliases:
            raise IntakeRejected("default repo is not in the authorized allowlist")
        with contextlib.closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                previous = connection.execute(
                    "SELECT content_sha256,kind,repository,task_id,"
                    "requires_approval,reason FROM fea_preview_events WHERE event_key=?",
                    (event.event_key,),
                ).fetchone()
                if previous is not None:
                    if previous["content_sha256"] != event.content_digest:
                        raise EventConflict("same event identity with different message content")
                    repo = str(previous["repository"])
                    if repo and repo not in aliases:
                        connection.rollback()
                        return Decision("blocked", reason="repository_policy_changed",
                                        replayed=True)
                    return Decision(
                        str(previous["kind"]), repo,
                        int(previous["task_id"]) if previous["task_id"] is not None else None,
                        bool(previous["requires_approval"]), str(previous["reason"]),
                        replayed=True,
                    )
                row = connection.execute(
                    "SELECT repo FROM fea_preview_projects WHERE "
                    "source=? AND tenant=? AND chat=? AND actor=?",
                    event.scope,
                ).fetchone()
                selected = str(row["repo"]) if row else default_repo
                decision = route_message(event.text, selected, aliases)
                if decision.kind == "switch_project":
                    connection.execute(
                        "INSERT INTO fea_preview_projects "
                        "(source,tenant,chat,actor,repo,updated_at) VALUES (?,?,?,?,?,?) "
                        "ON CONFLICT(source,tenant,chat,actor) DO UPDATE SET "
                        "repo=excluded.repo, updated_at=excluded.updated_at",
                        event.scope + (decision.repo, int(time.time())),
                    )
                if decision.kind == "reset_project":
                    connection.execute(
                        "DELETE FROM fea_preview_projects WHERE "
                        "source=? AND tenant=? AND chat=? AND actor=?",
                        event.scope,
                    )
                connection.execute(
                    "INSERT INTO fea_preview_events "
                    "(event_key,content_sha256,kind,repository,task_id,"
                    "requires_approval,reason,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        event.event_key, event.content_digest, decision.kind, decision.repo,
                        decision.task_id, int(decision.requires_approval),
                        decision.reason, int(time.time()),
                    ),
                )
                connection.commit()
                return decision
            except Exception:
                connection.rollback()
                raise
