#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_TARGET="${1:-/tmp/codex-assets-smoke-home}"
PROFILES=(minimal solo-dev team-collab)

rtk bash "$ROOT/scripts/doctor.sh" --scope repo

for profile in "${PROFILES[@]}"; do
  TARGET="$BASE_TARGET-$profile"
  BUILD="$ROOT/build/smoke-$profile"
  PLAN="$ROOT/build/apply-plan.smoke-$profile.json"

  rm -rf "$TARGET" "$BUILD"
  mkdir -p "$TARGET/skills/.system"
  printf 'system\n' > "$TARGET/skills/.system/keep"

  rtk bash "$ROOT/scripts/build.sh" --profile "$profile" --build "$BUILD"
  rtk bash "$ROOT/scripts/doctor.sh" --scope build --build "$BUILD"
  rtk bash "$ROOT/scripts/plan.sh" --build "$BUILD" --target "$TARGET" --output "$PLAN"
  rtk bash "$ROOT/scripts/apply.sh" --no-build --build "$BUILD" --target "$TARGET" --plan-out "$ROOT/build/apply-plan.smoke-live-$profile.json"
  rtk bash "$ROOT/scripts/diff.sh" --build "$BUILD" --target "$TARGET"
  rtk bash "$ROOT/scripts/drift.sh" --build "$BUILD" --target "$TARGET"
  rtk bash "$ROOT/scripts/doctor.sh" --scope live --build "$BUILD" --target "$TARGET"

  test -f "$TARGET/skills/.system/keep"
  test -f "$PLAN"
  case "$profile" in
    minimal)
      test -L "$TARGET/skills/caveman"
      ;;
    solo-dev|team-collab)
      test -L "$TARGET/skills/skill-asset-manager"
      ;;
  esac
done

rtk bash "$ROOT/scripts/build.sh" --profile team-collab
test -f "$ROOT/manifests/lock.json"

echo "[DONE] smoke profiles=${PROFILES[*]} base=$BASE_TARGET"
