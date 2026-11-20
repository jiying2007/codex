"""Versioned cross-repository interface contract and independent checks.

Transport-agnostic: UART, SPI, REST, protobuf, sensor APIs or SoC/MCU firmware
can all use the same immutable contract digest. Does not infer HIL from CI.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from typing import Callable, Iterable, Mapping

from .models import InboundEvent, IntakeRejected, WorkItemKey, _check_id, check_repo_alias
from .state import RunStore, _REF


class ContractRegistry:
    def __init__(self, store: RunStore):
        self.store = store
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_contracts (
                    workitem_fp TEXT NOT NULL, contract_id TEXT NOT NULL,
                    semantic_version TEXT NOT NULL, sha256 TEXT NOT NULL,
                    participants_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                    PRIMARY KEY(workitem_fp,contract_id)
                );
                CREATE TABLE IF NOT EXISTS fea_contract_checks (
                    workitem_fp TEXT NOT NULL, contract_id TEXT NOT NULL,
                    repository TEXT NOT NULL, run_id TEXT NOT NULL,
                    reference TEXT NOT NULL, checked_at INTEGER NOT NULL,
                    PRIMARY KEY(workitem_fp,contract_id,repository)
                );
            """)

    @staticmethod
    def _digest(value: str) -> str:
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)):
            raise IntakeRejected("exact SHA-256 contract content digest required")
        return value

    def register(
        self, key: WorkItemKey, contract_id: str, version: str,
        sha256: str, participants: Iterable[str],
        event: InboundEvent, allowed_repos: Iterable[str],
    ) -> dict:
        if event.tenant != key.tenant:
            raise IntakeRejected("WorkItem tenant mismatch")
        _check_id(contract_id, "contract_id")
        _check_id(version, "semantic_version")
        digest = self._digest(sha256)
        names = tuple(sorted({check_repo_alias(p) for p in participants}))
        if not 2 <= len(names) <= 8:
            raise IntakeRejected("cross-repo contract needs 2-8 named repositories")
        if not set(names).issubset({check_repo_alias(x) for x in allowed_repos}):
            raise IntakeRejected("cross-repo contract outside repository allowlist")
        with contextlib.closing(self.store._connect()) as db:
            has_owner_run = db.execute(
                "SELECT 1 FROM fea_runs WHERE workitem_fp=? AND tenant=? "
                "AND chat=? AND actor=? LIMIT 1",
                (key.fingerprint, event.tenant, event.chat, event.actor),
            ).fetchone()
            if not has_owner_run:
                raise IntakeRejected("contract requires a source-scoped owned run")
            db.execute("BEGIN IMMEDIATE")
            try:
                prior = db.execute(
                    "SELECT semantic_version,sha256,participants_json "
                    "FROM fea_contracts WHERE workitem_fp=? AND contract_id=?",
                    (key.fingerprint, contract_id),
                ).fetchone()
                if prior is not None:
                    if (prior["semantic_version"] != version
                            or prior["sha256"] != digest
                            or json.loads(prior["participants_json"]) != list(names)):
                        raise IntakeRejected("immutable cross-repo contract version changed")
                    db.rollback()
                    return {"contract_id": contract_id, "duplicate": True}
                db.execute(
                    "INSERT INTO fea_contracts "
                    "(workitem_fp,contract_id,semantic_version,sha256,"
                    "participants_json,created_at) VALUES (?,?,?,?,?,?)",
                    (key.fingerprint, contract_id, version, digest,
                     json.dumps(names), int(time.time())),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        return {"contract_id": contract_id, "duplicate": False, "participants": names}

    def verify_repository(
        self, run_id: str, event: InboundEvent, contract_id: str,
        reference: str, trusted_observer: Callable[[str], Mapping],
    ) -> dict:
        run = self.store.get_run(run_id, event)
        if not run["workitem_fp"]:
            raise IntakeRejected("cross-repo proof requires linked WorkItem")
        _check_id(contract_id, "contract_id")
        if not isinstance(reference, str) or not _REF.fullmatch(reference):
            raise IntakeRejected("invalid contract evidence reference")
        with contextlib.closing(self.store._connect()) as db:
            spec = db.execute(
                "SELECT * FROM fea_contracts WHERE "
                "workitem_fp=? AND contract_id=?",
                (run["workitem_fp"], contract_id),
            ).fetchone()
        if spec is None or run["repo"] not in json.loads(spec["participants_json"]):
            raise IntakeRejected("repository not part of this versioned contract")
        if not callable(trusted_observer):
            raise IntakeRejected("independent contract observer required")
        observed = trusted_observer(reference)
        if (not isinstance(observed, Mapping)
                or observed.get("repo_alias") != run["repo"]
                or observed.get("reference") != reference
                or observed.get("contract_sha256") != spec["sha256"]
                or observed.get("semantic_version") != spec["semantic_version"]
                or observed.get("ci_conclusion") != "success"):
            raise IntakeRejected("contract identity/CI evidence mismatch")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute(
                    "SELECT run_id,reference FROM fea_contract_checks WHERE "
                    "workitem_fp=? AND contract_id=? AND repository=?",
                    (run["workitem_fp"], contract_id, run["repo"]),
                ).fetchone()
                if existing is not None:
                    if existing["run_id"] != run_id or existing["reference"] != reference:
                        raise IntakeRejected("contract proof cannot be reassigned")
                    db.rollback()
                    return {"verified": True, "duplicate": True, "device_pass": False}
                now = int(time.time())
                db.execute(
                    "INSERT INTO fea_contract_checks "
                    "(workitem_fp,contract_id,repository,run_id,reference,checked_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (run["workitem_fp"], contract_id, run["repo"], run_id,
                     reference, now),
                )
                db.execute(
                    "INSERT INTO fea_evidence "
                    "(run_id,evidence_type,reference,verifier,verified,recorded_at) "
                    "VALUES (?,'contract',?,'trusted_contract_ci',1,?)",
                    (run_id, reference, now),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        # CI-backed contract proof and device acceptance remain separate.
        return {"verified": True, "duplicate": False, "device_pass": False}

    def status(
        self, key: WorkItemKey, contract_id: str, event: InboundEvent,
        allowed_repos: Iterable[str],
    ) -> dict:
        if event.tenant != key.tenant:
            raise IntakeRejected("contract tenant mismatch")
        _check_id(contract_id, "contract_id")
        with contextlib.closing(self.store._connect()) as db:
            owned = db.execute(
                "SELECT repo FROM fea_runs WHERE workitem_fp=? AND tenant=? "
                "AND chat=? AND actor=?",
                (key.fingerprint, event.tenant, event.chat, event.actor),
            ).fetchall()
            if not ({r["repo"] for r in owned} & set(allowed_repos)):
                raise IntakeRejected("no authorized linked run for this contract")
            spec = db.execute(
                "SELECT semantic_version,sha256,participants_json "
                "FROM fea_contracts WHERE workitem_fp=? AND contract_id=?",
                (key.fingerprint, contract_id),
            ).fetchone()
            if spec is None:
                raise IntakeRejected("contract not registered")
            observed = db.execute(
                "SELECT repository FROM fea_contract_checks "
                "WHERE workitem_fp=? AND contract_id=?",
                (key.fingerprint, contract_id),
            ).fetchall()
        participants = set(json.loads(spec["participants_json"]))
        missing = sorted(participants - {r["repository"] for r in observed})
        return {
            "contract_id": contract_id, "version": spec["semantic_version"],
            "sha256": spec["sha256"], "all_repositories_verified": not missing,
            "missing": missing, "device_verified": False,
            "business_accepted": False,
        }
