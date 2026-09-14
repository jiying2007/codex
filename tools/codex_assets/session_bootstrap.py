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
    return json.loads(path.read_text(encoding="utf-8"))


def _git(path: pathlib.Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _canonical_json_sha256(path: pathlib.Path) -> str:
    data = _read_json(path)
    payload = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def build_envelope(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).expanduser().resolve()
    cwd = pathlib.Path(args.cwd).expanduser().resolve()
    contract_path = root / "manifests/session_bootstrap.json"
    binding_path = root / "manifests/integrations/digital-worker-runtime-binding.json"
    provider_lock_path = root / "manifests/provider-locks/agent-dev-kit.json"
    provider_adapter_path = root / "scripts/knowledge-provider.sh"
    for path in (contract_path, binding_path, provider_lock_path, provider_adapter_path):
        if not path.is_file():
            raise BootstrapError(f"required Runtime Binding asset missing: {path}")

    bootstrap_contract = _read_json(contract_path)
    binding = _read_json(binding_path)
    provider_lock = _read_json(provider_lock_path)
    task_package = pathlib.Path(args.engineering_task_package).expanduser().resolve() if args.engineering_task_package else None
    mode = resolve_mode(
        args.mode,
        governed=args.governed,
        formal=args.formal,
        engineering_task_package=task_package,
    )

    if binding.get("status") != "active" or binding.get("readiness") != "SOURCE_SET_BOUND":
        raise BootstrapError("Codex Runtime Binding is not active/SOURCE_SET_BOUND")
    if provider_lock.get("delivery_mode") != "exact-source-set" or provider_lock.get("binding_status") != "source-set-bound":
        raise BootstrapError("ADK provider lock is not exact-source-set/source-set-bound")

    runtime_profile = args.runtime_profile
    if runtime_profile not in {"minimal", "solo-dev", "default", "team-collab"}:
        raise BootstrapError(f"unsupported runtime profile: {runtime_profile}")

    repo_root_raw = _git(cwd, "rev-parse", "--show-toplevel")
    repo_root = pathlib.Path(repo_root_raw).resolve() if repo_root_raw else None
    repo_head = _git(cwd, "rev-parse", "HEAD") if repo_root else None
    codex_commit = _git(root, "rev-parse", "HEAD")

    digital_worker_root = _path_or_default(
        args.digital_worker_root,
        "DIGITAL_WORKER_ROOT",
        pathlib.Path.home() / "digital-worker",
    )
    knowledge_root = _path_or_default(
        args.knowledge_root,
        "KNOWLEDGE_HUB_ROOT",
        pathlib.Path.home() / "knowledge-hub",
    )

    blocked: list[str] = []
    degraded: list[str] = []
    knowledge: dict[str, Any]

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
        if not digital_worker_root.is_dir():
            blocked.append("digital_worker_root_unavailable")
        if not knowledge_root.is_dir():
            blocked.append("knowledge_provider_unavailable")
        knowledge = {
            "mode": "current-provider",
            "root": str(knowledge_root),
            "available": knowledge_root.is_dir(),
            "adapter": str(provider_adapter_path),
        }
    else:
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
            base_commit = args.base_commit
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
    envelope = {
        "kind": bootstrap_contract["output_contract"]["kind"],
        "status": "blocked" if blocked else "ready",
        "mode": mode,
        "mode_name": mode_contract["name"],
        "task": args.task,
        "cwd": str(cwd),
        "target_repository": {
            "root": str(repo_root) if repo_root else None,
            "head": repo_head,
            "base_commit": args.base_commit,
        },
        "digital_worker": {
            "root": str(digital_worker_root),
            "required": mode in {"L1", "L2"},
            "engineering_task_package": str(task_package) if task_package else None,
        },
        "knowledge": knowledge,
        "agent_assets": {
            "provider_repository": provider_lock.get("repository"),
            "release_version": provider_lock.get("version"),
            "release_tag": provider_lock.get("release_tag"),
            "release_commit": provider_lock.get("provider_commit"),
            "asset_profile": provider_lock.get("asset_profile"),
            "delivery_mode": provider_lock.get("delivery_mode"),
            "source_set_identity": provider_lock.get("source_set", {}).get("identity"),
        },
        "runtime_binding": {
            "repository": "jiying2007/codex",
            "commit": codex_commit,
            "target": binding.get("runtime_target"),
            "profile": runtime_profile,
            "readiness": binding.get("readiness"),
            "source_binding": binding.get("source_binding"),
        },
        "routing": {
            "precedence": bootstrap_contract["resolution_precedence"],
            "knowledge_mode": mode_contract["knowledge_mode"],
        },
        "blocked_reasons": blocked,
        "degraded_reasons": degraded,
        "claims": {
            "runtime_local_only": True,
            "domain_verification_owned_by_digital_worker": True,
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
    parser.add_argument("--knowledge-root")
    parser.add_argument("--runtime-profile", default="default")
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
