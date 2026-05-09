#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="${1:-/tmp/codex-assets-smoke-home}"

rm -rf "$TARGET"
mkdir -p "$TARGET/skills/.system"
printf 'system\n' > "$TARGET/skills/.system/keep"

rtk bash "$ROOT/scripts/build.sh" --profile team-collab
rtk bash "$ROOT/scripts/doctor.sh" --scope repo
rtk bash "$ROOT/scripts/doctor.sh" --scope build
rtk bash "$ROOT/scripts/plan.sh" --target "$TARGET" --output "$ROOT/build/apply-plan.smoke.json"
rtk bash "$ROOT/scripts/apply.sh" --no-build --target "$TARGET"
rtk bash "$ROOT/scripts/diff.sh" --target "$TARGET"
rtk bash "$ROOT/scripts/drift.sh" --target "$TARGET"
rtk bash "$ROOT/scripts/doctor.sh" --scope live --target "$TARGET"

test -f "$TARGET/skills/.system/keep"
test -L "$TARGET/skills/skill-asset-manager"
test -f "$ROOT/manifests/lock.json"
test -f "$ROOT/build/apply-plan.smoke.json"

echo "[DONE] smoke target=$TARGET"
