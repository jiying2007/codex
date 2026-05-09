#!/usr/bin/env bash
set -euo pipefail

if [ -x "./scripts/rollback.sh" ] && [ -f "./manifests/skills.json" ] && [ -d "./src/codex-home" ]; then
  exec rtk bash ./scripts/rollback.sh "$@"
fi

echo "[FATAL] 请在 Codex v2 资产仓库根目录运行，或直接调用仓库 scripts/rollback.sh" >&2
exit 2
