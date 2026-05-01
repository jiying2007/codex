#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

"$ROOT/control/scripts/sync-skills-vendor.sh" "$ROOT"

profile="${2:-minimal}"
"$ROOT/control/scripts/activate-profile.sh" "$ROOT" "$profile"
"$ROOT/control/scripts/doctor.sh" "$ROOT" "$profile"

echo "[INFO] vendor 同步完成，当前 profile=$profile"
