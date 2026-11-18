from __future__ import annotations

"""Daily Codex session bootstrap for independent L0/L1 engineering tasks.

The former Digital Worker formal-evidence mode is deliberately not exposed.
Unknown modes and former formal CLI flags fail; they never fall back to L0/L1.
This assembles references only, not model execution or engineering acceptance.
"""

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

if not __package__:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


class BootstrapError(RuntimeError):
    pass


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BootstrapError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BootstrapError(f"JSON object required: {path}")
    return data


def _git(path: pathlib.Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def resolve_mode(explicit_mode: str, *, governed: bool) -> str:
    explicit = explicit_mode.upper()
    if explicit not in {"AUTO", "L0", "L1"}:
        raise BootstrapError(f"unsupported session mode: {explicit_mode}; only L0/L1 are available")
    if explicit == "L0" and governed:
        raise BootstrapError("--governed conflicts with explicit L0 mode")
    if explicit != "AUTO":
        return explicit
    return "L1" if governed else "L0"


def _path_or_default(value: str | None, key: str, default: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(value or os.environ.get(key) or str(default)).expanduser().resolve()


def _identity(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def build_envelope(args: argparse.Namespace) -> dict[str, Any]:
    root = pathlib.Path(args.root).expanduser().resolve()
    cwd = pathlib.Path(args.cwd).expanduser().resolve()
    contract_path = root / "manifests/session_bootstrap.json"
    provider_lock_path = root / "manifests/provider-locks/agent-dev-kit.json"
    provider_adapter_path = root / "scripts/knowledge-provider.sh"
    for path in (contract_path, provider_lock_path, provider_adapter_path):
        if not path.is_file():
            raise BootstrapError(f"required Runtime Binding asset missing: {path}")

    contract = _read_json(contract_path)
    provider = _read_json(provider_lock_path)
    mode = resolve_mode(args.mode, governed=args.governed)
    if (contract.get("contract_version") != "2.0" or
        set(contract.get("modes", {})) != {"L0", "L1"} or
        contract.get("status") != "active"):
        raise BootstrapError("daily-only bootstrap contract is invalid or obsolete")
    if (provider.get("delivery_mode") != "exact-source-set" or
        provider.get("binding_status") != "source-set-bound"):
        raise BootstrapError("ADK provider lock is not exact-source-set/source-set-bound")
    if args.runtime_profile not in {"minimal", "solo-dev", "default", "team-collab"}:
        raise BootstrapError(f"unsupported runtime profile: {args.runtime_profile}")

    repo_root_raw = _git(cwd, "rev-parse", "--show-toplevel")
    repo_root = pathlib.Path(repo_root_raw).resolve() if repo_root_raw else None
    repo_head = _git(cwd, "rev-parse", "HEAD") if repo_root else None
    knowledge_root = _path_or_default(
        args.knowledge_root,
        "KNOWLEDGE_HUB_ROOT",
        pathlib.Path.home() / "knowledge-hub",
    )
    knowledge = {
        "mode": "current-provider",
        "root": str(knowledge_root),
        "available": knowledge_root.is_dir(),
        "adapter": str(provider_adapter_path),
    }
    blocked: list[str] = []
    degraded: list[str] = []
    if not knowledge_root.is_dir():
        (degraded if mode == "L0" else blocked).append("knowledge_provider_unavailable")
    else:
        from tools.codex_assets.knowledge_provider_adapter import ProviderAdapterError, verify_source
        try:
            knowledge["execution_identity"] = verify_source(root, knowledge_root)
            knowledge["execution_identity_verified"] = True
        except ProviderAdapterError:
            knowledge["execution_identity_verified"] = False
            (degraded if mode == "L0" else blocked).append("knowledge_provider_source_drift")

    assets = {
        "provider_repository": provider.get("repository"),
        "release_version": provider.get("version"),
        "release_tag": provider.get("release_tag"),
        "release_commit": provider.get("provider_commit"),
        "asset_profile": provider.get("asset_profile"),
        "delivery_mode": provider.get("delivery_mode"),
        "source_set_identity": provider.get("source_set", {}).get("identity"),
    }
    binding = {
        "repository": "jiying2007/codex",
        "commit": _git(root, "rev-parse", "HEAD"),
        "target": contract["runtime_binding"],
        "profile": args.runtime_profile,
        "readiness": "SOURCE_SET_BOUND",
        "source_binding": {
            "provider_repository": provider.get("repository"),
            "release_version": provider.get("version"),
            "provider_commit": provider.get("provider_commit"),
            "asset_profile": provider.get("asset_profile"),
            "identity_mode": provider.get("source_set", {}).get("identity"),
        },
    }
    return {
        "kind": contract["output_contract"]["kind"],
        "status": "blocked" if blocked else "ready",
        "mode": mode,
        "mode_name": contract["modes"][mode]["name"],
        "task": args.task,
        "cwd": str(cwd),
        "session_bootstrap_identity": _identity({
            "mode": mode,
            "task": args.task,
            "cwd": str(cwd),
            "runtime_profile": args.runtime_profile,
            "source_identity": binding["source_binding"],
        }),
        "target_repository": {
            "root": str(repo_root) if repo_root else None,
            "head": repo_head,
            "base_commit": args.base_commit,
        },
        "knowledge": knowledge,
        "agent_assets": assets,
        "runtime_binding": binding,
        "routing": {
            "precedence": contract["resolution_precedence"],
            "knowledge_mode": contract["modes"][mode]["knowledge_mode"],
        },
        "blocked_reasons": blocked,
        "degraded_reasons": degraded,
        "claims": {
            "runtime_local_only": True,
            "project_acceptance_owned_by_project": True,
            "knowledge_lifecycle_owned_by_provider": True,
        },
    }


def configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve current standalone L0/L1 Codex session bootstrap.")
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[2]))
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--task", default="")
    parser.add_argument("--mode", default="auto", choices=["auto", "L0", "L1"])
    parser.add_argument("--governed", action="store_true")
    parser.add_argument("--base-commit")
    parser.add_argument("--knowledge-root")
    parser.add_argument("--runtime-profile", default="default")
    parser.add_argument("--summary-json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = configure_parser().parse_args(argv)
    try:
        envelope = build_envelope(args)
    except BootstrapError as exc:
        print(json.dumps(
            {"kind": "codex-session-bootstrap/v2", "status": "blocked", "reason": str(exc)},
            ensure_ascii=False, separators=(",", ":") if args.summary_json else None,
            indent=None if args.summary_json else 2,
        ))
        return 2
    print(json.dumps(
        envelope, ensure_ascii=False, sort_keys=True,
        separators=(",", ":") if args.summary_json else None,
        indent=None if args.summary_json else 2,
    ))
    return 2 if envelope["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
