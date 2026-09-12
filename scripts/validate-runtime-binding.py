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


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def main() -> None:
    for path in [BINDING, ADK, HUB, RECEIPT, ADAPTER, AGENTS]:
        require(path.is_file(), f"missing runtime binding asset: {path.relative_to(ROOT)}")

    binding = json.loads(BINDING.read_text(encoding="utf-8"))
    adk = json.loads(ADK.read_text(encoding="utf-8"))
    hub = json.loads(HUB.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    require(binding["role"] == "codex-runtime-distribution-and-host-integration", "Codex role drift")
    require(binding["runtime_target"] == "codex-cli", "runtime target drift")
    require(binding["identity_layers"]["asset_profile"] != binding["identity_layers"]["runtime_profile"], "asset/runtime profile semantics must stay distinct")
    require(binding["gate_semantics"]["runtime_success_implies_domain_verification_pass"] is False, "runtime must not claim domain PASS")
    require("cross_runtime_effectiveness_evaluation" in binding["must_not_own"], "cross-runtime eval must remain outside Codex binding")

    require(adk["repository"] == "jiying2007/agent-dev-kit", "ADK canonical repository required")
    require(re.fullmatch(r"[0-9a-f]{40}", adk["provider_commit"]) is not None, "ADK provider commit must be exact")
    require(adk["asset_profile"] == "embedded-fullstack", "required ADK asset profile drift")
    bundle = adk.get("asset_bundle_hash")
    if bundle is None:
        require(adk["readiness"] == "BLOCKED_ASSET_BUNDLE_IDENTITY", "missing bundle hash must fail closed")
    else:
        require(re.fullmatch(r"[0-9a-f]{64}", bundle) is not None, "bundle hash must be SHA-256")

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
    print(f"readiness={adk['readiness']}")


if __name__ == "__main__":
    main()
