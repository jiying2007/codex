#!/usr/bin/env bash
set -euo pipefail
export KNOWLEDGE_PROVIDER_CALLER_CWD="${KNOWLEDGE_PROVIDER_CALLER_CWD:-$PWD}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
exec python3 -I "$ROOT/tools/codex_assets/isolated_runtime.py" "$ROOT" tools.codex_assets.knowledge_provider_adapter "$@"
