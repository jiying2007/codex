#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec env PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  rtk python3 -m tools.codex_assets build --root "$ROOT" "$@"
