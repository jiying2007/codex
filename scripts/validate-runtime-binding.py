#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "manifests/integrations/digital-worker-runtime-binding.json"
ADK = ROOT / "manifests/provider-locks/agent-dev-kit.json"
RUNTIME = ROOT / "manifests/runtime_control.json"
ENGINE = ROOT / "tools/codex_assets/execution_policy/engine.py"
CONTRACTS = ROOT / "tools/codex_assets/execution_policy/contracts.py"
HUB = ROOT / "manifests/provider-locks/knowledge-hub.json"
RECEIPT_V2 = ROOT / "schemas/runtime-execution-receipt.v2.schema.json"
RECEIPT_V1 = ROOT / "schemas/runtime-execution-receipt.schema.json"
ADAPTER = ROOT / "scripts/knowledge-provider.sh"
AGENTS = ROOT / "AGENTS.md"

ADK_RELEASE = {
    "version": "7.0.4",
    "release_tag": "v7.0.4",
    "provider_commit": "1d6c28e89eb98a4af5ac978707730783f0c84437",
    "provider_tree": "c5b8fa7b11a81597ac2c7cd6fb44d7abf9605137",
    "manifest_blob": "a5e5963545318c4a4498cda0d49d10f08c5f6412",
    "release_artifact_sha256": "497e44ec83d2506c8721019aeca979965127b481203f33387806c51c0d1aff68",
    "engine_blob": "05dd80065ec4c58c342e48ff12d4cd53d3897740",
    "support_blob": "626af591141b2dda6302edbe4363637435066628",
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
        require(adk[field] == ADK_RELEASE[field], f"ADK 7.0.4 exact release identity drift: {field}")
    require(exact_sha(adk["provider_commit"], 40), "ADK provider commit must be exact")
    require(exact_sha(adk["provider_tree"], 40), "ADK provider tree must be exact")
    require(exact_sha(adk["manifest_blob"], 40), "ADK manifest blob must be exact")
    artifact = adk["release_artifact"]
    require(isinstance(artifact, dict) and set(artifact) == {"name", "sha256"}, "ADK release artifact fields drift")
    require(artifact["name"] == "agent-dev-kit-7.0.4.tar.gz", "ADK release artifact name drift")
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
    engine = runtime.get("engine")
    require(isinstance(engine, dict), "runtime engine declaration required")
    baseline = engine.get("behavior_baseline")
    require(baseline == {
        "repository": "jiying2007/agent-dev-kit",
        "version": ADK_RELEASE["version"],
        "commit": ADK_RELEASE["provider_commit"],
        "engine_blob": ADK_RELEASE["engine_blob"],
        "support_blob": ADK_RELEASE["support_blob"],
    }, "runtime behavior baseline must bind exact v7.0.4 canonical execution policy")
    require(ENGINE.is_file() and CONTRACTS.is_file(), "vendored execution policy source missing")
    require(git_blob_sha(ENGINE) == ADK_RELEASE["engine_blob"], "vendored runtime engine != provider canonical blob")
    require(git_blob_sha(CONTRACTS) == ADK_RELEASE["support_blob"], "vendored runtime contracts != provider canonical blob")


def validate_receipt_v2(receipt: dict[str, object], binding: dict[str, object]) -> None:
    contract = binding.get("execution_receipt_contract")
    require(contract == {
        "schema": "schemas/runtime-execution-receipt.v2.schema.json",
        "schema_version": 2,
        "identity_model": "execution-source-set-bound",
        "legacy_v1_schema": "schemas/runtime-execution-receipt.schema.json",
        "legacy_v1_status": "historical-read-only",
    }, "runtime execution receipt contract drift")
    require(receipt.get("additionalProperties") is False, "receipt v2 must be closed schema")
    required = receipt.get("required")
    require(isinstance(required, list), "receipt v2 required fields missing")
    for field in ("execution_source_set_identity", "digital_worker_governance_identity", "runtime_binding", "agent_assets"):
        require(field in required, f"receipt v2 must require {field}")
    props = receipt.get("properties")
    require(isinstance(props, dict), "receipt v2 properties missing")
    require("asset_bundle_hash" not in json.dumps(props, sort_keys=True), "receipt v2 must not use retired asset_bundle_hash")
    text = RECEIPT_V2.read_text(encoding="utf-8")
    for forbidden_claim in ("verification_pass", "release_ready", "domain_gate_pass"):
        require(forbidden_claim in text, f"receipt v2 must explicitly forbid {forbidden_claim}")


def main() -> None:
    for path in [BINDING, ADK, RUNTIME, ENGINE, CONTRACTS, HUB, RECEIPT_V2, RECEIPT_V1, ADAPTER, AGENTS]:
        require(path.is_file(), f"missing runtime binding asset: {path.relative_to(ROOT)}")
    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    adk = json.loads(ADK.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    hub = json.loads(HUB.read_text(encoding="utf-8"))
    receipt_v2 = json.loads(RECEIPT_V2.read_text(encoding="utf-8"))

    require(binding["schema_version"] == 2 and binding["contract_version"] == "2.1", "Codex runtime binding schema drift")
    require(binding["status"] == "active", "Codex runtime binding must be active")
    require(binding["role"] == "codex-runtime-distribution-and-host-integration", "Codex role drift")
    require(binding["runtime_target"] == "codex-cli", "runtime target drift")
    require(binding["source_binding"] == {
        "provider_repository": "jiying2007/agent-dev-kit",
        "release_version": ADK_RELEASE["version"],
        "provider_commit": ADK_RELEASE["provider_commit"],
        "asset_profile": "embedded-fullstack",
        "identity_mode": "exact-release-source-blobs",
    }, "runtime source binding drift")
    require(binding["readiness"] == "SOURCE_SET_BOUND", "runtime source binding readiness drift")
    require(binding["gate_semantics"]["runtime_success_implies_domain_verification_pass"] is False, "runtime must not claim domain PASS")
    require(binding["gate_semantics"]["runtime_release_gate_implies_product_release_readiness"] is False, "runtime must not claim product release readiness")
    require("cross_runtime_effectiveness_evaluation" in binding["must_not_own"], "cross-runtime eval must remain outside Codex binding")

    validate_adk_lock(adk)
    validate_runtime_source(runtime)
    validate_receipt_v2(receipt_v2, binding)

    require(hub["repository"] == "jiying2007/knowledge-hub", "Knowledge Hub canonical repository required")
    require(re.fullmatch(r"[0-9a-f]{40}", hub["provider_commit"]) is not None, "Hub provider commit must be exact")
    require(hub["rules"]["consumer_must_not_depend_on_provider_internal_temp_paths"] is True, "Hub internal paths must not be contract")
    adapter = ADAPTER.read_text(encoding="utf-8")
    for token in ["knowledge-context.sh", "knowledge-evidence-pack.sh", "knowledge-action-check.sh", "knowledge-proposal-route.sh", "knowledge-activity.sh", "BLOCKED"]:
        require(token in adapter, f"adapter missing surface: {token}")
    require(".tmp/activity/receipts" not in adapter, "adapter must not bind Hub internal receipt path")
    require(".tmp/activity/receipts" not in AGENTS.read_text(encoding="utf-8"), "AGENTS must not bind Hub internal receipt path")

    print("runtime binding validation PASS")
    print(f"adk_version={adk['version']}")
    print(f"adk_commit={adk['provider_commit']}")
    print(f"runtime_engine_blob={ADK_RELEASE['engine_blob']}")
    print(f"runtime_support_blob={ADK_RELEASE['support_blob']}")
    print(f"runtime_readiness={binding['readiness']}")


if __name__ == "__main__":
    main()
