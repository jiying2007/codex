#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FAIL_ON="${SESSION_COACH_FAIL_ON:-never}"

rtk git -C "$ROOT" diff --check
rtk bash "$ROOT/scripts/session-coach.sh" \
  --record-evidence final-ready \
  --evidence-status pass \
  --evidence-summary "final-ready completed"
rtk bash "$ROOT/scripts/session-coach.sh" --event final --deep --top 8 --no-cooldown --fail-on "$FAIL_ON"
