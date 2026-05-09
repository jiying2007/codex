#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for script in "$ROOT"/scripts/*.sh; do
  [ -f "$script" ] || continue
  bash -n "$script"
done

python3 -m py_compile "$ROOT"/tools/codex_assets/*.py
exec python3 -m tools.codex_assets doctor --root "$ROOT" "$@"
