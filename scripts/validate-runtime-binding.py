#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ADK = ROOT / "manifests/provider-locks/agent-dev-kit.json"
RUNTIME = ROOT / "manifests/execution_policy.json"
HUB = ROOT / "manifests/provider-locks/knowledge-hub.json"
ADAPTER = ROOT / "scripts/knowledge-provider.sh"
PROVIDER_MODULE = ROOT / "tools/codex_assets/knowledge_provider_adapter.py"
AGENTS = ROOT / "AGENTS.md"

ADK_RELEASE = {
    "version": "11.4.17",
    "release_tag": "v11.4.17",
    "provider_commit": "3ab45d2d4d7607f1d6c46c7c6726b8551603a017",
    "provider_tree": "736a9a649d35d0114c196f53640d87b8862522c2",
    "manifest_blob": "c7fb6ad32c5162ab4c4d87e5fcee4ab377c9cfcd",
    "release_artifact_sha256": "93fe08fdd4d9c00d4160377faf4299bdaaad0f73f1e3acdf88881f074499779f"
}
ADK_FIELDS = {
    "schema", "repository", "version", "release_tag", "provider_commit", "provider_tree",
    "manifest_blob", "release_artifact", "asset_profile", "delivery_mode", "binding_status",
    "source_set", "rules",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def exact_sha(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def validate_adk_lock(adk: dict[str, object]) -> None:
    require(set(adk) == ADK_FIELDS, "ADK provider lock must use only terminal v3 fields")
    require(adk["schema"] == "codex-provider-lock/v3", "ADK provider lock schema drift")
    require(adk["repository"] == "jiying2007/agent-dev-kit", "ADK canonical repository required")
    for field in ("version", "release_tag", "provider_commit", "provider_tree", "manifest_blob"):
        require(adk[field] == ADK_RELEASE[field], f"ADK {ADK_RELEASE['version']} exact release identity drift: {field}")
    require(exact_sha(adk["provider_commit"], 40), "ADK provider commit must be exact")
    require(exact_sha(adk["provider_tree"], 40), "ADK provider tree must be exact")
    require(exact_sha(adk["manifest_blob"], 40), "ADK manifest blob must be exact")
    artifact = adk["release_artifact"]
    require(isinstance(artifact, dict) and set(artifact) == {"name", "sha256"}, "ADK release artifact fields drift")
    require(artifact["name"] == f"agent-dev-kit-{ADK_RELEASE['version']}.tar.gz", "ADK release artifact name drift")
    require(artifact["sha256"] == ADK_RELEASE["release_artifact_sha256"], "ADK release artifact digest drift")
    require(adk["asset_profile"] == "embedded-fullstack", "required ADK asset profile drift")
    require(adk["delivery_mode"] == "exact-source-set", "ADK delivery mode drift")
    require(adk["binding_status"] == "source-set-bound", "ADK source-set binding status drift")
    require(adk["source_set"] == {
        "identity": "exact-release-source-blobs",
        "consumer_assembly": "codex-runtime-distribution",
        "required_entry_fields": [
            "version", "vendor_rel", "source_repo", "source_ref", "source_path", "source_blob"
        ],
    }, "ADK source-set declaration drift")
    rules = adk["rules"]
    require(isinstance(rules, dict) and all(value is True for value in rules.values()), "ADK provider rules must fail closed")
    serialized = json.dumps(adk, sort_keys=True)
    for retired in (
        "asset_bundle_hash", "BLOCKED_ASSET_BUNDLE_IDENTITY", "source-integrated-bundle-pending",
        "manifest-first", "5.0.0-rc.2", "llm_agent/agent-dev-kit", "agent_dev_kit-4.0.0",
    ):
        require(retired not in serialized, f"retired ADK compatibility resurfaced: {retired}")


def validate_runtime_source(runtime: dict[str, object]) -> None:
    from tools.codex_assets.execution_policy_adapter import load_runtime_config

    checked = load_runtime_config(ROOT)
    require(runtime == {key: value for key, value in checked.items() if not key.startswith("_")},
            "runtime config validation must use the same canonical source")


def main() -> None:
    for path in [ADK, RUNTIME, HUB, ADAPTER, AGENTS,
                 ROOT / "manifests/session_bootstrap.json"]:
        require(path.is_file(), f"missing runtime binding asset: {path.relative_to(ROOT)}")
    adk = json.loads(ADK.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    hub = json.loads(HUB.read_text(encoding="utf-8"))
    bootstrap = json.loads((ROOT / "manifests/session_bootstrap.json").read_text(encoding="utf-8"))
    require(bootstrap.get("contract_version") == "2.0" and
            set(bootstrap.get("modes", {})) == {"L0", "L1"} and
            bootstrap.get("status") == "active",
            "active bootstrap contract must support L0/L1 only")
    require("digital-worker" not in json.dumps(bootstrap, sort_keys=True).lower() and
            "digital_worker" not in json.dumps(bootstrap, sort_keys=True).lower(),
            "retired Digital Worker must not be an active runtime contract")

    validate_adk_lock(adk)
    validate_runtime_source(runtime)

    require(hub["repository"] == "jiying2007/knowledge-hub", "Knowledge Hub canonical repository required")
    require(re.fullmatch(r"[0-9a-f]{40}", hub["provider_commit"]) is not None, "Hub provider commit must be exact")
    require(hub["rules"]["consumer_must_not_depend_on_provider_internal_temp_paths"] is True,
            "Hub internal paths must not be contract")
    require(hub.get("protocol_version") == 4, "Hub protocol must be v4")
    require(exact_sha(hub.get("source_manifest_sha256"), 64), "Hub executable source manifest must be exact")
    require("tools.codex_assets.knowledge_provider_adapter" in ADAPTER.read_text(encoding="utf-8"),
            "shell must forward to sole adapter module")
    adapter = PROVIDER_MODULE.read_text(encoding="utf-8")
    for token in ["knowledge-provider.sh", "knowledge-evidence-pack.sh",
                  "knowledge-action-check.sh", "knowledge-proposal-route.sh",
                  "knowledge-activity.sh", "BLOCKED", "UNKNOWN", "verify_source"]:
        require(token in adapter, f"adapter missing surface: {token}")
    require(".tmp/activity/receipts" not in adapter, "adapter must not bind Hub internal receipt path")
    require(".tmp/activity/receipts" not in AGENTS.read_text(encoding="utf-8"),
            "AGENTS must not bind Hub internal receipt path")
    print("standalone Codex runtime binding PASS")
    print(f"adk_version={adk['version']}")
    print(f"adk_commit={adk['provider_commit']}")
    print("runtime_readiness=SOURCE_SET_BOUND")
    print("bootstrap_modes=L0,L1")


if __name__ == "__main__":
    main()
