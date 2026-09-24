#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/codex-home"
AGENTS = ROOT / "manifests/agents.json"
PROVIDER = ROOT / "manifests/provider-locks/agent-dev-kit.json"

PROVIDER_VERSION = "7.0.31"
PROVIDER_COMMIT = "7367ef84787de75bb751940b32c9e80009660e47"
EXPECTED = {
    "architecture-planner": "3b7638b277806f0e752a2ae5d261a93047c394b0",
    "build-release-engineer": "e9fca2c67489d9dd5471f6b075ba2d660397f322",
    "code-review-governor": "c30ad03e8ed093d90c702a26a4bf53e27110c047",
    "component-engineer": "5f837f15739eb4cddc39c5afcbea605463cf673b",
    "driver-engineer": "648d4a236fd86696bfeba861e57a3f849adee80b",
    "performance-reliability-engineer": "65bcc09b0fa086341b157a1e2a69dfece063f38a",
    "requirements-analyst": "92c58a6112800359ac32c88bc141f9335763ea40",
    "security-compliance-reviewer": "8beec5332ddc26fb57db894b38a88c49303f3a15",
    "test-validation-engineer": "dd66ee4e568e2493615f8e7c1e28a4931abe8603",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def main() -> None:
    provider = json.loads(PROVIDER.read_text(encoding="utf-8"))
    manifest = json.loads(AGENTS.read_text(encoding="utf-8"))
    require(provider["schema"] == "codex-provider-lock/v3", "provider lock schema drift")
    require(provider["repository"] == "jiying2007/agent-dev-kit", "provider repository drift")
    require(provider["version"] == PROVIDER_VERSION, "provider version drift")
    require(provider["release_tag"] == "v7.0.31", "provider release tag drift")
    require(provider["provider_commit"] == PROVIDER_COMMIT, "provider commit drift")
    require(provider["delivery_mode"] == "exact-source-set", "provider delivery mode drift")
    require(provider["binding_status"] == "source-set-bound", "provider binding status drift")
    require(provider["source_set"] == {
        "identity": "exact-release-source-blobs",
        "consumer_assembly": "codex-runtime-distribution",
        "required_entry_fields": [
            "version", "vendor_rel", "source_repo", "source_ref", "source_path", "source_blob"
        ],
    }, "provider source-set contract drift")
    require(not (SOURCE / "vendor/agents/agent-dev-kit/2.9.0").exists(), "retired ADK 2.9.0 vendor tree still exists")

    require(sorted(path.name for path in (SOURCE / "vendor/agents/agent-dev-kit").iterdir()) == [PROVIDER_VERSION], "retired ADK vendor tree returned")

    adk_agents = {
        item["name"]: item
        for item in manifest["agents"]
        if str(item.get("vendor_rel", "")).startswith("vendor/agents/agent-dev-kit/")
    }
    require(set(adk_agents) == set(EXPECTED), f"ADK active agent set drift: {sorted(adk_agents)}")

    for name, expected_blob in sorted(EXPECTED.items()):
        item = adk_agents[name]
        require(item.get("enabled") is True, f"{name}: must remain enabled")
        require(item.get("profiles") == ["team-collab"], f"{name}: profile drift")
        require(item.get("version") == PROVIDER_VERSION, f"{name}: provider version mismatch")
        require(item.get("source_repo") == provider["repository"], f"{name}: canonical repository mismatch")
        require(item.get("source_ref") == PROVIDER_COMMIT, f"{name}: provider commit mismatch")
        require(item.get("source_blob") == expected_blob, f"{name}: immutable provider blob mismatch")
        require(re.fullmatch(r"[0-9a-f]{40}", str(item.get("source_blob", ""))) is not None, f"{name}: invalid source_blob")
        require(item.get("source_path") == f"agents/{name}/AGENTS.md", f"{name}: source_path drift")
        expected_rel = f"vendor/agents/agent-dev-kit/{PROVIDER_VERSION}/{name}/AGENTS.md"
        require(item.get("vendor_rel") == expected_rel, f"{name}: vendor path drift")
        require(item.get("review_status") == "accepted", f"{name}: review status must be accepted")
        vendor = SOURCE / expected_rel
        require(vendor.is_file(), f"{name}: vendored source missing")
        require(git_blob_sha(vendor) == expected_blob, f"{name}: vendored content != exact ADK source blob")
        rendered = json.dumps(item, ensure_ascii=False, sort_keys=True)
        for retired in ("2.9.0", "llm_agent/agent-dev-kit", "asset_bundle_hash", "BLOCKED_ASSET_BUNDLE_IDENTITY"):
            require(retired not in rendered, f"{name}: retired compatibility token returned: {retired}")

    provider_text = json.dumps(provider, ensure_ascii=False, sort_keys=True)
    for retired in ("codex-provider-lock/v2", "asset_bundle_hash", "BLOCKED_ASSET_BUNDLE_IDENTITY", "manifest-first"):
        require(retired not in provider_text, f"provider lock retired compatibility returned: {retired}")

    print("ADK agent binding PASS")
    print(f"provider_version={provider['version']}")
    print(f"provider_commit={provider['provider_commit']}")
    print(f"binding_status={provider['binding_status']}")
    print(f"active_agents={len(adk_agents)}")


if __name__ == "__main__":
    main()
