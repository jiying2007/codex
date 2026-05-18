#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FAIL_ON="${SESSION_COACH_FAIL_ON:-never}"

rtk git -C "$ROOT" diff --check
rtk git -C "$ROOT" diff --cached --check
rtk bash "$ROOT/scripts/session-coach.sh" \
  --record-evidence commit-ready \
  --evidence-status pass \
  --evidence-summary "commit-ready completed"
rtk bash "$ROOT/scripts/session-coach.sh" --event commit --deep --top 8 --no-cooldown --fail-on "$FAIL_ON"
