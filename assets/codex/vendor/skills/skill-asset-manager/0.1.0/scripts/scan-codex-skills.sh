#!/usr/bin/env bash
set -euo pipefail

if [ -x "./scripts/scan-codex-skills.sh" ] && [ -f "./assets/codex/control/catalog/skills.csv" ]; then
  exec rtk bash ./scripts/scan-codex-skills.sh "$@"
fi

echo "[FATAL] 请在 Codex 资产仓库根目录运行，或直接调用仓库 scripts/scan-codex-skills.sh" >&2
exit 2
