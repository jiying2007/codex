#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_TARGET="${1:-/tmp/codex-assets-smoke-home}"
PROFILES=(minimal solo-dev default team-collab)
MAIN_PROFILE="default"
MAIN_PROFILE_STATE="$ROOT/build/codex-home/control/state/active-profile.env"
if [[ -f "$MAIN_PROFILE_STATE" ]]; then
  MAIN_PROFILE="$(sed -n 's/^PROFILE=//p' "$MAIN_PROFILE_STATE")"
fi
case "$MAIN_PROFILE" in
  minimal|solo-dev|default|team-collab) ;;
  *)
    echo "[FATAL] invalid main build profile: $MAIN_PROFILE" >&2
    exit 2
    ;;
esac

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
    default)
      test -L "$TARGET/skills/adk-runtime-router"
      test ! -e "$TARGET/skills/skill-asset-manager"
      test "$(find "$TARGET/skills" -mindepth 1 -maxdepth 1 -type l | wc -l)" -eq 11
      ;;
  esac
done

rtk bash "$ROOT/scripts/build.sh" --profile "$MAIN_PROFILE"
test -f "$ROOT/manifests/lock.json"
grep -Fxq "PROFILE=$MAIN_PROFILE" "$MAIN_PROFILE_STATE"

echo "[DONE] smoke profiles=${PROFILES[*]} base=$BASE_TARGET"
