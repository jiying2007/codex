#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 4500

FORBIDDEN = (
    "~/knowledge-hub/local/activity-report.json",
    "~/knowledge-hub/tools/knowledge-",
    ".tmp/activity/receipts",
    "knowledge-context.sh",
    "knowledge-activity.sh",
    "runtime-control.sh",
    "execution-policy.sh",
    "Runtime Control",
)
REQUIRED = (
    "~/codex/scripts/knowledge-provider.sh",
    "Provider Adapter",
    "jiying2007/agent-dev-kit",
    "exact provider commit",
    "Execution Policy",
    "Digital Worker 不是日常前置依赖",
    'execution-policy --thread-id "${CODEX_THREAD_ID:?current thread id required}" gate --event final',
    "(cd ~/codex && rtk python3 -m tools.codex_assets",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def validate_rules(root: Path) -> int:
    root_bytes = (root / "AGENTS.md").read_bytes()
    source_bytes = (root / "src/codex-home/AGENTS.md").read_bytes()
    require(root_bytes == source_bytes, "AGENTS root/source SSOT drift")
    require(len(root_bytes) <= MAX_BYTES, f"AGENTS exceeds byte budget: {len(root_bytes)} > {MAX_BYTES}")
    text = root_bytes.decode("utf-8")
    for token in FORBIDDEN:
        require(token not in text, f"retired runtime instruction returned: {token}")
    for token in REQUIRED:
        require(token in text, f"required terminal rule missing: {token}")
    assets = json.loads((root / "manifests/assets.json").read_text(encoding="utf-8"))
    profiles = json.loads((root / "manifests/profiles.json").read_text(encoding="utf-8"))
    names = {item["name"] for item in profiles["profiles"]}
    default = assets["default_profile"]
    require(default in names, "default runtime profile is not declared")
    require(f"默认 adk-first、`{default}`" in text, "AGENTS default profile differs from manifest")
    for profile in re.findall(r"--profile\s+([a-z0-9-]+)", text):
        require(profile in names, f"AGENTS references an undeclared profile: {profile}")
    for group in re.findall(r"`([^`]+)` 是 Codex Runtime Profile", text):
        for profile in group.split("/"):
            require(profile in names, f"AGENTS describes an undeclared profile: {profile}")
    return len(root_bytes)


def main() -> None:
    size = validate_rules(ROOT)
    print("AGENTS terminal contract PASS")
    print(f"bytes={size}")
    print("knowledge_boundary=provider-adapter-only")
    print("daily_boundary=cli-adk-project-acceptance")


if __name__ == "__main__":
    main()
