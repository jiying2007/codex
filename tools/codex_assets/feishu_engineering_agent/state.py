"""Private offline AgentRun ledger; not wired to the production Feishu consumer.

WorkItem remains owned by Feishu Project/TAPD. The ledger only records
bounded execution attempts and evidence references, never message bodies.
"""
from __future__ import annotations

import contextlib
import re
import sqlite3
import time
import uuid
from typing import Iterable, Optional

from .models import InboundEvent, IntakeRejected, WorkItemKey, _check_id, check_repo_alias
from .store import OfflineIntakeStore

_TRANSITIONS = {
    "proposed": frozenset(("ready", "blocked", "canceled")),
    "ready": frozenset(("queued", "blocked", "canceled")),
    "queued": frozenset(("running", "unknown", "canceled", "blocked")),
    "running": frozenset(("waiting_ci", "waiting_qa", "failed", "unknown", "canceled")),
    "waiting_ci": frozenset(("waiting_qa", "failed", "unknown")),
    "waiting_qa": frozenset(("completed", "blocked", "failed", "unknown")),
    "unknown": frozenset(("blocked",)),  # no replay of uncertain model/remote effects
    "blocked": frozenset(),
    "canceled": frozenset(),
    "completed": frozenset(),
    "failed": frozenset(),
}
_EVIDENCE_TYPES = frozenset(("sdd", "commit", "pr", "ci", "qa", "device", "contract"))
_REF = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9:/?&=._#%-]{0,511}\Z")


class RunStore(OfflineIntakeStore):
    """Same private preview DB, SQLite transactions and 0600 file rules as intake."""

    def __init__(self, path):
        super().__init__(path)
        with contextlib.closing(self._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_runs (
                    run_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL, chat TEXT NOT NULL, actor TEXT NOT NULL,
                    repo TEXT NOT NULL, mode TEXT NOT NULL,
                    provider TEXT, workspace TEXT, kind TEXT, item_id TEXT,
                    workitem_fp TEXT, status TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS fea_runs_workitem
                  ON fea_runs(workitem_fp, created_at);
                CREATE TABLE IF NOT EXISTS fea_evidence (
                    run_id TEXT NOT NULL REFERENCES fea_runs(run_id),
                    evidence_type TEXT NOT NULL, reference TEXT NOT NULL,
                    verifier TEXT NOT NULL, verified INTEGER NOT NULL,
                    recorded_at INTEGER NOT NULL,
                    PRIMARY KEY(run_id, evidence_type, reference)
                );
            """)

    def create_run(
        self, event: InboundEvent, repo: str, allowed_repos: Iterable[str],
        mode: str = "read", workitem: Optional[WorkItemKey] = None,
    ) -> str:
        alias = check_repo_alias(repo)
        if alias not in frozenset(check_repo_alias(x) for x in allowed_repos):
            raise IntakeRejected("repository is not authorized")
        if mode not in ("read", "review", "edit"):
            raise IntakeRejected("invalid execution mode")
        if workitem is not None and workitem.tenant != event.tenant:
            raise IntakeRejected("external WorkItem tenant mismatch")
        run_id = uuid.uuid4().hex
        when = int(time.time())
        with contextlib.closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO fea_runs "
                    "(run_id,tenant,chat,actor,repo,mode,provider,workspace,kind,"
                    "item_id,workitem_fp,status,revision,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,'proposed',0,?,?)",
                    (run_id, event.tenant, event.chat, event.actor, alias, mode,
                     workitem.provider if workitem else None,
                     workitem.workspace if workitem else None,
                     workitem.kind if workitem else None,
                     workitem.item_id if workitem else None,
                     workitem.fingerprint if workitem else None, when, when),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return run_id

    def get_run(self, run_id: str, event: Optional[InboundEvent] = None) -> dict:
        _check_id(run_id, "run_id")
        with contextlib.closing(self._connect()) as db:
            row = db.execute("SELECT * FROM fea_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise IntakeRejected("run not found")
        record = dict(row)
        if event is not None and (record["tenant"], record["chat"], record["actor"]) != (
            event.tenant, event.chat, event.actor
        ):
            raise IntakeRejected("run ownership mismatch")
        return record

    def transition(
        self, run_id: str, expected_revision: int, status: str,
        actor: str,
    ) -> dict:
        _check_id(actor, "actor")
        if status not in _TRANSITIONS:
            raise IntakeRejected("unsupported run status")
        with contextlib.closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT actor,status,revision,workitem_fp FROM fea_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if row is None or row["actor"] != actor:
                    raise IntakeRejected("run not found or actor mismatch")
                if row["revision"] != expected_revision:
                    raise IntakeRejected("stale run revision")
                if status not in _TRANSITIONS[row["status"]]:
                    raise IntakeRejected("run status transition denied")
                if status == "completed" and row["workitem_fp"]:
                    evidence = db.execute(
                        "SELECT evidence_type, verifier, verified FROM fea_evidence "
                        "WHERE run_id=?", (run_id,),
                    ).fetchall()
                    kinds = {r["evidence_type"] for r in evidence if r["verified"]}
                    qa_independent = any(
                        r["evidence_type"] == "qa" and r["verified"]
                        and r["verifier"] != actor for r in evidence
                    )
                    if not ({"pr", "ci", "qa"}.issubset(kinds) and qa_independent):
                        raise IntakeRejected("external workitem requires PR, CI, independent QA")
                now = int(time.time())
                db.execute(
                    "UPDATE fea_runs SET status=?,revision=revision+1,updated_at=? "
                    "WHERE run_id=?", (status, now, run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return self.get_run(run_id)

    def add_evidence(
        self, run_id: str, evidence_type: str, reference: str,
        verifier: str, verified: bool = False,
    ) -> None:
        """Record an assertion; verified=True is for an independently trusted adapter.

        This method does not itself prove an external fact. In particular an
        interactive user input must not be allowed to set verified=True.
        """
        self.get_run(run_id)
        if evidence_type not in _EVIDENCE_TYPES or not isinstance(reference, str):
            raise IntakeRejected("unsupported evidence")
        if not _REF.fullmatch(reference):
            raise IntakeRejected("invalid evidence reference")
        _check_id(verifier, "verifier")
        with contextlib.closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "INSERT INTO fea_evidence "
                    "(run_id,evidence_type,reference,verifier,verified,recorded_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (run_id, evidence_type, reference, verifier,
                     int(verified), int(time.time())),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise IntakeRejected("duplicate evidence must not be rewritten") from exc
            except Exception:
                db.rollback()
                raise

    def workitem_runs(self, key: WorkItemKey) -> list:
        with contextlib.closing(self._connect()) as db:
            rows = db.execute(
                "SELECT run_id,repo,status,revision FROM fea_runs "
                "WHERE workitem_fp=? ORDER BY created_at,run_id",
                (key.fingerprint,),
            ).fetchall()
        return [dict(row) for row in rows]
