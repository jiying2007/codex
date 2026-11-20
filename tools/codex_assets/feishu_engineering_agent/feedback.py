"""Return verified engineering results to source WorkItem, optionally via API.

No automatic closure. When project/TAPD write API is unavailable a text
handoff is produced for the original product/test owner to paste manually.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import sqlite3
import time
from typing import Callable, Mapping, Optional

from .models import InboundEvent, IntakeRejected, _check_id
from .state import RunStore, _REF


class FeedbackUnknown(IntakeRejected):
    """May have been posted; cannot retry the same remote write blindly."""


class SourceFeedback:
    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_feedback (
                    run_id TEXT PRIMARY KEY, effect_state TEXT NOT NULL,
                    remote_reference TEXT NOT NULL DEFAULT '',
                    error_kind TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                );
            """)

    def draft(self, run_id: str, event: InboundEvent) -> str:
        run = self.store.get_run(run_id, event)
        if not run["provider"] or not run["workitem_fp"]:
            raise IntakeRejected("source WorkItem link required")
        with contextlib.closing(self.store._connect()) as db:
            receipts = db.execute(
                "SELECT evidence_type, reference FROM fea_evidence "
                "WHERE run_id=? AND verified=1 ORDER BY evidence_type,reference",
                (run_id,),
            ).fetchall()
        evidence = "; ".join(x["evidence_type"] + ":" + x["reference"]
                             for x in receipts) or "尚无已核验的 Git/CI/QA 证据"
        return (
            "【研发状态同步；人工核对原系统需求/缺陷】\n"
            "工作项：" + run["provider"] + "/" + run["workspace"] + "/"
            + run["kind"] + "/" + run["item_id"] + "\n"
            "AgentRun：" + run_id + "；仓库：" + run["repo"] + "\n"
            "研发状态：" + run["status"] + "\n"
            "证据：" + evidence + "\n"
            "工作项来源可能是用户手工提供，未自动核验原系统内容。\n"
            "此文字不代表产品/测试已验收；请原系统负责人复核并按业务流程决定是否关闭。"
        )

    @staticmethod
    def sign_feedback(run: Mapping, event: InboundEvent,
                      source_revision: str, approval_ref: str,
                      secret: bytes) -> str:
        """Signed by independent source-write policy, never by user chat."""
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise IntakeRejected("source comment approval key unavailable")
        payload = [
            run["run_id"], event.tenant, event.chat, event.actor, run["repo"],
            run["provider"], run["workspace"], run["kind"], run["item_id"],
            source_revision, approval_ref,
        ]
        return hmac.new(
            secret,
            json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def post_once(
        self, run_id: str, event: InboundEvent,
        source_revision: str, approval_ref: str,
        writer: Callable[[dict], Mapping[str, str]],
        remote_write_enabled: bool = False,
        approval_signature: str = "",
        private_approval_key: bytes = b"",
    ) -> dict:
        """An explicit source-comment-only write; never changes WorkItem status."""
        run = self.store.get_run(run_id, event)
        if not remote_write_enabled or not callable(writer):
            raise IntakeRejected("external WorkItem writes disabled")
        if not run["provider"] or not run["workitem_fp"] or run["status"] not in (
            "waiting_qa", "completed",
        ):
            raise IntakeRejected("source feedback requires linked verified work")
        _check_id(source_revision, "source_revision")
        _check_id(approval_ref, "approval_ref")
        if (not isinstance(approval_signature, str)
                or not hmac.compare_digest(
                    approval_signature,
                    self.sign_feedback(run, event, source_revision, approval_ref,
                                       private_approval_key),
                )):
            raise IntakeRejected("independent source-comment approval required")
        now = int(time.time())
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    "SELECT effect_state FROM fea_feedback WHERE run_id=?", (run_id,),
                ).fetchone()
                if prior:
                    raise IntakeRejected("feedback already attempted; no replay")
                db.execute(
                    "INSERT INTO fea_feedback(run_id,effect_state,created_at) "
                    "VALUES (?,'sending',?)", (run_id, now),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        request = {
            "provider": run["provider"], "workspace": run["workspace"],
            "kind": run["kind"], "item_id": run["item_id"],
            "source_revision": source_revision, "approval_ref": approval_ref,
            "comment": self.draft(run_id, event),
            "operation": "append_comment_only",
        }
        try:
            observed = writer(request)
            if (not isinstance(observed, Mapping)
                    or observed.get("operation") != "append_comment_only"
                    or observed.get("provider") != run["provider"]
                    or observed.get("item_id") != run["item_id"]):
                raise FeedbackUnknown("unverified external feedback receipt")
            remote_ref = observed.get("reference")
            if not isinstance(remote_ref, str) or not _REF.fullmatch(remote_ref):
                raise FeedbackUnknown("unverified bounded source comment reference")
        except Exception as exc:
            with contextlib.closing(self.store._connect()) as db:
                db.execute(
                    "UPDATE fea_feedback SET effect_state='unknown',error_kind=? "
                    "WHERE run_id=?", (type(exc).__name__, run_id),
                )
                db.commit()
            raise FeedbackUnknown("source feedback outcome UNKNOWN") from exc
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "UPDATE fea_feedback SET effect_state='acknowledged',"
                    "remote_reference=? WHERE run_id=? AND effect_state='sending'",
                    (observed["reference"], run_id),
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                raise FeedbackUnknown("source feedback receipt persistence UNKNOWN") from exc
        return {"run_id": run_id, "source_comment": observed["reference"],
                "source_workitem_closed": False, "write": "acknowledged_only"}

    def recover_unknown(self, run_id: str, event: InboundEvent) -> str:
        self.store.get_run(run_id, event)
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT effect_state FROM fea_feedback WHERE run_id=?",
                                 (run_id,)).fetchone()
                if row is None:
                    raise IntakeRejected("feedback never attempted")
                if row["effect_state"] == "sending":
                    db.execute(
                        "UPDATE fea_feedback SET effect_state='unknown' WHERE run_id=?",
                        (run_id,),
                    )
                    db.commit()
                    return "unknown"
                db.rollback()
                return row["effect_state"]
            except Exception:
                db.rollback()
                raise
