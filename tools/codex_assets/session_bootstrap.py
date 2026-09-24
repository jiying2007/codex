from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
from typing import Any


class BootstrapError(RuntimeError):
    pass


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BootstrapError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BootstrapError(f"JSON object required: {path}")
    return value


def _git(path: pathlib.Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _canonical_value_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_sha256(path: pathlib.Path) -> str:
    return _canonical_value_sha256(_read_json(path))


def resolve_mode(
    explicit_mode: str,
    *,
    governed: bool,
    formal: bool,
    engineering_task_package: pathlib.Path | None,
) -> str:
    explicit = explicit_mode.upper()
    if explicit not in {"AUTO", "L0", "L1", "L2"}:
        raise BootstrapError(f"invalid mode: {explicit_mode}")

    if explicit != "AUTO":
        if formal and explicit != "L2":
            raise BootstrapError("--formal conflicts with explicit non-L2 mode")
        if governed and explicit == "L0":
            raise BootstrapError("--governed conflicts with explicit L0 mode")
        if engineering_task_package is not None and explicit != "L2":
            raise BootstrapError("engineering task package conflicts with explicit non-L2 mode")
        return explicit

    if formal or engineering_task_package is not None:
        return "L2"
    if governed:
        return "L1"
    return "L0"


def _path_or_default(value: str | None, env_key: str, default: pathlib.Path) -> pathlib.Path:
    raw = value or os.environ.get(env_key) or str(default)
    return pathlib.Path(raw).expanduser().resolve()


def _require_full_sha(value: str | None, name: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", value or "") is None:
        raise BootstrapError(f"{name} must be a full 40-hex commit SHA")
    return value or ""


def _require_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BootstrapError(f"{name} must be a non-empty string")
    return value.strip()


def _normalize_repo_ref(value: str, name: str) -> str:
    candidate = pathlib.PurePosixPath(value)
    if candidate.is_absolute() or not value or ".." in candidate.parts:
        raise BootstrapError(f"{name} must be a safe repository-relative path: {value}")
    return candidate.as_posix()


def _validate_tracked_clean_refs(
    root: pathlib.Path,
    refs: list[str],
    *,
    category: str,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in refs:
        ref = _normalize_repo_ref(raw, category)
        if ref in seen:
            continue
        seen.add(ref)
        path = root / ref
        if not path.is_file():
            raise BootstrapError(f"{category} missing: {ref}")
        if _git(root, "ls-files", "--error-unmatch", "--", ref) is None:
            raise BootstrapError(f"{category} is not git-tracked: {ref}")
        normalized.append(ref)
    if normalized:
        dirty = _git(root, "status", "--porcelain", "--", *normalized)
        if dirty:
            raise BootstrapError(f"{category} refs must match the exact digital-worker checkout")
    return normalized


def _validate_formal_digital_worker_identity(
    digital_worker_root: pathlib.Path,
    *,
    domain_refs: list[str],
    routing_refs: list[str],
    skill_refs: list[str],
) -> dict[str, Any]:
    if not digital_worker_root.is_dir():
        raise BootstrapError(f"digital-worker root missing: {digital_worker_root}")
    commit = _require_full_sha(_git(digital_worker_root, "rev-parse", "HEAD"), "digital-worker provider commit")

    catalog_ref = "contracts/catalog.json"
    catalog_path = digital_worker_root / catalog_ref
    if not catalog_path.is_file():
        raise BootstrapError(f"digital-worker contract catalog missing: {catalog_path}")
    if _git(digital_worker_root, "ls-files", "--error-unmatch", "--", catalog_ref) is None:
        raise BootstrapError("digital-worker contract catalog must be git-tracked")

    selected_domains = _validate_tracked_clean_refs(
        digital_worker_root,
        domain_refs,
        category="digital-worker domain ref",
    )
    selected_routing = _validate_tracked_clean_refs(
        digital_worker_root,
        routing_refs,
        category="digital-worker routing ref",
    )
    selected_skills = _validate_tracked_clean_refs(
        digital_worker_root,
        skill_refs,
        category="digital-worker skill ref",
    )
    if not selected_domains:
        raise BootstrapError("L2 requires at least one explicit digital-worker domain ref")
    if not selected_routing:
        raise BootstrapError("L2 requires at least one explicit digital-worker routing ref")

    dirty_catalog = _git(digital_worker_root, "status", "--porcelain", "--", catalog_ref)
    if dirty_catalog:
        raise BootstrapError("digital-worker contract catalog must match the exact checkout")

    identity = {
        "provider": "digital-worker",
        "repository": "jiying2007/digital-worker",
        "provider_commit": commit,
        "contract_catalog_ref": catalog_ref,
        "contract_catalog_digest": _canonical_json_sha256(catalog_path),
        "selected_domain_refs": selected_domains,
        "selected_routing_refs": selected_routing,
        "materially_used_domain_skills": selected_skills,
    }
    identity["identity_digest"] = _canonical_value_sha256(identity)
    return identity


def _validate_formal_engineering_identity(
    engineering_task_package: pathlib.Path,
    requested_base_commit: str,
) -> dict[str, Any]:
    try:
        package = _read_json(engineering_task_package)
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"cannot read engineering task package: {exc}") from exc

    package_id = _require_nonempty_string(package.get("package_id"), "engineering task package package_id")
    work_item_id = _require_nonempty_string(package.get("work_item_id"), "engineering task package work_item_id")
    run_id = _require_nonempty_string(package.get("run_id"), "engineering task package run_id")
    repo_root = _require_nonempty_string(package.get("repo_root"), "engineering task package repo_root")
    package_base_commit = _require_full_sha(package.get("base_commit"), "engineering task package base_commit")
    if package_base_commit != requested_base_commit:
        raise BootstrapError(
            "engineering task package base_commit mismatch: "
            f"requested={requested_base_commit} package={package_base_commit}"
        )

    return {
        "package_id": package_id,
        "work_item_id": work_item_id,
        "run_id": run_id,
        "repo_root": repo_root,
        "base_commit": package_base_commit,
        "engineering_task_package_ref": str(engineering_task_package),
        "engineering_task_package_sha256": hashlib.sha256(engineering_task_package.read_bytes()).hexdigest(),
    }


def _validate_formal_knowledge_identity(
    digital_worker_root: pathlib.Path,
    knowledge_root: pathlib.Path,
) -> dict[str, Any]:
    lock_path = digital_worker_root / "config/integrations/cross-repo-lock.json"
    if not lock_path.is_file():
        raise BootstrapError(f"digital-worker cross-repo lock missing: {lock_path}")
    lock = _read_json(lock_path)
    provider = lock.get("providers", {}).get("knowledge_control_plane", {})
    expected_commit = _require_full_sha(provider.get("commit"), "knowledge provider commit")
    contract_rel = provider.get("contract")
    expected_digest = provider.get("contract_canonical_sha256")
    if not isinstance(contract_rel, str) or not contract_rel:
        raise BootstrapError("knowledge provider contract path missing from digital-worker lock")
    if re.fullmatch(r"[0-9a-f]{64}", expected_digest or "") is None:
        raise BootstrapError("knowledge provider contract digest missing from digital-worker lock")
    if not knowledge_root.is_dir():
        raise BootstrapError(f"knowledge provider root missing: {knowledge_root}")
    actual_commit = _git(knowledge_root, "rev-parse", "HEAD")
    if actual_commit != expected_commit:
        raise BootstrapError(
            f"knowledge provider checkout mismatch: expected={expected_commit} actual={actual_commit or 'unavailable'}"
        )
    contract_path = knowledge_root / contract_rel
    if not contract_path.is_file():
        raise BootstrapError(f"knowledge provider contract missing: {contract_path}")
    actual_digest = _canonical_json_sha256(contract_path)
    if actual_digest != expected_digest:
        raise BootstrapError(
            f"knowledge provider contract digest mismatch: expected={expected_digest} actual={actual_digest}"
        )
    return {
        "mode": "exact-pinned-provider",
        "root": str(knowledge_root),
        "commit": actual_commit,
        "contract": contract_rel,
        "contract_canonical_sha256": actual_digest,
    }


def _load_prior_bootstrap(path_value: str | None) -> tuple[pathlib.Path | None, dict[str, Any] | None]:
    if not path_value:
        return None, None
    path = pathlib.Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise BootstrapError(f"prior session bootstrap missing: {path}")
    prior = _read_json(path)
    if prior.get("kind") != "codex-session-bootstrap/v1":
        raise BootstrapError("prior session bootstrap has incompatible kind")
    if prior.get("status") != "ready":
        raise BootstrapError("prior session bootstrap is not ready")
    return path, prior


def _formal_execution_source_set(
    *,
    digital_worker: dict[str, Any],
    knowledge: dict[str, Any],
    agent_assets: dict[str, Any],
    runtime_binding: dict[str, Any],
    engineering: dict[str, Any],
) -> dict[str, Any]:
    materials = {
        "digital_worker_governance": {
            key: digital_worker[key]
            for key in (
                "repository",
                "provider_commit",
                "contract_catalog_ref",
                "contract_catalog_digest",
                "selected_domain_refs",
                "selected_routing_refs",
                "materially_used_domain_skills",
                "identity_digest",
            )
        },
        "knowledge_provider": {
            "commit": knowledge.get("commit"),
            "contract": knowledge.get("contract"),
            "contract_canonical_sha256": knowledge.get("contract_canonical_sha256"),
        },
        "agent_assets": {
            "provider_repository": agent_assets.get("provider_repository"),
            "release_version": agent_assets.get("release_version"),
            "release_tag": agent_assets.get("release_tag"),
            "release_commit": agent_assets.get("release_commit"),
            "asset_profile": agent_assets.get("asset_profile"),
            "source_set_identity": agent_assets.get("source_set_identity"),
        },
        "runtime_binding": {
            "repository": runtime_binding.get("repository"),
            "commit": runtime_binding.get("commit"),
            "target": runtime_binding.get("target"),
            "profile": runtime_binding.get("profile"),
            "source_binding": runtime_binding.get("source_binding"),
        },
        "engineering": engineering,
    }
    return {
        "kind": "codex-execution-source-set/v1",
        "identity": f"sha256:{_canonical_value_sha256(materials)}",
        "materials": materials,
    }


def _session_bootstrap_identity(
    *,
    mode: str,
    task: str,
    cwd: pathlib.Path,
    runtime_profile: str,
    execution_source_set_identity: str | None,
    prior_session_identity: str | None,
) -> str:
    material = {
        "mode": mode,
        "task": task,
        "cwd": str(cwd),
        "runtime_profile": runtime_profile,
        "execution_source_set_identity": execution_source_set_identity,
        "prior_session_identity": prior_session_identity,
    }
    return f"sha256:{_canonical_value_sha256(material)}"


def build_envelope(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).expanduser().resolve()
    cwd = pathlib.Path(args.cwd).expanduser().resolve()
    contract_path = root / "manifests/session_bootstrap.json"
    binding_path = root / "manifests/integrations/digital-worker-runtime-binding.json"
    provider_lock_path = root / "manifests/provider-locks/agent-dev-kit.json"
    provider_adapter_path = root / "scripts/knowledge-provider.sh"
    for path in (contract_path, provider_lock_path, provider_adapter_path):
        if not path.is_file():
            raise BootstrapError(f"required Runtime Binding asset missing: {path}")

    bootstrap_contract = _read_json(contract_path)
    provider_lock = _read_json(provider_lock_path)
    task_package = pathlib.Path(args.engineering_task_package).expanduser().resolve() if args.engineering_task_package else None
    mode = resolve_mode(
        args.mode,
        governed=args.governed,
        formal=args.formal,
        engineering_task_package=task_package,
    )

    if provider_lock.get("delivery_mode") != "exact-source-set" or provider_lock.get("binding_status") != "source-set-bound":
        raise BootstrapError("ADK provider lock is not exact-source-set/source-set-bound")

    # Daily runtime identity is a projection of the existing ADK lock, not a
    # dependency on the optional Digital Worker integration or another SSOT.
    binding = {
        "runtime_target": bootstrap_contract["runtime_binding"],
        "readiness": "SOURCE_SET_BOUND",
        "source_binding": {
            "provider_repository": provider_lock.get("repository"),
            "release_version": provider_lock.get("version"),
            "provider_commit": provider_lock.get("provider_commit"),
            "asset_profile": provider_lock.get("asset_profile"),
            "identity_mode": provider_lock.get("source_set", {}).get("identity"),
        },
    }
    if mode == "L2":
        if not binding_path.is_file():
            raise BootstrapError(f"required formal Runtime Binding asset missing: {binding_path}")
        binding = _read_json(binding_path)
        if binding.get("status") != "active" or binding.get("readiness") != "SOURCE_SET_BOUND":
            raise BootstrapError("Codex Runtime Binding is not active/SOURCE_SET_BOUND")

    runtime_profile = args.runtime_profile
    if runtime_profile not in {"minimal", "solo-dev", "default", "team-collab"}:
        raise BootstrapError(f"unsupported runtime profile: {runtime_profile}")

    repo_root_raw = _git(cwd, "rev-parse", "--show-toplevel")
    repo_root = pathlib.Path(repo_root_raw).resolve() if repo_root_raw else None
    repo_head = _git(cwd, "rev-parse", "HEAD") if repo_root else None
    codex_commit = _git(root, "rev-parse", "HEAD")

    digital_worker_root = (
        _path_or_default(
            args.digital_worker_root,
            "DIGITAL_WORKER_ROOT",
            pathlib.Path.home() / "digital-worker",
        )
        if mode == "L2" else None
    )
    knowledge_root = _path_or_default(
        args.knowledge_root,
        "KNOWLEDGE_HUB_ROOT",
        pathlib.Path.home() / "knowledge-hub",
    )

    blocked: list[str] = []
    degraded: list[str] = []
    knowledge: dict[str, Any]
    digital_worker_governance: dict[str, Any] | None = None
    engineering_identity: dict[str, Any] | None = None
    prior_path: pathlib.Path | None = None
    prior_bootstrap: dict[str, Any] | None = None

    try:
        prior_path, prior_bootstrap = _load_prior_bootstrap(args.prior_session_bootstrap)
    except BootstrapError as exc:
        blocked.append(str(exc))

    if args.escalate_from_l1 and prior_bootstrap is None:
        blocked.append("L1 to L2 escalation requires --prior-session-bootstrap")
    if args.escalate_from_l1 and mode != "L2":
        blocked.append("--escalate-from-l1 requires L2 mode")
    if prior_bootstrap is not None and mode == "L2" and prior_bootstrap.get("mode") != "L1":
        blocked.append("L2 prior session bootstrap must be L1 for governed escalation")

    if mode == "L0":
        knowledge = {
            "mode": "current-provider",
            "root": str(knowledge_root),
            "available": knowledge_root.is_dir(),
            "adapter": str(provider_adapter_path),
        }
        if not knowledge_root.is_dir():
            degraded.append("knowledge_provider_unavailable")
    elif mode == "L1":
        if not knowledge_root.is_dir():
            blocked.append("knowledge_provider_unavailable")
        knowledge = {
            "mode": "current-provider",
            "root": str(knowledge_root),
            "available": knowledge_root.is_dir(),
            "adapter": str(provider_adapter_path),
        }
    else:
        assert digital_worker_root is not None
        if task_package is None or not task_package.is_file():
            blocked.append("engineering_task_package_missing")
        if not digital_worker_root.is_dir():
            blocked.append("digital_worker_root_unavailable")
        if not knowledge_root.is_dir():
            blocked.append("knowledge_provider_unavailable")
        try:
            base_commit = _require_full_sha(args.base_commit, "base_commit")
        except BootstrapError as exc:
            blocked.append(str(exc))
            base_commit = args.base_commit or ""

        if task_package is not None and task_package.is_file() and re.fullmatch(r"[0-9a-f]{40}", base_commit):
            try:
                engineering_identity = _validate_formal_engineering_identity(task_package, base_commit)
            except BootstrapError as exc:
                blocked.append(str(exc))

        if digital_worker_root.is_dir():
            try:
                digital_worker_governance = _validate_formal_digital_worker_identity(
                    digital_worker_root,
                    domain_refs=args.digital_worker_domain_ref,
                    routing_refs=args.digital_worker_routing_ref,
                    skill_refs=args.digital_worker_skill_ref,
                )
            except BootstrapError as exc:
                blocked.append(str(exc))

        if blocked:
            knowledge = {
                "mode": "exact-pinned-provider",
                "root": str(knowledge_root),
                "available": knowledge_root.is_dir(),
                "adapter": str(provider_adapter_path),
            }
        else:
            try:
                knowledge = _validate_formal_knowledge_identity(digital_worker_root, knowledge_root)
                knowledge["adapter"] = str(provider_adapter_path)
            except BootstrapError as exc:
                blocked.append(str(exc))
                knowledge = {
                    "mode": "exact-pinned-provider",
                    "root": str(knowledge_root),
                    "available": knowledge_root.is_dir(),
                    "adapter": str(provider_adapter_path),
                }

    mode_contract = bootstrap_contract["modes"][mode]
    agent_assets = {
        "provider_repository": provider_lock.get("repository"),
        "release_version": provider_lock.get("version"),
        "release_tag": provider_lock.get("release_tag"),
        "release_commit": provider_lock.get("provider_commit"),
        "asset_profile": provider_lock.get("asset_profile"),
        "delivery_mode": provider_lock.get("delivery_mode"),
        "source_set_identity": provider_lock.get("source_set", {}).get("identity"),
    }
    runtime_binding = {
        "repository": "jiying2007/codex",
        "commit": codex_commit,
        "target": binding.get("runtime_target"),
        "profile": runtime_profile,
        "readiness": binding.get("readiness"),
        "source_binding": binding.get("source_binding"),
    }

    execution_source_set: dict[str, Any] | None = None
    if (
        mode == "L2"
        and not blocked
        and digital_worker_governance is not None
        and engineering_identity is not None
    ):
        execution_source_set = _formal_execution_source_set(
            digital_worker=digital_worker_governance,
            knowledge=knowledge,
            agent_assets=agent_assets,
            runtime_binding=runtime_binding,
            engineering=engineering_identity,
        )

    work_identity = None
    if engineering_identity is not None:
        work_identity = {
            "work_item_id": engineering_identity["work_item_id"],
            "run_id": engineering_identity["run_id"],
            "engineering_package_id": engineering_identity["package_id"],
        }

    prior_session_identity = prior_bootstrap.get("session_bootstrap_identity") if prior_bootstrap else None
    session_identity = _session_bootstrap_identity(
        mode=mode,
        task=args.task,
        cwd=cwd,
        runtime_profile=runtime_profile,
        execution_source_set_identity=execution_source_set.get("identity") if execution_source_set else None,
        prior_session_identity=prior_session_identity,
    )

    governance_escalation: dict[str, Any] | None = None
    if mode == "L2" and prior_bootstrap is not None:
        if prior_session_identity == session_identity:
            blocked.append("L1 to L2 escalation must create a new session bootstrap identity")
        prior_source_set = prior_bootstrap.get("execution_source_set") or {}
        if execution_source_set is not None and prior_source_set.get("identity") == execution_source_set.get("identity"):
            blocked.append("L1 to L2 escalation must freeze a new Execution Source Set")
        governance_escalation = {
            "from_level": "L1",
            "to_level": "L2",
            "escalation_reason": "formal-evidence",
            "prior_context_disposition": "provisional-not-promoted",
            "prior_session_bootstrap_ref": str(prior_path),
            "prior_session_bootstrap_identity": prior_session_identity,
            "new_execution_source_set_ref": execution_source_set.get("identity") if execution_source_set else None,
            "new_session_bootstrap_ref": session_identity,
            "formal_evidence_start_ref": session_identity,
        }

    envelope = {
        "kind": bootstrap_contract["output_contract"]["kind"],
        "status": "blocked" if blocked else "ready",
        "mode": mode,
        "mode_name": mode_contract["name"],
        "task": args.task,
        "cwd": str(cwd),
        "session_bootstrap_identity": session_identity,
        "work_identity": work_identity,
        "target_repository": {
            "root": str(repo_root) if repo_root else None,
            "head": repo_head,
            "base_commit": args.base_commit,
        },
        "digital_worker": {
            "root": str(digital_worker_root) if digital_worker_root is not None else None,
            "required": mode == "L2",
            "engineering_task_package": str(task_package) if task_package else None,
            "governance_identity": digital_worker_governance,
        },
        "knowledge": knowledge,
        "agent_assets": agent_assets,
        "runtime_binding": runtime_binding,
        "execution_source_set": execution_source_set,
        "governance_escalation": governance_escalation,
        "routing": {
            "precedence": bootstrap_contract["resolution_precedence"],
            "knowledge_mode": mode_contract["knowledge_mode"],
        },
        "blocked_reasons": blocked,
        "degraded_reasons": degraded,
        "claims": {
            "runtime_local_only": True,
            "domain_verification_owned_by_digital_worker": mode == "L2",
            "project_acceptance_owned_by_project": True,
            "knowledge_lifecycle_owned_by_provider": True,
        },
    }
    serialized = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
    for forbidden in bootstrap_contract["output_contract"]["forbidden_claims"]:
        if f'"{forbidden}"' in serialized:
            raise BootstrapError(f"forbidden domain/product claim leaked into session envelope: {forbidden}")
    return envelope


def configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve the thin Codex session bootstrap mode and identity envelope.")
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[2]))
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--task", default="")
    parser.add_argument("--mode", default="auto", choices=["auto", "L0", "L1", "L2"])
    parser.add_argument("--governed", action="store_true")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--engineering-task-package")
    parser.add_argument("--base-commit")
    parser.add_argument("--digital-worker-root")
    parser.add_argument("--digital-worker-domain-ref", action="append", default=[])
    parser.add_argument("--digital-worker-routing-ref", action="append", default=[])
    parser.add_argument("--digital-worker-skill-ref", action="append", default=[])
    parser.add_argument("--knowledge-root")
    parser.add_argument("--runtime-profile", default="default")
    parser.add_argument("--prior-session-bootstrap")
    parser.add_argument("--escalate-from-l1", action="store_true")
    parser.add_argument("--summary-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = configure_parser()
    args = parser.parse_args(argv)
    try:
        envelope = build_envelope(args)
    except BootstrapError as exc:
        payload = {
            "kind": "codex-session-bootstrap/v1",
            "status": "blocked",
            "reason": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.summary_json else None, indent=None if args.summary_json else 2))
        return 2

    print(
        json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if args.summary_json else None,
            indent=None if args.summary_json else 2,
        )
    )
    return 2 if envelope["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
