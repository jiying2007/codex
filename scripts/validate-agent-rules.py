#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_RULES = ROOT / "AGENTS.md"
SOURCE_RULES = ROOT / "src/codex-home/AGENTS.md"
MAX_BYTES = 4500

FORBIDDEN = (
    "~/knowledge-hub/local/activity-report.json",
    "~/knowledge-hub/tools/knowledge-",
    ".tmp/activity/receipts",
    "knowledge-context.sh",
    "knowledge-activity.sh",
)
REQUIRED = (
    "~/codex/scripts/knowledge-provider.sh",
    "Provider Adapter",
    "jiying2007/agent-dev-kit",
    "exact provider commit",
    "Runtime Control",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def main() -> None:
    root_bytes = ROOT_RULES.read_bytes()
    source_bytes = SOURCE_RULES.read_bytes()
    require(root_bytes == source_bytes, "AGENTS root/source SSOT drift")
    require(len(root_bytes) <= MAX_BYTES, f"AGENTS exceeds byte budget: {len(root_bytes)} > {MAX_BYTES}")
    text = root_bytes.decode("utf-8")
    for token in FORBIDDEN:
        require(token not in text, f"retired direct Knowledge Hub compatibility returned: {token}")
    for token in REQUIRED:
        require(token in text, f"required terminal rule missing: {token}")
    print("AGENTS terminal contract PASS")
    print(f"bytes={len(root_bytes)}")
    print("knowledge_boundary=provider-adapter-only")


if __name__ == "__main__":
    main()
