#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

rtk bash "$ROOT/scripts/build.sh" --profile team-collab
rtk bash "$ROOT/scripts/doctor.sh" --scope all
rtk bash "$ROOT/scripts/plan.sh" --target "$HOME/.codex" --output "$ROOT/build/apply-plan.check.json"
rtk bash "$ROOT/scripts/apply.sh" --dry-run --no-build --target "$HOME/.codex" --plan-out "$ROOT/build/apply-plan.check-dry-run.json"
rtk bash "$ROOT/tests/smoke.sh"
rtk bash "$ROOT/scripts/diff.sh" --target "$HOME/.codex"
rtk bash "$ROOT/scripts/drift.sh" --target "$HOME/.codex"

if rtk rg -n "(sk-[A-Za-z0-9_-]{20,}|(api[_-]?key|token|password)\\s*[:=]\\s*['\\\"][A-Za-z0-9_./+=:-]{16,}['\\\"]|BEGIN (RSA|OPENSSH|EC|DSA|PRIVATE) KEY)" "$ROOT" --glob '!build/**' --glob '!.git/**'; then
  echo "[FATAL] 疑似敏感信息命中" >&2
  exit 1
fi

for old_script in apply-to-codex.sh scan-codex-skills.sh doctor-assets.sh diff-codex.sh backup-codex.sh; do
  if [[ -e "$ROOT/scripts/$old_script" ]]; then
    echo "[FATAL] 旧脚本入口残留: scripts/$old_script" >&2
    exit 1
  fi
done

if rtk rg -n "assets/codex|control/catalog|apply-to-codex|scan-codex-skills|doctor-assets|diff-codex|backup-codex" "$ROOT/README.md" "$ROOT/docs" "$ROOT/manifests" "$ROOT/scripts" "$ROOT/src" "$ROOT/tools" "$ROOT/tests" --glob '!build/**' --glob '!scripts/check.sh'; then
  echo "[FATAL] 旧入口残留命中" >&2
  exit 1
fi

echo "[DONE] check"
