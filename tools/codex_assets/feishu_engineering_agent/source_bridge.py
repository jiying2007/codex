"""Optional, explicitly-authorized Feishu Project/TAPD read-only enrichment.

Provider reader is injected by an authorized host adapter. A tenant with no
enterprise API can still use manual intake and handoff unchanged.
"""
from __future__ import annotations

import contextlib
import hashlib
import time
from typing import Callable, Mapping, Optional

from .models import InboundEvent, IntakeRejected, WorkItemKey
from .state import RunStore
from .workitems import WorkItemSnapshot


class SourceReconciler:
    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_source_reads (
                    run_id TEXT NOT NULL, source_version TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL, provider TEXT NOT NULL,
                    observed_at INTEGER NOT NULL,
                    PRIMARY KEY(run_id,source_version)
                );
            """)

    def read_optional(
        self, run_id: str, event: InboundEvent,
        reader: Optional[Callable[[WorkItemKey], WorkItemSnapshot]],
        source_read_enabled: bool = False,
    ) -> dict:
        """Return real provider text only in the immediate authorized response.

        No silent credential fallback, no permanent raw WorkItem copy, no
        write/close permission, and no model call.
        """
        run = self.store.get_run(run_id, event)
        if (not run["provider"] or not run["workitem_fp"]
                or not run["workspace"] or not run["item_id"]):
            raise IntakeRejected("run is not linked to an external WorkItem")
        if not source_read_enabled or reader is None:
            return {
                "source": "user_supplied_unverified",
                "source_api_available": False, "model_invoked": False,
                "run_id": run_id,
            }
        if not callable(reader):
            raise IntakeRejected("independent provider reader required")
        key = WorkItemKey(
            run["provider"], run["tenant"], run["workspace"],
            run["kind"], run["item_id"],
        )
        snapshot = reader(key)
        if not isinstance(snapshot, WorkItemSnapshot) or snapshot.key != key:
            raise IntakeRejected("provider WorkItem response not verifiably scoped")
        canonical = (
            snapshot.title + "\n" + snapshot.description + "\n" +
            snapshot.state + "\n" + snapshot.version
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    "SELECT content_sha256 FROM fea_source_reads "
                    "WHERE run_id=? AND source_version=?",
                    (run_id, snapshot.version),
                ).fetchone()
                if prior is not None and prior["content_sha256"] != digest:
                    raise IntakeRejected("provider reused the same version with new content")
                if prior is None:
                    db.execute(
                        "INSERT INTO fea_source_reads "
                        "(run_id,source_version,content_sha256,provider,observed_at) "
                        "VALUES (?,?,?,?,?)",
                        (run_id, snapshot.version, digest, run["provider"],
                         int(time.time())),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {
            "run_id": run_id, "source": "provider_read_only",
            "source_api_available": True, "model_invoked": False,
            "title": snapshot.title, "description": snapshot.description,
            "state": snapshot.state, "version": snapshot.version,
            "workitem_closed": False,
        }
