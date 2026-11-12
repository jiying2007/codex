#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
exec env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  rtk python3 -m tools.codex_assets disk-usage --root "$ROOT" "$@"
