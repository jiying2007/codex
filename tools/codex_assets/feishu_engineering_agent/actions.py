"""Resolve durable card intents without treating clicks as execution authority."""
from __future__ import annotations

import contextlib
import sqlite3
import time
from typing import Iterable

from .models import InboundEvent, IntakeRejected, _check_id
from .state import RunStore


class CardActionQueue:
    """Owner-scoped text/card action receipts; no model, API or Git operation."""

    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_card_resolutions (
                    click_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    result TEXT NOT NULL,
                    resolved_at INTEGER NOT NULL
                );
            """)

    def pending_for(self, event: InboundEvent, limit: int = 20) -> list:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise IntakeRejected("pending action limit invalid")
        with contextlib.closing(self.store._connect()) as db:
            rows = db.execute(
                "SELECT a.click_key,a.action,a.card_id,c.run_id,r.repo "
                "FROM fea_card_actions a JOIN fea_cards c ON c.card_id=a.card_id "
                "JOIN fea_runs r ON r.run_id=c.run_id "
                "WHERE r.tenant=? AND r.chat=? AND r.actor=? "
                "AND a.handled_at IS NULL ORDER BY a.recorded_at,a.click_key LIMIT ?",
                (event.tenant, event.chat, event.actor, limit),
            ).fetchall()
        return [dict(x) for x in rows]

    def resolve(
        self, click_key: str, event: InboundEvent,
        allowed_repos: Iterable[str], result: str,
    ) -> dict:
        """A request_execution click may become only 'awaiting_policy'.

        Owner cancel can atomically cancel a run before it begins. A running
        turn must be interrupted via the native exact thread adapter instead.
        """
        _check_id(click_key, "click_key")
        if result not in ("recorded", "dismissed", "cancel_if_not_running"):
            raise IntakeRejected("unsupported card resolution")
        permitted = frozenset(allowed_repos)
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT a.action,a.handled_at,c.run_id,r.repo,r.status,"
                    "r.revision FROM fea_card_actions a "
                    "JOIN fea_cards c ON a.card_id=c.card_id "
                    "JOIN fea_runs r ON r.run_id=c.run_id "
                    "WHERE a.click_key=? AND r.tenant=? AND r.chat=? AND r.actor=?",
                    (click_key, event.tenant, event.chat, event.actor),
                ).fetchone()
                if row is None or row["repo"] not in permitted:
                    raise IntakeRejected("card action owner/repository mismatch")
                existing = db.execute(
                    "SELECT result FROM fea_card_resolutions WHERE click_key=?",
                    (click_key,),
                ).fetchone()
                if existing is not None:
                    db.rollback()
                    return {"resolved": True, "duplicate": True,
                            "result": existing["result"], "run_id": row["run_id"]}
                if row["handled_at"] is not None:
                    raise IntakeRejected("card action already processed without receipt")
                action = row["action"]
                if result == "cancel_if_not_running":
                    if action != "request_cancel" or row["status"] not in (
                        "proposed", "ready", "queued",
                    ):
                        raise IntakeRejected("only pre-run cancel is supported here")
                    db.execute(
                        "UPDATE fea_runs SET status='canceled',revision=revision+1,"
                        "updated_at=? WHERE run_id=?",
                        (int(time.time()), row["run_id"]),
                    )
                    outcome = "canceled_before_execution"
                elif action == "request_execution" and result == "recorded":
                    outcome = "awaiting_separate_runtime_and_budget_approval"
                else:
                    outcome = "dismissed_or_read"
                now = int(time.time())
                db.execute(
                    "UPDATE fea_card_actions SET handled_at=? WHERE click_key=?",
                    (now, click_key),
                )
                db.execute(
                    "INSERT INTO fea_card_resolutions "
                    "(click_key,run_id,result,resolved_at) VALUES (?,?,?,?)",
                    (click_key, row["run_id"], outcome, now),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"resolved": True, "duplicate": False,
                "run_id": row["run_id"], "result": outcome,
                "model_started": False, "external_effect": False}
