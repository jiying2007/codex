#!/usr/bin/env bash
set -euo pipefail

if [ -x "./scripts/apply-to-codex.sh" ] && [ -f "./assets/codex/control/catalog/skills.csv" ]; then
  exec rtk bash ./scripts/apply-to-codex.sh "$@"
fi

echo "[FATAL] 请在 Codex 资产仓库根目录运行，或直接调用仓库 scripts/apply-to-codex.sh" >&2
exit 2
