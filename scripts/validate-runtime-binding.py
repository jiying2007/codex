#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINDING = ROOT / "manifests/integrations/digital-worker-runtime-binding.json"
ADK = ROOT / "manifests/provider-locks/agent-dev-kit.json"
HUB = ROOT / "manifests/provider-locks/knowledge-hub.json"
RECEIPT = ROOT / "schemas/runtime-execution-receipt.schema.json"
ADAPTER = ROOT / "scripts/knowledge-provider.sh"
AGENTS = ROOT / "AGENTS.md"

ADK_RELEASE = {
    "version": "5.1.0",
    "release_tag": "v5.1.0",
    "provider_commit": "59cbd5cb40ca7077ee5407636bfc617e295ec7e5",
    "provider_tree": "16d3c99d4dac8c41c09509b82c536a11cc058ca9",
    "manifest_blob": "bc349b0dc003c553059cdddbc368ae8ea6ffda89",
    "release_artifact_sha256": "d4684fe5888203b4a25e7dda9ab51b83fb900cae2d09adb6e5179a775748c965",
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


def validate_adk_lock(adk: dict[str, object]) -> None:
    require(set(adk) == ADK_FIELDS, "ADK provider lock must use only the terminal v3 fields")
    require(adk["schema"] == "codex-provider-lock/v3", "ADK provider lock schema drift")
    require(adk["repository"] == "jiying2007/agent-dev-kit", "ADK canonical repository required")
    for field in ("version", "release_tag", "provider_commit", "provider_tree", "manifest_blob"):
        require(adk[field] == ADK_RELEASE[field], f"ADK exact release identity drift: {field}")
    require(exact_sha(adk["provider_commit"], 40), "ADK provider commit must be exact")
    require(exact_sha(adk["provider_tree"], 40), "ADK provider tree must be exact")
    require(exact_sha(adk["manifest_blob"], 40), "ADK manifest blob must be exact")

    artifact = adk["release_artifact"]
    require(isinstance(artifact, dict), "ADK release artifact declaration required")
    require(set(artifact) == {"name", "sha256"}, "ADK release artifact fields drift")
    require(artifact["name"] == "agent-dev-kit-5.1.0.tar.gz", "ADK release artifact name drift")
    require(artifact["sha256"] == ADK_RELEASE["release_artifact_sha256"], "ADK release artifact digest drift")

    require(adk["asset_profile"] == "embedded-fullstack", "required ADK asset profile drift")
    require(adk["delivery_mode"] == "exact-source-set", "ADK delivery mode drift")
    require(adk["binding_status"] == "source-set-bound", "ADK source-set binding status drift")

    source_set = adk["source_set"]
    require(isinstance(source_set, dict), "ADK source-set declaration required")
    require(source_set == {
        "identity": "exact-release-source-blobs",
        "consumer_assembly": "codex-runtime-distribution",
        "required_entry_fields": [
            "version", "vendor_rel", "source_repo", "source_ref", "source_path", "source_blob"
        ],
    }, "ADK source-set declaration drift")

    rules = adk["rules"]
    require(isinstance(rules, dict), "ADK provider rules required")
    require(set(rules) == {
        "consumer_must_bind_exact_release_source",
        "consumer_must_bind_exact_source_blob_per_vendored_asset",
        "consumer_must_own_runtime_assembly",
        "consumer_must_not_use_legacy_nested_repo_identity",
        "consumer_must_not_relabel_historical_evidence",
    }, "ADK provider rule set drift")
    require(all(value is True for value in rules.values()), "ADK provider rules must fail closed")

    serialized = json.dumps(adk, sort_keys=True)
    for retired in (
        "asset_bundle_hash", "BLOCKED_ASSET_BUNDLE_IDENTITY", "source-integrated-bundle-pending",
        "manifest-first", "5.0.0-rc.2", "llm_agent/agent-dev-kit", "provider_repo", "provider_contract",
        "agent_dev_kit-4.0.0",
    ):
        require(retired not in serialized, f"retired ADK compatibility resurfaced: {retired}")


def main() -> None:
    for path in [BINDING, ADK, HUB, RECEIPT, ADAPTER, AGENTS]:
        require(path.is_file(), f"missing runtime binding asset: {path.relative_to(ROOT)}")

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    adk = json.loads(ADK.read_text(encoding="utf-8"))
    hub = json.loads(HUB.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    require(binding["schema_version"] == 2 and binding["contract_version"] == "2.0", "Codex runtime binding schema drift")
    require(binding["status"] == "active", "Codex runtime binding must be active")
    require(binding["role"] == "codex-runtime-distribution-and-host-integration", "Codex role drift")
    require(binding["runtime_target"] == "codex-cli", "runtime target drift")
    require(binding["identity_layers"]["asset_profile"] != binding["identity_layers"]["runtime_profile"], "asset/runtime profile semantics must stay distinct")
    source_binding = binding["source_binding"]
    require(source_binding == {
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

    binding_text = json.dumps(binding, sort_keys=True)
    for retired in ("asset_bundle_hash", "BLOCKED_ASSET_BUNDLE_IDENTITY", "exact ADK bundle", "candidate-only"):
        require(retired not in binding_text, f"retired runtime binding compatibility resurfaced: {retired}")

    require(hub["repository"] == "jiying2007/knowledge-hub", "Knowledge Hub canonical repository required")
    require(re.fullmatch(r"[0-9a-f]{40}", hub["provider_commit"]) is not None, "Hub provider commit must be exact")
    require(hub["rules"]["consumer_must_not_depend_on_provider_internal_temp_paths"] is True, "Hub internal paths must not be contract")

    text = RECEIPT.read_text(encoding="utf-8")
    for forbidden in ["verification_pass", "release_ready", "domain_gate_pass"]:
        require(forbidden in text, f"receipt schema must explicitly forbid {forbidden}")
    require(receipt["additionalProperties"] is False, "receipt must be closed schema")

    adapter = ADAPTER.read_text(encoding="utf-8")
    for token in ["knowledge-context.sh", "knowledge-evidence-pack.sh", "knowledge-action-check.sh", "knowledge-proposal-route.sh", "knowledge-activity.sh", "BLOCKED"]:
        require(token in adapter, f"adapter missing surface: {token}")
    require(".tmp/activity/receipts" not in adapter, "adapter must not bind Hub internal receipt path")

    agents = AGENTS.read_text(encoding="utf-8")
    require(".tmp/activity/receipts" not in agents, "AGENTS must not bind Hub internal receipt path")

    print("runtime binding validation PASS")
    print(f"adk_version={adk['version']}")
    print(f"adk_commit={adk['provider_commit']}")
    print(f"binding_status={adk['binding_status']}")
    print(f"runtime_readiness={binding['readiness']}")


if __name__ == "__main__":
    main()
