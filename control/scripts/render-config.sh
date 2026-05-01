#!/usr/bin/env bash
set -euo pipefail

ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="$ROOT_DEFAULT"
PROFILE=""

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "用法: $(basename "$0") [ROOT] [profile]"
  exit 0
fi

if [ "$#" -eq 1 ] && [ -d "$1" ]; then
  ROOT="$1"
elif [ "$#" -eq 1 ]; then
  PROFILE="$1"
elif [ "$#" -ge 2 ] && [ -d "$1" ]; then
  ROOT="$1"
  PROFILE="$2"
elif [ "$#" -ge 2 ]; then
  PROFILE="$1"
fi

CATALOG_DIR="$ROOT/control/catalog"
MCP_CSV="$CATALOG_DIR/mcp.csv"
CONFIG_FILE="$ROOT/config.toml"
GENERATED_DIR="$ROOT/control/generated"
STATE_FILE="$ROOT/control/state/active-profile.env"
FRAGMENT_FILE="$GENERATED_DIR/config-managed.toml"

mkdir -p "$GENERATED_DIR"

if [ -z "$PROFILE" ] && [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

if [ -z "${PROFILE:-}" ]; then
  echo "[ERROR] 未提供 profile，且未找到 active-profile.env" >&2
  exit 2
fi

if [ ! -f "$MCP_CSV" ] || [ ! -f "$CONFIG_FILE" ]; then
  echo "[ERROR] 缺少 mcp catalog 或 config.toml" >&2
  exit 2
fi

has_profile() {
  local field="$1"
  local profile="$2"
  local token
  IFS='|' read -r -a parts <<< "$field"
  for token in "${parts[@]}"; do
    if [ "$token" = "$profile" ]; then
      return 0
    fi
  done
  return 1
}

bool_word() {
  if [ "$1" = "1" ]; then
    echo "true"
  else
    echo "false"
  fi
}

emit_array() {
  local raw="$1"
  local item
  local out=""
  if [ -z "$raw" ]; then
    echo "[]"
    return
  fi

  IFS='|' read -r -a items <<< "$raw"
  for item in "${items[@]}"; do
    [ -z "$item" ] && continue
    if [ -n "$out" ]; then
      out+="\"$item\", "
    else
      out="\"$item\", "
    fi
  done
  out="${out%, }"
  echo "[$out]"
}

{
  echo "# >>> CODEX-MANAGED MCP START"
  echo "# profile = $PROFILE"
  echo "# generated_at = $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo

  while IFS=, read -r name enabled _transport command args env_keys required parallel _group profiles _notes; do
    [ "$name" = "name" ] && continue
    [ -z "$name" ] && continue

    if ! has_profile "$profiles" "$PROFILE"; then
      continue
    fi

    echo "[mcp_servers.$name]"
    echo "command = \"$command\""
    echo "args = $(emit_array "$args")"
    echo "enabled = $(bool_word "$enabled")"
    echo "required = $(bool_word "$required")"
    echo "supports_parallel_tool_calls = $(bool_word "$parallel")"

    if [ -n "$env_keys" ]; then
      echo
      echo "[mcp_servers.$name.env]"
      IFS='|' read -r -a env_arr <<< "$env_keys"
      for key in "${env_arr[@]}"; do
        [ -z "$key" ] && continue
        echo "$key = \"\""
      done
    fi

    echo
  done < "$MCP_CSV"

  echo "# <<< CODEX-MANAGED MCP END"
} > "$FRAGMENT_FILE"

if rg -q "# >>> CODEX-MANAGED MCP START" "$CONFIG_FILE"; then
  awk '
    BEGIN {skip=0}
    /^# >>> CODEX-MANAGED MCP START/ {skip=1; next}
    /^# <<< CODEX-MANAGED MCP END/ {skip=0; next}
    skip==0 {print}
  ' "$CONFIG_FILE" > "$CONFIG_FILE.tmp"
  mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
fi

{
  echo
  cat "$FRAGMENT_FILE"
} >> "$CONFIG_FILE"

echo "[INFO] 已写入 managed 区块: $CONFIG_FILE"
echo "[INFO] 片段文件: $FRAGMENT_FILE"
