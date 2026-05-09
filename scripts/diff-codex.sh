#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SOURCE=""
TARGET="$HOME/.codex"
MANIFEST=""
ONLY=""

usage() {
  cat <<'USAGE'
用法: scripts/diff-codex.sh [options]

对比当前仓库登记资产与 ~/.codex 中对应文件的差异。

Options:
  --root PATH      源仓库根目录（默认：脚本所在仓库）
  --source PATH    资产源目录（默认：<root>/assets/codex）
  --target PATH    目标目录（默认：~/.codex）
  --manifest PATH  资产清单（默认：<source>/control/catalog/assets.txt）
  --only LIST      只对比逗号分隔的顶层路径，如 skills,prompts,vendor
  -h, --help       显示帮助
USAGE
}

csv_contains() {
  local list="$1"
  local item="$2"
  local part
  [ -n "$list" ] || return 0
  IFS=',' read -r -a parts <<< "$list"
  for part in "${parts[@]}"; do
    part="${part#"${part%%[![:space:]]*}"}"
    part="${part%"${part##*[![:space:]]}"}"
    [ "$part" = "$item" ] && return 0
  done
  return 1
}

is_excluded_rel() {
  local rel="$1"
  case "$rel" in
    .git|.git/*|.codex|.codex/*|.tmp|.tmp/*|tmp|tmp/*|cache|cache/*|log|log/*|sessions|sessions/*|shell_snapshots|shell_snapshots/*|memories|memories/*)
      return 0
      ;;
    auth.json|history.jsonl|installation_id|models_cache.json|session_index.jsonl|version.json|tasks.codex.json)
      return 0
      ;;
    logs_*.sqlite|logs_*.sqlite-shm|logs_*.sqlite-wal|state_*.sqlite|state_*.sqlite-shm|state_*.sqlite-wal)
      return 0
      ;;
    skills/.system|skills/.system/*|mcp/secrets|mcp/secrets/*|control/state/active-profile.env|control/state/backup|control/state/backup/*|control/generated/config-managed.toml)
      return 0
      ;;
    *.secret|*.key|*.pem|config.local.*)
      return 0
      ;;
  esac
  return 1
}

collect_files() {
  local base="$1"
  local src="$SOURCE/$base"
  if [ -L "$src" ]; then
    return 0
  elif [ -d "$src" ]; then
    find "$src" \
      \( -path "$SOURCE/skills/.system" -o -path "$SOURCE/mcp/secrets" -o -path "$SOURCE/control/state/backup" \) -prune \
      -o -type f -print | sort
  elif [ -e "$src" ]; then
    printf '%s\n' "$src"
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --source)
      SOURCE="$2"
      shift 2
      ;;
    --target)
      TARGET="$2"
      shift 2
      ;;
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
    --only)
      ONLY="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[FATAL] 未知参数: $1" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SOURCE="${SOURCE:-$ROOT/assets/codex}"
SOURCE="$(cd "$SOURCE" && pwd)"
TARGET="${TARGET/#\~/$HOME}"
MANIFEST="${MANIFEST:-$SOURCE/control/catalog/assets.txt}"

[ -f "$MANIFEST" ] || { echo "[FATAL] 资产清单不存在: $MANIFEST" >&2; exit 2; }

missing=0
different=0
same=0

while IFS= read -r raw || [ -n "$raw" ]; do
  base="${raw%%#*}"
  base="${base#"${base%%[![:space:]]*}"}"
  base="${base%"${base##*[![:space:]]}"}"
  [ -n "$base" ] || continue
  top="${base%%/*}"
  csv_contains "$ONLY" "$top" || continue
  is_excluded_rel "$base" && continue

  while IFS= read -r src; do
    rel="${src#$SOURCE/}"
    is_excluded_rel "$rel" && continue
    dest="$TARGET/$rel"
    if [ ! -e "$dest" ] && [ ! -L "$dest" ]; then
      echo "[MISS] $rel"
      missing=$((missing + 1))
    elif cmp -s "$src" "$dest"; then
      same=$((same + 1))
    else
      echo "[DIFF] $rel"
      different=$((different + 1))
    fi
  done < <(collect_files "$base")
done < "$MANIFEST"

echo "[INFO] same=$same diff=$different missing=$missing"

if [ "$different" -gt 0 ] || [ "$missing" -gt 0 ]; then
  exit 1
fi
