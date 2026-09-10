#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="post-apply"
OFFLINE_HERMETIC=0
TARGET="$HOME/.codex"
RUN_BUILD=1
PLAN=""

usage() {
  printf '%s\n' \
    'Usage: scripts/check.sh [--pre-apply] [--offline-hermetic] [--no-build] [--plan PATH] [--target PATH]' \
    '' \
    'Run the complete Codex asset verification gate.' \
    '' \
    'Options:' \
    '  --pre-apply   Verify source, build, governance, tests, smoke and apply dry-run' \
    '                without asserting that the current live target already matches.' \
    '  --no-build    Reuse build only when doctor proves its source fingerprint current.' \
    '  --plan PATH   Reuse this plan; its build receipt and target are verified.' \
    '  --target PATH Use PATH as the live/apply-plan target (default: ~/.codex).' \
    '  -h, --help    Show this help and exit.' \
    '' \
    'The default post-apply mode remains fail-closed: it verifies live doctor,' \
    'build/live diff and managed-state drift.'
}

while (($# > 0)); do
  case "$1" in
    --pre-apply)
      MODE="pre-apply"
      shift
      ;;
    --target)
      if (($# < 2)); then
        echo "[FATAL] --target 缺少路径参数" >&2
        usage >&2
        exit 2
      fi
      TARGET="$2"
      shift 2
      ;;
    --no-build)
      RUN_BUILD=0
      shift
      ;;
    --offline-hermetic)
      OFFLINE_HERMETIC=1
      shift
      ;;
    --plan)
      if (($# < 2)); then
        echo "[FATAL] --plan 缺少路径参数" >&2
        usage >&2
        exit 2
      fi
      PLAN="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FATAL] 未知参数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"

echo "[INFO] check_mode=$MODE target=$TARGET run_build=$RUN_BUILD plan=${PLAN:-generated}"
if [[ "$RUN_BUILD" == "1" ]]; then
  rtk bash "$ROOT/scripts/build.sh"
else
  echo "[INFO] build=reused validation=doctor-source-fingerprint"
fi
if [[ "$MODE" == "post-apply" ]]; then
  rtk bash "$ROOT/scripts/doctor.sh" --scope all --target "$TARGET"
else
  rtk bash "$ROOT/scripts/doctor.sh" --scope repo
  rtk bash "$ROOT/scripts/doctor.sh" --scope build
fi
rtk bash "$ROOT/scripts/doctor.sh" --scope governance
rtk bash "$ROOT/scripts/check-mcp-deny-paths.sh"
rtk bash "$ROOT/scripts/governance-report.sh" --summary-json
if [[ "$OFFLINE_HERMETIC" == "1" ]]; then
  export CODEX_OFFLINE_HERMETIC=1
  echo "[INFO] test_network=disabled mode=offline-hermetic"
fi
env PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" rtk python3 -m unittest discover -s "$ROOT/tests" -p 'test_*.py'
rtk bash "$ROOT/scripts/check-routing-precedence.sh"
rtk bash "$ROOT/scripts/check-skills.sh"
if [[ "${REQUIRE_MODERN_BWRAP:-0}" == "1" ]]; then
  rtk bash "$ROOT/scripts/check-bwrap-capability.sh" --require-modern --json-out "$ROOT/build/bwrap-capability.json"
else
  rtk bash "$ROOT/scripts/check-bwrap-capability.sh" --json-out "$ROOT/build/bwrap-capability.json"
fi
if [[ -z "$PLAN" ]]; then
  PLAN="$ROOT/build/apply-plan.check.json"
  rtk bash "$ROOT/scripts/plan.sh" --target "$TARGET" --prune-stale --output "$PLAN"
else
  echo "[INFO] plan=reused validation=build-receipt+target"
fi
rtk bash "$ROOT/scripts/apply.sh" --plan "$PLAN" --target "$TARGET" --dry-run --plan-out "$ROOT/build/apply-plan.check-dry-run.json"
rtk bash "$ROOT/tests/smoke.sh"
if [[ "$MODE" == "post-apply" ]]; then
  rtk bash "$ROOT/scripts/diff.sh" --target "$TARGET"
  rtk bash "$ROOT/scripts/drift.sh" --target "$TARGET"
else
  echo "[INFO] live_consistency=skipped reason=pre-apply"
fi

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

for old_control in control/archives control/knowledge control/roles control/workflows control/scripts control/catalog control/generated; do
  if [[ -e "$ROOT/src/codex-home/$old_control" ]]; then
    echo "[FATAL] v2 源资产包含旧 control 边界: src/codex-home/$old_control" >&2
    exit 1
  fi
done

if rtk rg -n "assets/codex|control/catalog|apply-to-codex|scan-codex-skills|doctor-assets|diff-codex|backup-codex" "$ROOT/README.md" "$ROOT/docs" "$ROOT/manifests" "$ROOT/scripts" "$ROOT/src" "$ROOT/tools" "$ROOT/tests" --glob '!build/**' --glob '!scripts/check.sh' --glob '!tools/codex_assets/check_skills.py' --glob '!tools/codex_assets/cli.py' --glob '!tools/codex_assets/core.py' --glob '!docs/design.md'; then
  echo "[FATAL] 旧入口残留命中" >&2
  exit 1
fi

echo "[DONE] check"
