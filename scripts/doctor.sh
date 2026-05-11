#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for script in "$ROOT"/scripts/*.sh; do
  [ -f "$script" ] || continue
  rtk bash -n "$script"
done

rtk python3 -m py_compile "$ROOT"/tools/codex_assets/*.py
exec env PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  rtk python3 -m tools.codex_assets doctor --root "$ROOT" "$@"
