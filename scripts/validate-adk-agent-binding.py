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

EXPECTED = {
    "architecture-planner",
    "build-release-engineer",
    "code-review-governor",
    "component-engineer",
    "driver-engineer",
    "performance-reliability-engineer",
    "requirements-analyst",
    "security-compliance-reviewer",
    "test-validation-engineer",
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
    require(provider["schema"] == "codex-provider-lock/v2", "provider lock schema drift")
    require(provider["repository"] == "jiying2007/agent-dev-kit", "provider repository drift")
    require(provider["version"] == "5.1.0", "provider version drift")
    require(provider["provider_commit"] == "59cbd5cb40ca7077ee5407636bfc617e295ec7e5", "provider commit drift")
    require(not (SOURCE / "vendor/agents/agent-dev-kit/2.9.0").exists(), "retired ADK 2.9.0 vendor tree still exists")

    adk_agents = {
        item["name"]: item
        for item in manifest["agents"]
        if str(item.get("vendor_rel", "")).startswith("vendor/agents/agent-dev-kit/")
    }
    require(set(adk_agents) == EXPECTED, f"ADK active agent set drift: {sorted(adk_agents)}")

    for name in sorted(EXPECTED):
        item = adk_agents[name]
        require(item.get("enabled") is True, f"{name}: must remain enabled")
        require(item.get("profiles") == ["team-collab"], f"{name}: profile drift")
        require(item.get("version") == provider["version"], f"{name}: provider version mismatch")
        require(item.get("source_repo") == provider["repository"], f"{name}: canonical repository mismatch")
        require(item.get("source_ref") == provider["provider_commit"], f"{name}: provider commit mismatch")
        require(item.get("review_status") == "accepted", f"{name}: review status must be accepted")
        require(re.fullmatch(r"[0-9a-f]{40}", str(item.get("source_blob", ""))) is not None, f"{name}: invalid source_blob")
        require(item.get("source_path") == f"agents/{name}/AGENTS.md", f"{name}: source_path drift")
        expected_rel = f"vendor/agents/agent-dev-kit/{provider['version']}/{name}/AGENTS.md"
        require(item.get("vendor_rel") == expected_rel, f"{name}: vendor path drift")
        vendor = SOURCE / expected_rel
        require(vendor.is_file(), f"{name}: vendored source missing")
        require(git_blob_sha(vendor) == item["source_blob"], f"{name}: vendored content != exact ADK source blob")
        rendered = json.dumps(item, ensure_ascii=False, sort_keys=True)
        require("2.9.0" not in rendered, f"{name}: retired 2.9.0 token returned")
        require("llm_agent/agent-dev-kit" not in rendered, f"{name}: retired nested repository identity returned")

    print("ADK agent binding PASS")
    print(f"provider_version={provider['version']}")
    print(f"provider_commit={provider['provider_commit']}")
    print(f"active_agents={len(adk_agents)}")


if __name__ == "__main__":
    main()
