#!/usr/bin/env bash
# gen-registry.sh — 从 control/catalog/skills.csv 自动生成 skills/registry.csv
# 用法：control/scripts/gen-registry.sh [ROOT]

set -euo pipefail
ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SKILLS_CSV="$ROOT/control/catalog/skills.csv"
REGISTRY="$ROOT/skills/registry.csv"

if [ ! -f "$SKILLS_CSV" ]; then
  echo "[ERROR] 缺少 $SKILLS_CSV" >&2
  exit 2
fi

{
  echo "name,version,status,owner"
  while IFS=, read -r name enabled _kind version _vendor _target _profiles _tags; do
    [ "$name" = "name" ] && continue
    [ -z "$name" ] && continue
    status="active"
    [ "$enabled" != "1" ] && status="disabled"
    echo "$name,$version,$status,global"
  done < "$SKILLS_CSV"
} > "$REGISTRY"

echo "[INFO] 已生成 $REGISTRY（$(grep -c '' "$REGISTRY") 行）"
