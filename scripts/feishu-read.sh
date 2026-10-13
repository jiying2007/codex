#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
exec env -u PYTHONPATH -u PYTHONHOME rtk python3 -E -m tools.codex_assets feishu-read --root "$ROOT" "$@"
