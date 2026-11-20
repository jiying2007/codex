"""Small-team PR/CI/QA proof coordinator, not a second project manager.

WorkItem remains authoritative in Feishu Project/TAPD. Git publication is
effect-once with a durable UNKNOWN outcome. Evidence verification is delegated
to trusted read-only provider observers, not inferred from pasted chat text.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import hmac
import json
import re
import sqlite3
import time
from typing import Any, Callable, Mapping, Optional

from .models import InboundEvent, IntakeRejected, _check_id
from .state import RunStore, _REF


class PublicationUnknown(IntakeRejected):
    """A remote PR creation may have succeeded, never blindly replay."""


@dataclasses.dataclass(frozen=True)
class PublicationGrant:
    run_id: str
    actor: str
    repository: str
    approval_ref: str
    expires_at: int

    def __post_init__(self):
        for field in ("run_id", "actor", "repository", "approval_ref"):
            _check_id(getattr(self, field), field)

    def canonical(self) -> bytes:
        return json.dumps(dataclasses.asdict(self), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")


class DeliveryCoordinator:
    """Evidence gate and one-shot Git publication under independent approval."""

    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_publications (
                    run_id TEXT PRIMARY KEY, repo_full_name TEXT NOT NULL,
                    target_ref TEXT NOT NULL, head_sha TEXT NOT NULL,
                    effect_state TEXT NOT NULL, remote_pr_id TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS fea_qa_attestations (
                    run_id TEXT NOT NULL, reviewer TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, workitem_fingerprint TEXT NOT NULL,
                    head_sha TEXT NOT NULL, attested_at INTEGER NOT NULL,
                    PRIMARY KEY(run_id,reviewer,evidence_ref)
                );
            """)

    @staticmethod
    def sign_publication(grant: PublicationGrant, secret: bytes) -> str:
        """Only the separate Git authorization issuer should sign this grant."""
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise IntakeRejected("private Git approval key must be >=32 bytes")
        return hmac.new(secret, grant.canonical(), hashlib.sha256).hexdigest()

    @staticmethod
    def _sha(value: str) -> str:
        if (not isinstance(value, str) or len(value) != 40
                or any(c not in "0123456789abcdef" for c in value)):
            raise IntakeRejected("exact 40-hex commit SHA required")
        return value

    @staticmethod
    def _repo_full_name(value: str) -> str:
        if (not isinstance(value, str) or len(value) > 150 or
                value.count("/") != 1):
            raise IntakeRejected("expected owner/repo")
        for part in value.split("/"):
            _check_id(part, "repository component")
        return value

    def publish_once(
        self, run_id: str, event: InboundEvent, grant: PublicationGrant,
        repo_full_name: str, head_sha: str, target_ref: str,
        publisher: Callable[[dict], Mapping[str, Any]],
        remote_write_enabled: bool = False,
        now: Optional[int] = None,
        approval_signature: str = "",
        private_approval_key: bytes = b"",
    ) -> dict:
        """Create a PR exactly once; commit was produced and reviewed elsewhere."""
        run = self.store.get_run(run_id, event)
        when = int(time.time()) if now is None else int(now)
        if (not remote_write_enabled or grant.expires_at <= when
                or grant.expires_at > when + 3600
                or (grant.run_id, grant.actor, grant.repository) !=
                (run_id, event.actor, run["repo"])):
            raise IntakeRejected("independent Git publication authorization required")
        if (not isinstance(approval_signature, str)
                or not hmac.compare_digest(
                    approval_signature, self.sign_publication(grant, private_approval_key)
                )):
            raise IntakeRejected("signed independent PR publication grant required")
        if run["mode"] != "edit" or run["status"] != "waiting_ci":
            raise IntakeRejected("publication requires reviewed edited run")
        if not callable(publisher):
            raise IntakeRejected("trusted publisher is required")
        repo = self._repo_full_name(repo_full_name)
        sha = self._sha(head_sha)
        if (not isinstance(target_ref, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", target_ref)
                or ".." in target_ref or "//" in target_ref
                or target_ref.endswith(".lock")):
            raise IntakeRejected("invalid bounded Git target ref")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    "SELECT 1 FROM fea_publications WHERE run_id=?", (run_id,),
                ).fetchone()
                if prior is not None:
                    raise IntakeRejected("publication already attempted; reconcile, never replay")
                db.execute(
                    "INSERT INTO fea_publications "
                    "(run_id,repo_full_name,target_ref,head_sha,effect_state,created_at) "
                    "VALUES (?,?,?,?, 'sending',?)",
                    (run_id, repo, target_ref, sha, when),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        request = {"run_id": run_id, "repo_full_name": repo,
                   "head_sha": sha, "target_ref": target_ref,
                   "approval_ref": grant.approval_ref}
        try:
            result = publisher(request)
            if not isinstance(result, Mapping):
                raise PublicationUnknown("unverified publisher receipt")
            returned = result.get("pr_id")
            _check_id(returned, "pr_id")
            if result.get("head_sha") != sha or result.get("repo_full_name") != repo:
                raise PublicationUnknown("publication receipt identity mismatch")
        except Exception as exc:
            with contextlib.closing(self.store._connect()) as db:
                db.execute(
                    "UPDATE fea_publications SET effect_state='unknown',last_error=? "
                    "WHERE run_id=?", (type(exc).__name__, run_id),
                )
                db.commit()
            raise PublicationUnknown("Git publication effect UNKNOWN") from exc
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    "UPDATE fea_publications SET effect_state='acknowledged',remote_pr_id=? "
                    "WHERE run_id=? AND effect_state='sending'",
                    (returned, run_id),
                )
                db.commit()
            except Exception as exc:
                db.rollback()
                raise PublicationUnknown("publication receipt not durably persisted") from exc
        return {"run_id": run_id, "pr_id": returned,
                "publication": "acknowledged_not_verified"}

    def verify_git(
        self, run_id: str, event: InboundEvent,
        evidence_type: str, reference: str, head_sha: str,
        observer: Callable[[str], Mapping[str, Any]],
    ) -> dict:
        """Source must be verified by a separately trusted, read-only Git adapter."""
        if evidence_type not in ("pr", "ci", "contract"):
            raise IntakeRejected("Git observer may verify only PR/CI/contract")
        run = self.store.get_run(run_id, event)
        sha = self._sha(head_sha)
        if not callable(observer):
            raise IntakeRejected("trusted Git source observer required")
        observed = observer(reference)
        if not isinstance(observed, Mapping) or observed.get("head_sha") != sha:
            raise IntakeRejected("Git evidence SHA mismatched")
        if (observed.get("repo_alias") != run["repo"]
                or observed.get("reference") != reference):
            raise IntakeRejected("Git evidence repository or reference mismatched")
        if evidence_type == "ci" and observed.get("conclusion") != "success":
            raise IntakeRejected("CI not successful")
        if evidence_type == "pr" and observed.get("state") not in ("open", "merged"):
            raise IntakeRejected("PR not confirmed by source")
        if evidence_type == "contract" and not observed.get("contract_verified"):
            raise IntakeRejected("cross-repo contract not verified")
        self.store.add_evidence(
            run_id, evidence_type, reference, verifier="trusted_git",
            verified=True,
        )
        return {"run_id": run_id, "kind": evidence_type, "verified": True,
                "head_sha": sha}

    @staticmethod
    def qa_message(
        run_id: str, fingerprint: str, head_sha: str,
        reviewer: str, evidence_ref: str, attested_at: int,
    ) -> bytes:
        for field in (run_id, reviewer):
            _check_id(field, field)
        if not isinstance(evidence_ref, str) or not _REF.fullmatch(evidence_ref):
            raise IntakeRejected("invalid QA evidence reference")
        if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise IntakeRejected("WorkItem fingerprint required")
        DeliveryCoordinator._sha(head_sha)
        if type(attested_at) is not int or attested_at < 1:
            raise IntakeRejected("invalid QA timestamp")
        payload = [run_id, fingerprint, head_sha, reviewer, evidence_ref, attested_at]
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def accept_manual_qa(
        self, run_id: str, event: InboundEvent, head_sha: str,
        reviewer: str, evidence_ref: str, attested_at: int,
        signature: str, independent_qa_secret: bytes,
        now: Optional[int] = None,
    ) -> dict:
        """QA must sign an out-of-band attestation with a private reviewer key.

        The Bot's message user cannot set verified=True or self-approve;
        no Feishu/TAPD API access is necessary for this bounded fallback.
        """
        run = self.store.get_run(run_id, event)
        when = int(time.time()) if now is None else int(now)
        if (not run["workitem_fp"] or run["status"] != "waiting_qa"
                or reviewer == event.actor or abs(when - attested_at) > 86400):
            raise IntakeRejected("independent current QA for WorkItem required")
        if (not isinstance(independent_qa_secret, bytes)
                or len(independent_qa_secret) < 32):
            raise IntakeRejected("independent QA credential missing")
        payload = self.qa_message(run_id, run["workitem_fp"], head_sha,
                                  reviewer, evidence_ref, attested_at)
        expected = hmac.new(independent_qa_secret, payload, hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            raise IntakeRejected("independent QA attestation invalid")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                previous = db.execute(
                    "SELECT 1 FROM fea_qa_attestations "
                    "WHERE run_id=? AND reviewer=? AND evidence_ref=?",
                    (run_id, reviewer, evidence_ref),
                ).fetchone()
                if previous:
                    db.rollback()
                    return {"run_id": run_id, "verified": True, "duplicate": True}
                db.execute(
                    "INSERT INTO fea_qa_attestations "
                    "(run_id,reviewer,evidence_ref,workitem_fingerprint,"
                    "head_sha,attested_at) VALUES (?,?,?,?,?,?)",
                    (run_id, reviewer, evidence_ref, run["workitem_fp"],
                     head_sha, attested_at),
                )
                db.execute(
                    "INSERT INTO fea_evidence "
                    "(run_id,evidence_type,reference,verifier,verified,recorded_at) "
                    "VALUES (?,'qa',?,?,1,?)",
                    (run_id, evidence_ref, reviewer, when),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"run_id": run_id, "verified": True,
                "source_closed": False, "duplicate": False}

    def advance_after_ci(self, run_id: str, event: InboundEvent) -> dict:
        """Move to QA only after independently observed PR and successful CI."""
        run = self.store.get_run(run_id, event)
        if run["status"] != "waiting_ci":
            raise IntakeRejected("run is not awaiting CI verification")
        with contextlib.closing(self.store._connect()) as db:
            rows = db.execute(
                "SELECT evidence_type FROM fea_evidence "
                "WHERE run_id=? AND verified=1 AND evidence_type IN ('pr','ci')",
                (run_id,),
            ).fetchall()
        if {r["evidence_type"] for r in rows} != {"pr", "ci"}:
            raise IntakeRejected("verified PR and CI both required")
        updated = self.store.transition(
            run_id, run["revision"], "waiting_qa", event.actor,
        )
        return {"run_id": run_id, "status": updated["status"],
                "source_closed": False}

    def mark_unconfirmed_remote_effects_unknown(self) -> int:
        """On restart, never replay an outstanding network write receipt."""
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                affected = db.execute(
                    "UPDATE fea_publications SET effect_state='unknown' "
                    "WHERE effect_state='sending'",
                ).rowcount
                db.commit()
                return affected
            except Exception:
                db.rollback()
                raise

    def complete_engineering_only(self, run_id: str, event: InboundEvent) -> dict:
        """Completion of AgentRun is not closure of Feishu Project/TAPD item."""
        run = self.store.get_run(run_id, event)
        result = self.store.transition(
            run_id, run["revision"], "completed", event.actor,
        )
        return {"run_id": run_id, "run_status": result["status"],
                "workitem_status": "external_owner_must_accept"}
