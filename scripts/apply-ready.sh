#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLAN="${1:-$ROOT/build/apply-plan.apply-ready.json}"
FAIL_ON="${SESSION_COACH_FAIL_ON:-never}"

rtk bash "$ROOT/scripts/build.sh"
rtk bash "$ROOT/scripts/doctor.sh" --scope all
rtk bash "$ROOT/scripts/plan.sh" --target "$HOME/.codex" --output "$PLAN"
rtk bash "$ROOT/scripts/apply.sh" --dry-run --no-build --target "$HOME/.codex" --plan-out "$ROOT/build/apply-plan.apply-ready-dry-run.json"
rtk bash "$ROOT/scripts/session-coach.sh" \
  --record-evidence apply-ready \
  --evidence-status pass \
  --evidence-summary "apply-ready completed"
rtk bash "$ROOT/scripts/session-coach.sh" --event apply --deep --top 8 --no-cooldown --fail-on "$FAIL_ON"
