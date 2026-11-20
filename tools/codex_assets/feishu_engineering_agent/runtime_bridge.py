"""Codex native turn coordinator: exact sessions, durable effect receipt, no replay.

A trusted caller supplies an already authenticated Feishu event, a SessionRegistry
binding, an independently qualified transport and an explicit RuntimeGrant.
No default Codex process launch, model call, fallback to --last or polling loop.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from typing import Any, Callable, Mapping, Optional

from .models import InboundEvent, IntakeRejected, _check_id
from .sessions import RuntimeGrant, SessionRegistry
from .state import RunStore


class RemoteOutcomeUnknown(IntakeRejected):
    """A remote/model effect may have happened; never retry automatically."""


class NativeTurnCoordinator:
    """Durable run+turn one-shot dispatch and observed lifecycle."""

    def __init__(self, store: RunStore, sessions: SessionRegistry):
        self.store = store
        self.sessions = sessions
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_turn_effects (
                    run_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL, turn_id TEXT NOT NULL DEFAULT '',
                    request_hash TEXT NOT NULL, effect_state TEXT NOT NULL,
                    observed_status TEXT NOT NULL DEFAULT '',
                    started_at INTEGER NOT NULL, finished_at INTEGER,
                    last_error TEXT NOT NULL DEFAULT ''
                );
            """)

    def dispatch(
        self, run_id: str, event: InboundEvent, host: str,
        repo_path: str, codex_home: str,
        grant: Optional[RuntimeGrant], prompt: str,
        send: Callable[[dict], Mapping[str, Any]],
        model_calls_enabled: bool = False,
    ) -> dict:
        """Send exactly once after recording a remote effect in private SQLite.

        A result of turn/start is only an acknowledgement. Real turn success
        requires a correlated turn/completed notification later.
        """
        if not callable(send):
            raise IntakeRejected("trusted native Codex sender required")
        run = self.store.get_run(run_id, event)
        if run["status"] != "queued":
            raise IntakeRejected("run must be explicitly queued and authorized")
        binding = self.sessions.exact(run_id, event, host, repo_path, codex_home)
        rpc = self.sessions.turn_request(
            binding, grant, prompt, model_calls_enabled=model_calls_enabled,
        )
        # A dataclass supplied by a chat/card handler is not itself an approval.
        # Require the independent, signed WorkItem approval to have been
        # durably admitted by EngineeringWorkflow before any model effect.
        with contextlib.closing(self.store._connect()) as approval_db:
            receipt = approval_db.execute(
                "SELECT approval_ref,billing_source FROM fea_run_approvals "
                "WHERE run_id=?", (run_id,),
            ).fetchone()
        if (receipt is None or grant is None
                or receipt["approval_ref"] != grant.authorization_ref
                or receipt["billing_source"] != grant.billing_source):
            raise IntakeRejected("native Codex turn lacks persistent signed approval")
        # request_hash is only metadata; do not save prompt or model response.
        import hashlib
        digest = hashlib.sha256(
            json.dumps(rpc, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                found = db.execute(
                    "SELECT 1 FROM fea_turn_effects WHERE run_id=?", (run_id,),
                ).fetchone()
                current = db.execute(
                    "SELECT status,revision FROM fea_runs WHERE run_id=?", (run_id,),
                ).fetchone()
                if (found is not None or current is None
                        or current["status"] != "queued"):
                    raise IntakeRejected("run already dispatched or status changed")
                now = int(time.time())
                db.execute(
                    "INSERT INTO fea_turn_effects "
                    "(run_id,thread_id,request_hash,effect_state,started_at) "
                    "VALUES (?,?,?,'sending',?)",
                    (run_id, binding["thread_id"], digest, now),
                )
                db.execute(
                    "UPDATE fea_runs SET status='running',revision=revision+1,"
                    "updated_at=? WHERE run_id=?", (now, run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        try:
            response = send(rpc)
            if not isinstance(response, Mapping) or response.get("error"):
                raise RemoteOutcomeUnknown("native transport response unverified")
            result = response.get("result")
            turn = result.get("turn") if isinstance(result, dict) else None
            turn_id = turn.get("id") if isinstance(turn, dict) else None
            _check_id(turn_id, "turn_id")
        except Exception as exc:
            # A timeout, local failure or unknown acknowledgement cannot prove
            # that no paid model call occurred.
            with contextlib.closing(self.store._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "UPDATE fea_turn_effects SET effect_state='unknown',"
                        "last_error=? WHERE run_id=?",
                        (type(exc).__name__, run_id),
                    )
                    db.execute(
                        "UPDATE fea_runs SET status='unknown',revision=revision+1,"
                        "updated_at=? WHERE run_id=?",
                        (int(time.time()), run_id),
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            raise RemoteOutcomeUnknown("Codex turn outcome UNKNOWN; no automatic replay") from exc
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "UPDATE fea_turn_effects SET effect_state='started',turn_id=? "
                    "WHERE run_id=? AND effect_state='sending'",
                    (turn_id, run_id),
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                raise RemoteOutcomeUnknown("Codex acknowledgement not durably stored") from exc
        return {"run_id": run_id, "turn_id": turn_id,
                "status": "running", "verified_complete": False}

    def observe(
        self, run_id: str, event: InboundEvent, notification: Mapping[str, Any],
    ) -> dict:
        """Accept only native notifications correlated to the exact run+turn.

        A mere response/streamed text is never a final result, CI or QA proof.
        """
        run = self.store.get_run(run_id, event)
        if not isinstance(notification, Mapping):
            raise IntakeRejected("invalid Codex notification")
        if notification.get("method") != "turn/completed":
            raise IntakeRejected("not a terminal Codex turn event")
        params = notification.get("params")
        if not isinstance(params, dict):
            raise IntakeRejected("missing Codex terminal params")
        turn = params.get("turn")
        if not isinstance(turn, dict):
            raise IntakeRejected("missing Codex terminal turn")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                attempt = db.execute(
                    "SELECT * FROM fea_turn_effects WHERE run_id=?", (run_id,),
                ).fetchone()
                if (attempt is None or attempt["effect_state"] not in
                        ("started", "interrupting", "observed") or not attempt["turn_id"]):
                    raise IntakeRejected("no active observed native turn")
                if (params.get("threadId") != attempt["thread_id"]
                        or turn.get("id") != attempt["turn_id"]):
                    raise IntakeRejected("turn notification source mismatch")
                status = turn.get("status")
                if status not in ("completed", "failed", "interrupted"):
                    raise IntakeRejected("unknown native terminal status")
                if attempt["effect_state"] == "observed":
                    if attempt["observed_status"] != status:
                        raise IntakeRejected("conflicting terminal notification")
                    db.rollback()
                    return {"run_id": run_id, "duplicate": True, "turn_status": status}
                if run["status"] != "running":
                    raise IntakeRejected("run no longer active")
                new_run_status = ("waiting_ci" if status == "completed" else
                                  "failed" if status == "failed" else "unknown")
                now = int(time.time())
                db.execute(
                    "UPDATE fea_turn_effects SET effect_state='observed',"
                    "observed_status=?,finished_at=? WHERE run_id=?",
                    (status, now, run_id),
                )
                db.execute(
                    "UPDATE fea_runs SET status=?,revision=revision+1,updated_at=? "
                    "WHERE run_id=?",
                    (new_run_status, now, run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"run_id": run_id, "turn_status": status,
                "run_status": new_run_status, "duplicate": False}

    def interrupt(
        self, run_id: str, event: InboundEvent,
        host: str, repo_path: str, codex_home: str,
        send: Callable[[dict], Mapping[str, Any]],
    ) -> dict:
        """Interrupt only the currently running exact turn, not a guessed session."""
        binding = self.sessions.exact(run_id, event, host, repo_path, codex_home)
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT * FROM fea_turn_effects WHERE run_id=?", (run_id,),
                ).fetchone()
                if (row is None or row["effect_state"] != "started"
                        or row["thread_id"] != binding["thread_id"]):
                    raise IntakeRejected("cannot interrupt unobserved turn")
                db.execute(
                    "UPDATE fea_turn_effects SET effect_state='interrupting' "
                    "WHERE run_id=?", (run_id,),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        try:
            response = send(self.sessions.interrupt_request(binding, row["turn_id"]))
            if not isinstance(response, Mapping) or response.get("error"):
                raise RemoteOutcomeUnknown("interrupt acknowledgement uncertain")
        except Exception as exc:
            with contextlib.closing(self.store._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "UPDATE fea_turn_effects SET effect_state='unknown',"
                        "last_error=? WHERE run_id=?",
                        (type(exc).__name__, run_id),
                    )
                    db.execute(
                        "UPDATE fea_runs SET status='unknown',revision=revision+1,"
                        "updated_at=? WHERE run_id=?",
                        (int(time.time()), run_id),
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            raise RemoteOutcomeUnknown("interrupt status UNKNOWN, no replay") from exc
        # An ACK does not establish that the turn has actually stopped.
        return {"run_id": run_id, "interruption_requested": True,
                "turn_stopped": False}

    def restart_recovery(self, run_id: str, event: InboundEvent) -> str:
        """Mark abandoned running/interrupting effects UNKNOWN once after restart."""
        self.store.get_run(run_id, event)
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT effect_state FROM fea_turn_effects WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if row is None:
                    raise IntakeRejected("no native turn attempt")
                if row["effect_state"] == "observed":
                    db.rollback()
                    return "observed"
                db.execute(
                    "UPDATE fea_turn_effects SET effect_state='unknown' WHERE run_id=?",
                    (run_id,),
                )
                db.execute(
                    "UPDATE fea_runs SET status='unknown',revision=revision+1,"
                    "updated_at=? WHERE run_id=? AND status='running'",
                    (int(time.time()), run_id),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return "unknown"
