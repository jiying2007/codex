#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="${1:-$ROOT_DEFAULT}"
ROOT="$(cd "$ROOT" && pwd)"
SOURCE="$ROOT/assets/codex"

errors=0
warnings=0

error() {
  echo "[ERROR] $*"
  errors=$((errors + 1))
}

warn() {
  echo "[WARN ] $*"
  warnings=$((warnings + 1))
}

check_absent() {
  local path="$1"
  if [ -e "$ROOT/$path" ] || [ -L "$ROOT/$path" ]; then
    error "根目录不应存在运行资产入口: $path"
  fi
}

check_file() {
  local path="$1"
  if [ ! -f "$path" ]; then
    error "缺少文件: $path"
  fi
}

check_dir() {
  local path="$1"
  if [ ! -d "$path" ]; then
    error "缺少目录: $path"
  fi
}

for path in agents control mcp prompts rules skills vendor config.toml config.debug.toml config.dev.toml config.embedded.toml config.max.toml; do
  check_absent "$path"
done

check_dir "$SOURCE"
check_file "$ROOT/README.md"
check_file "$ROOT/AGENTS.md"
check_file "$SOURCE/control/catalog/assets.txt"
check_file "$SOURCE/control/catalog/skills.csv"
check_file "$SOURCE/skills/registry.csv"

if [ -e "$SOURCE/skills/.system" ] || [ -L "$SOURCE/skills/.system" ]; then
  error "资产源不应包含 skills/.system"
fi

if find "$SOURCE" -type l -print -quit | grep -q .; then
  warn "资产源包含 symlink；apply 脚本会跳过，但建议确认是否为机器态入口"
fi

for script in "$ROOT"/scripts/*.sh; do
  [ -f "$script" ] || continue
  if ! bash -n "$script"; then
    error "脚本语法检查失败: $script"
  fi
done

if [ -x "$SOURCE/control/scripts/doctor.sh" ]; then
  if ! "$SOURCE/control/scripts/doctor.sh" "$SOURCE" team-collab; then
    warn "assets/codex/control/scripts/doctor.sh 报告问题，请检查上方输出"
  fi
else
  warn "资产源缺少可执行 doctor.sh"
fi

echo "[INFO ] asset-root=$ROOT source=$SOURCE errors=$errors warnings=$warnings"

if [ "$errors" -gt 0 ]; then
  exit 1
fi
