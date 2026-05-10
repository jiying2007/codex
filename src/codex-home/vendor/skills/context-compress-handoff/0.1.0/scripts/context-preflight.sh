#!/usr/bin/env bash
set -euo pipefail

REPO="${CODEX_ASSET_REPO:-$HOME/codex}"

if [[ ! -x "$REPO/scripts/context-preflight.sh" ]]; then
  echo "[FATAL] context-preflight entrypoint not found: $REPO/scripts/context-preflight.sh" >&2
  exit 2
fi

exec rtk bash "$REPO/scripts/context-preflight.sh" "$@"
