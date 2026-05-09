#!/usr/bin/env bash
set -euo pipefail

ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="$ROOT_DEFAULT"
PROFILE=""
RENDER_CONFIG="1"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "用法: $(basename "$0") [ROOT] <profile> [--no-render]"
  exit 0
fi

if [ "$#" -eq 1 ]; then
  PROFILE="${1:-}"
elif [ "$#" -ge 2 ] && [ -d "${1:-}" ]; then
  ROOT="$1"
  PROFILE="$2"
elif [ "$#" -ge 2 ]; then
  PROFILE="$1"
fi

if [ -z "$PROFILE" ]; then
  echo "用法: $(basename "$0") [ROOT] <profile> [--no-render]" >&2
  exit 2
fi

for arg in "$@"; do
  if [ "$arg" = "--no-render" ]; then
    RENDER_CONFIG="0"
  fi
done

CATALOG_DIR="$ROOT/control/catalog"
SKILLS_CSV="$CATALOG_DIR/skills.csv"
AGENTS_CSV="$CATALOG_DIR/agents.csv"
PROFILES_CSV="$CATALOG_DIR/profiles.csv"
STATE_DIR="$ROOT/control/state"
mkdir -p "$STATE_DIR"

if [ ! -f "$PROFILES_CSV" ] || [ ! -f "$SKILLS_CSV" ] || [ ! -f "$AGENTS_CSV" ]; then
  echo "[ERROR] catalog 不完整，请检查 $CATALOG_DIR" >&2
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

ensure_profile_exists() {
  local found="0"
  while IFS=, read -r name _rest; do
    [ "$name" = "name" ] && continue
    [ -z "$name" ] && continue
    if [ "$name" = "$PROFILE" ]; then
      found="1"
      break
    fi
  done < "$PROFILES_CSV"
  if [ "$found" != "1" ]; then
    echo "[ERROR] profile 不存在: $PROFILE" >&2
    exit 2
  fi
}

backup_existing() {
  local path="$1"
  local backup_root="$STATE_DIR/backup/$(date '+%Y%m%d-%H%M%S')"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    mkdir -p "$backup_root"
    local name
    name="$(basename "$path")"
    mv "$path" "$backup_root/$name"
    echo "[INFO] 备份现有目录: $path -> $backup_root/$name"
  fi
}

relink_targets() {
  local csv="$1"
  local section="$2"
  local line
  local enabled
  local vendor_rel
  local target_rel
  local profiles
  local source_abs
  local target_abs

  declare -A wanted=()
  declare -A managed=()

  while IFS=, read -r _name enabled _source_kind _version vendor_rel target_rel profiles _rest; do
    [ -z "$target_rel" ] && continue
    [ "$target_rel" = "target_rel" ] && continue
    managed["$target_rel"]="1"

    if [ "$enabled" != "1" ]; then
      continue
    fi

    if ! has_profile "$profiles" "$PROFILE"; then
      continue
    fi

    wanted["$target_rel"]="$vendor_rel"
  done < "$csv"

  for target_rel in "${!managed[@]}"; do
    target_abs="$ROOT/$target_rel"

    if [ -n "${wanted[$target_rel]+x}" ]; then
      source_abs="$ROOT/${wanted[$target_rel]}"

      if [ ! -e "$source_abs" ]; then
        echo "[WARN] 缺少源路径($section): $source_abs"
        continue
      fi

      mkdir -p "$(dirname "$target_abs")"

      if [ -L "$target_abs" ]; then
        local current
        current="$(readlink "$target_abs")"
        if [ "$current" = "$source_abs" ]; then
          continue
        fi
        rm -f "$target_abs"
      fi

      backup_existing "$target_abs"
      ln -sfn "$source_abs" "$target_abs"
      echo "[INFO] 激活 $section: $target_rel -> $source_abs"
    else
      if [ -L "$target_abs" ]; then
        rm -f "$target_abs"
        echo "[INFO] 停用 $section: $target_rel"
      fi
    fi
  done
}

ensure_profile_exists
relink_targets "$SKILLS_CSV" "skill"
relink_targets "$AGENTS_CSV" "agent"

cat > "$STATE_DIR/active-profile.env" <<STATE
PROFILE=$PROFILE
UPDATED_AT=$(date '+%Y-%m-%d %H:%M:%S %z')
STATE

echo "[INFO] 当前 profile: $PROFILE"

if [ "$RENDER_CONFIG" = "1" ]; then
  "$ROOT/control/scripts/render-config.sh" "$ROOT" "$PROFILE"
fi
