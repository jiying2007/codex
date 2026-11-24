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
from .sessions import SessionRegistry


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
        SessionRegistry(store)
        with contextlib.closing(store._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS fea_publications (
                    run_id TEXT PRIMARY KEY, repo_full_name TEXT NOT NULL,
                    target_ref TEXT NOT NULL, head_sha TEXT NOT NULL,
                    effect_state TEXT NOT NULL, remote_pr_id TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    last_error TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS fea_delivery_heads (
                    run_id TEXT PRIMARY KEY,
                    head_sha TEXT NOT NULL,
                    pinned_at INTEGER NOT NULL
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
                SessionRegistry.require_no_successor(db, run_id)
                prior = db.execute(
                    "SELECT 1 FROM fea_publications WHERE run_id=?", (run_id,),
                ).fetchone()
                if prior is not None:
                    raise IntakeRejected("publication already attempted; reconcile, never replay")
                pinned = db.execute(
                    "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if pinned is not None and pinned["head_sha"] != sha:
                    raise IntakeRejected("published head differs from pinned PR/CI head")
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
        if run["mode"] != "edit" or run["status"] not in ("waiting_ci", "waiting_qa"):
            raise IntakeRejected("Git delivery proof requires an active edited run")
        if not isinstance(reference, str) or not _REF.fullmatch(reference):
            raise IntakeRejected("invalid Git evidence reference")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                SessionRegistry.require_no_successor(db, run_id)
                published = db.execute(
                    "SELECT head_sha FROM fea_publications WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if published is not None and published["head_sha"] != sha:
                    raise IntakeRejected("Git evidence head differs from publication")
                pinned = db.execute(
                    "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if pinned is not None and pinned["head_sha"] != sha:
                    raise IntakeRejected("PR/CI evidence commit mismatch")
                now = int(time.time())
                if pinned is None:
                    db.execute(
                        "INSERT INTO fea_delivery_heads(run_id,head_sha,pinned_at) "
                        "VALUES (?,?,?)", (run_id, sha, now),
                    )
                db.execute(
                    "INSERT INTO fea_evidence "
                    "(run_id,evidence_type,reference,verifier,verified,recorded_at) "
                    "VALUES (?,?,?,'trusted_git',1,?)",
                    (run_id, evidence_type, reference, now),
                )
                db.commit()
            except sqlite3.IntegrityError as exc:
                db.rollback()
                raise IntakeRejected("duplicate Git evidence cannot replace proof") from exc
            except Exception:
                db.rollback()
                raise
        return {"run_id": run_id, "kind": evidence_type, "verified": True,
                "head_sha": sha}

    def snapshot(self, run_id: str, event: InboundEvent) -> dict:
        """Bounded delivery metadata for the authorized Run owner."""
        run = self.store.get_run(run_id, event)
        with contextlib.closing(self.store._connect()) as db:
            pinned = db.execute(
                "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?", (run_id,),
            ).fetchone()
            receipts = db.execute(
                "SELECT evidence_type,reference,verifier FROM fea_evidence "
                "WHERE run_id=? AND verified=1 AND evidence_type IN ('pr','ci','qa') "
                "ORDER BY evidence_type,reference LIMIT 20", (run_id,),
            ).fetchall()
        return {
            "run_id": run_id, "run_status": run["status"],
            "workitem_fingerprint": run["workitem_fp"],
            "head_sha": pinned["head_sha"] if pinned else None,
            "evidence": [dict(row) for row in receipts],
            "workitem_closed": False,
        }

    def verify_github_delivery(self, run_id: str, event: InboundEvent,
                               head_sha: str, branch: str, forge,
                               pr_number: int, ci_run_ids, required_workflows) -> dict:
        """Bind all required observed workflows and PR to the local worker commit.

        One ledger transaction records the exact proof set and advances to QA.
        Retried reads are safe; divergent evidence or a reserved continuation
        cannot replace this delivery. No remote write or product closure.
        """
        run = self.store.get_run(run_id, event)
        sha = self._sha(head_sha)
        if run["mode"] != "edit" or run["status"] not in ("waiting_ci", "waiting_qa", "completed"):
            raise IntakeRejected("delivery requires a locally completed edit")
        if forge.repo_alias != run["repo"]:
            raise IntakeRejected("Git delivery repository alias mismatch")
        observed = forge.observe_delivery(pr_number, ci_run_ids, branch, sha, required_workflows)
        root = "https://github.com/" + forge.repo_full_name
        expected = {("pr", root + "/pull/" + str(pr_number))}
        expected.update(("ci", root + "/actions/runs/" + str(i)) for i in ci_run_ids)
        if (observed["head_sha"] != sha or observed["repo_alias"] != run["repo"]
                or observed["branch"] != branch or observed["pr_number"] != pr_number
                or set(observed["workflows"]) != set(required_workflows)
                or set(observed["workflows"].values()) != set(ci_run_ids)):
            raise IntakeRejected("GitHub delivery proof mismatch")
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                current = db.execute(
                    "SELECT status,mode,revision FROM fea_runs WHERE run_id=?", (run_id,),
                ).fetchone()
                if current is None or current["mode"] != "edit" or current["status"] not in (
                        "waiting_ci", "waiting_qa", "completed"):
                    raise IntakeRejected("Run changed while observing Git delivery")
                SessionRegistry.require_no_successor(db, run_id)
                local = db.execute(
                    "SELECT reference FROM fea_evidence WHERE run_id=? "
                    "AND evidence_type='commit' AND verifier='local_codex' AND verified=0",
                    (run_id,),
                ).fetchall()
                if {row["reference"] for row in local} != {sha}:
                    raise IntakeRejected("Git delivery head does not match the local worker commit receipt")
                published = db.execute(
                    "SELECT * FROM fea_publications WHERE run_id=?", (run_id,),
                ).fetchone()
                if published is not None and (
                        published["head_sha"] != sha or published["repo_full_name"] != forge.repo_full_name
                        or published["target_ref"] != "refs/heads/" + branch
                        or (published["remote_pr_id"] and published["remote_pr_id"] != str(pr_number))):
                    raise IntakeRejected("Git delivery conflicts with the existing publication receipt")
                pinned = db.execute(
                    "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?", (run_id,),
                ).fetchone()
                if pinned is not None and pinned["head_sha"] != sha:
                    raise IntakeRejected("Git delivery head already pinned to a different commit")
                rows = db.execute(
                    "SELECT evidence_type,reference,verifier,verified FROM fea_evidence "
                    "WHERE run_id=? AND evidence_type IN ('pr','ci')", (run_id,),
                ).fetchall()
                existing = {(row["evidence_type"], row["reference"]) for row in rows}
                if any(row["verifier"] != "trusted_git" or not row["verified"] for row in rows):
                    raise IntakeRejected("unverified Git evidence cannot be adopted")
                if existing - expected or (current["status"] != "waiting_ci" and existing != expected):
                    raise IntakeRejected("Git delivery evidence is already pinned to another proof set")
                now = int(time.time())
                if pinned is None:
                    db.execute(
                        "INSERT INTO fea_delivery_heads(run_id,head_sha,pinned_at) VALUES (?,?,?)",
                        (run_id, sha, now),
                    )
                for kind, reference in sorted(expected - existing):
                    db.execute(
                        "INSERT INTO fea_evidence "
                        "(run_id,evidence_type,reference,verifier,verified,recorded_at) "
                        "VALUES (?,?,?,'trusted_git',1,?)", (run_id, kind, reference, now),
                    )
                if current["status"] == "waiting_ci":
                    db.execute(
                        "UPDATE fea_runs SET status='waiting_qa',revision=revision+1,updated_at=? "
                        "WHERE run_id=? AND revision=?",
                        (now, run_id, current["revision"]),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
        result = self.snapshot(run_id, event)
        result["pr_state"] = observed["pr_state"]
        result["required_workflows"] = observed["workflows"]
        return result

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
                pinned = db.execute(
                    "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                if pinned is None or pinned["head_sha"] != self._sha(head_sha):
                    raise IntakeRejected("QA head does not match verified PR/CI commit")
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
        with contextlib.closing(self.store._connect()) as db:
            pinned = db.execute(
                "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if pinned is None:
            raise IntakeRejected("PR/CI must share a verified exact head")
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
        if run["mode"] != "edit" or run["status"] != "waiting_qa":
            raise IntakeRejected("engineering delivery requires edited Run awaiting QA")
        with contextlib.closing(self.store._connect()) as db:
            pinned = db.execute(
                "SELECT head_sha FROM fea_delivery_heads WHERE run_id=?",
                (run_id,),
            ).fetchone()
            valid_qa = db.execute(
                "SELECT 1 FROM fea_qa_attestations q "
                "JOIN fea_evidence e ON e.run_id=q.run_id AND "
                "e.evidence_type='qa' AND e.reference=q.evidence_ref "
                "AND e.verifier=q.reviewer AND e.verified=1 "
                "WHERE q.run_id=? AND q.head_sha=? LIMIT 1",
                (run_id, pinned["head_sha"] if pinned else ""),
            ).fetchone()
        if pinned is None or valid_qa is None:
            raise IntakeRejected("matching signed independent QA and head required")
        result = self.store.transition(
            run_id, run["revision"], "completed", event.actor,
        )
        return {"run_id": run_id, "run_status": result["status"],
                "workitem_status": "external_owner_must_accept"}


class ContextDelivery:
    """Read-only proof for the latest actual edit in a live topic.

    No publication, model, source-status change, or simulated QA. Persist only
    exact GitHub evidence after rechecking the local task receipt.
    """
    def __init__(self, config, executor, forge_factory=None):
        self.config, self.executor = config, executor
        self.store = executor.store
        self.forge_factory = forge_factory

    def _local(self, event, result):
        latest = self.executor._latest(result.context_id,result.repo)
        if latest is None or latest["mode"]!="edit" or latest["status"]!="completed":
            raise IntakeRejected("当前话题没有已完成的本地编辑版本")
        row=self.executor.binding(latest["task_id"])
        if (row is None or (row["tenant"],row["chat"],row["actor"],row["topic"],row["repo"])!=
                (event.tenant,event.chat,event.actor,result.topic,result.repo)):
            raise IntakeRejected("交付话题身份不匹配")
        repo=self.config.repositories.get(result.repo)
        if repo is None or not self.config.sender_allowed(event.actor,repo):
            raise IntakeRejected("当前仓库不再授权")
        with self.store._connect() as db:
            local=db.execute("SELECT branch_name,commit_hash,worktree_path FROM task_results WHERE task_id=?",
                             (row["task_id"],)).fetchone()
        if (local is None or not row["branch"] or not row["commit_sha"]
                or local["branch_name"]!=row["branch"] or local["commit_hash"]!=row["commit_sha"]
                or local["worktree_path"]!=row["cwd"]):
            raise IntakeRejected("本地 Git 交付回执不完整或不一致")
        return row,repo

    def verify(self,event,result):
        from .github_adapter import GitHubForge, GitHubTransport
        row,repo=self._local(event,result)
        if not repo.github_repository or not repo.github_required_workflows:
            return "已存在本地提交 "+row["commit_sha"]+"；尚未配置该仓库的 GitHub 必需 CI，不能宣称交付通过。"
        forge=(self.forge_factory(repo) if self.forge_factory else GitHubForge(
            repo.alias,repo.github_repository,
            GitHubTransport(repo.github_repository,self.config.agent_github_read_token),
            repo.github_base_branch))
        observed=forge.discover_delivery(row["branch"],row["commit_sha"],repo.github_required_workflows)
        if (observed.get("repo_alias")!=repo.alias or observed.get("repo_full_name")!=repo.github_repository
                or observed.get("head_sha")!=row["commit_sha"] or observed.get("branch")!=row["branch"]
                or observed.get("base_branch")!=repo.github_base_branch
                or set(observed.get("workflows",{}))!=set(repo.github_required_workflows)
                or type(observed.get("pr_number")) is not int):
            raise IntakeRejected("独立交付观察与实际 Git 版本不一致")
        proof=json.dumps(observed,sort_keys=True,separators=(",",":"))
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            latest=db.execute(
                "SELECT x.task_id,t.status,x.commit_sha,x.branch FROM engineering_context_tasks x "
                "JOIN tasks t ON t.id=x.task_id WHERE x.context_id=? AND t.repository=? ORDER BY x.task_id DESC LIMIT 1",
                (row["context_id"],row["repository"])).fetchone()
            if (latest is None or latest["task_id"]!=row["task_id"] or latest["status"]!="completed"
                    or latest["commit_sha"]!=row["commit_sha"] or latest["branch"]!=row["branch"]):
                raise IntakeRejected("核验期间研发版本发生变化")
            old=db.execute("SELECT head_sha,repository,pr_number FROM engineering_context_delivery WHERE task_id=?",
                           (row["task_id"],)).fetchone()
            if old is not None and (old["head_sha"]!=row["commit_sha"]
                    or old["repository"]!=repo.github_repository or old["pr_number"]!=observed["pr_number"]):
                raise IntakeRejected("交付回执冲突")
            db.execute(
                "INSERT INTO engineering_context_delivery(task_id,head_sha,repository,pr_number,proof_json,verified_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET proof_json=excluded.proof_json,verified_at=excluded.verified_at",
                (row["task_id"],row["commit_sha"],repo.github_repository,observed["pr_number"],proof,int(time.time())))
        return ("已独立核验精确本地提交 "+row["commit_sha"]+" 的 PR 与全部必需 CI。"
                "\nPR：https://github.com/"+repo.github_repository+"/pull/"+str(observed["pr_number"])
                +"\n必需 CI："+str(len(observed["workflows"]))+" 项；等待项目实际测试/QA。原工单未关闭。")

    @staticmethod
    def _joint_snapshot(db,context_id):
        return [dict(row) for row in db.execute(
            "SELECT t.repository,x.task_id,t.mode,t.status,x.commit_sha,x.branch "
            "FROM engineering_context_tasks x JOIN tasks t ON t.id=x.task_id "
            "WHERE x.context_id=? AND x.task_id IN (SELECT MAX(y.task_id) "
            "FROM engineering_context_tasks y JOIN tasks q ON q.id=y.task_id "
            "WHERE y.context_id=? GROUP BY q.repository) ORDER BY t.repository",
            (context_id,context_id))]

    def verify_joint(self,event,result):
        """Refresh participating repositories; CI evidence is not joint product QA."""
        with self.store._connect() as db:
            snapshot=self._joint_snapshot(db,result.context_id)
        if len(snapshot)<2:
            raise IntakeRejected("联合交付至少需要两个实际研发仓库")
        selections=[]
        for item in snapshot:
            selected=dataclasses.replace(result,repo=item["repository"])
            row,repo=self._local(event,selected)
            if (row["task_id"]!=item["task_id"] or row["commit_sha"]!=item["commit_sha"]
                    or not repo.github_repository or not repo.github_required_workflows):
                raise IntakeRejected("联合交付仓库版本或 CI 配置不完整")
            selections.append(selected)
        for selected in selections:
            self.verify(event,selected)
        with self.store._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._joint_snapshot(db,result.context_id)!=snapshot:
                raise IntakeRejected("联合核验期间研发版本发生变化")
            evidence=[]
            for item in snapshot:
                proof=db.execute("SELECT * FROM engineering_context_delivery WHERE task_id=?",
                                 (item["task_id"],)).fetchone()
                repo=self.config.repositories.get(item["repository"])
                if (proof is None or repo is None or not self.config.sender_allowed(event.actor,repo)
                        or proof["head_sha"]!=item["commit_sha"] or proof["repository"]!=repo.github_repository):
                    raise IntakeRejected("联合交付缺少精确仓库证明")
                observed=json.loads(proof["proof_json"])
                if set(observed["workflows"])!=set(repo.github_required_workflows):
                    raise IntakeRejected("联合交付必需 CI 已变化")
                evidence.append({"alias":item["repository"],"task_id":item["task_id"],
                                 "head_sha":item["commit_sha"],"branch":item["branch"],
                                 "repository":proof["repository"],"pr_number":proof["pr_number"],
                                 "workflows":observed["workflows"]})
            heads=json.dumps(snapshot,sort_keys=True,separators=(",",":"))
            digest=hashlib.sha256(heads.encode("utf-8")).hexdigest()
            db.execute("INSERT INTO engineering_context_joint_delivery(context_id,head_set_sha256,proof_json,verified_at) "
                       "VALUES (?,?,?,?) ON CONFLICT(context_id,head_set_sha256) DO UPDATE SET "
                       "proof_json=excluded.proof_json,verified_at=excluded.verified_at",
                       (result.context_id,digest,json.dumps(evidence,sort_keys=True,separators=(",",":")),int(time.time())))
        lines=["联合交付 CI 核验通过（不是跨仓集成测试或产品验收）","版本集合："+digest]
        for proof in evidence:
            lines.append(proof["alias"]+" "+proof["head_sha"]+" PR #"+str(proof["pr_number"]))
        lines.append("待针对上述精确版本集合完成实际跨仓联调及独立 QA；原工单未关闭。")
        return "\n".join(lines)

    def feedback(self,event,result):
        row,repo=self._local(event,result)
        with self.store._connect() as db:
            sources=list(db.execute("SELECT url FROM engineering_context_sources WHERE context_id=? ORDER BY url",
                                    (row["context_id"],)))
            proof=db.execute("SELECT * FROM engineering_context_delivery WHERE task_id=?",(row["task_id"],)).fetchone()
        lines=["研发交付反馈（原工单由业务负责人验收）","仓库："+repo.alias,
               "本地提交："+row["commit_sha"],"分支："+row["branch"]]
        lines.extend("来源："+s["url"] for s in sources)
        if proof is None or proof["head_sha"]!=row["commit_sha"] or proof["repository"]!=repo.github_repository:
            lines.append("PR/CI：尚未独立核验，请在本话题发送“检查 CI”。")
        else:
            observed=json.loads(proof["proof_json"])
            root="https://github.com/"+proof["repository"]
            lines.append("PR："+root+"/pull/"+str(proof["pr_number"]))
            lines.extend("CI："+root+"/actions/runs/"+str(i) for i in observed["workflows"].values())
            lines.append("以上为记录的精确版本核验证据；如代码/CI 变化须重新核验。")
        lines.extend(["独立产品/测试验收：待实际负责人确认。",
                      "未执行原工作项回写、自动关闭、发布或设备烧录。"])
        return "\n".join(lines)
