#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FAIL_ON="${SESSION_COACH_FAIL_ON:-never}"

usage() {
  printf '%s\n' \
    "Usage: scripts/apply-ready.sh [PLAN_PATH]" \
    "Build, validate, generate a bound apply plan, then execute a dry-run from any cwd."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if (( $# > 1 )); then
  echo "[FATAL] apply-ready 只接受一个可选 PLAN_PATH" >&2
  exit 2
fi
if [[ "${1:-}" == -* ]]; then
  echo "[FATAL] 未知参数: $1" >&2
  exit 2
fi
PLAN="${1:-$ROOT/build/apply-plan.apply-ready.json}"

rtk bash "$ROOT/scripts/build.sh"
rtk bash "$ROOT/scripts/doctor.sh" --scope all
rtk bash "$ROOT/scripts/plan.sh" --target "$HOME/.codex" --output "$PLAN"
rtk bash "$ROOT/scripts/apply.sh" --plan "$PLAN" --target "$HOME/.codex" --dry-run --plan-out "$ROOT/build/apply-plan.apply-ready-dry-run.json"
rtk bash "$ROOT/scripts/session-coach.sh" \
  --record-evidence apply-ready \
  --evidence-status pass \
  --evidence-summary "apply-ready completed"
rtk bash "$ROOT/scripts/session-coach.sh" --event apply --deep --top 8 --no-cooldown --fail-on "$FAIL_ON"
