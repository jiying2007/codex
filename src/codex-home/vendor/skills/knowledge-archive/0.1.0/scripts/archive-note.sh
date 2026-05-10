#!/usr/bin/env bash
set -euo pipefail

REPO="${CODEX_ASSET_REPO:-$HOME/codex}"

if [[ ! -x "$REPO/scripts/archive-note.sh" ]]; then
  echo "[FATAL] archive-note entrypoint not found: $REPO/scripts/archive-note.sh" >&2
  exit 2
fi

exec rtk bash "$REPO/scripts/archive-note.sh" "$@"
