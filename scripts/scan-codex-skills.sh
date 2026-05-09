#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SOURCE=""
CODEX_HOME="$HOME/.codex"
INBOX=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法: scripts/scan-codex-skills.sh [options]

扫描 ~/.codex/skills 中尚未登记到资产仓库的 skill，复制到 inbox 等待审核。

Options:
  --root PATH       仓库根目录（默认：脚本所在仓库）
  --source PATH     资产源目录（默认：<root>/assets/codex）
  --codex-home PATH Codex 运行目录（默认：~/.codex）
  --inbox PATH      候选 skill 目录（默认：<root>/inbox/skills）
  --dry-run         只预览，不写入
  -h, --help        显示帮助

固定规则:
  - 跳过 skills/.system。
  - 跳过没有 SKILL.md 的目录。
  - 跳过已在 assets/codex/control/catalog/skills.csv 登记的 skill。
  - 跳过 symlink；profile 激活入口不是归档来源。
USAGE
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[DRY ] %s\n' "$*"
  else
    "$@"
  fi
}

csv_has_skill() {
  local name="$1"
  local csv="$2"
  awk -F, -v n="$name" 'NR > 1 && $1 == n { found=1 } END { exit(found ? 0 : 1) }' "$csv"
}

frontmatter_value() {
  local file="$1"
  local key="$2"
  awk -v key="$key" '
    BEGIN { in_fm=0 }
    /^---[[:space:]]*$/ {
      if (in_fm == 0) { in_fm=1; next }
      exit
    }
    in_fm == 1 && $0 ~ "^" key ":" {
      sub("^[^:]+:[[:space:]]*", "")
      gsub(/^"|"$/, "")
      print
      exit
    }
  ' "$file"
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
    --codex-home)
      CODEX_HOME="$2"
      shift 2
      ;;
    --inbox)
      INBOX="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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
CODEX_HOME="${CODEX_HOME/#\~/$HOME}"
INBOX="${INBOX:-$ROOT/inbox/skills}"

SKILLS_DIR="$CODEX_HOME/skills"
SKILLS_CSV="$SOURCE/control/catalog/skills.csv"
INTAKE_CSV="$SOURCE/control/catalog/skill-intake.csv"

[ -d "$SKILLS_DIR" ] || { echo "[FATAL] skills 目录不存在: $SKILLS_DIR" >&2; exit 2; }
[ -f "$SKILLS_CSV" ] || { echo "[FATAL] catalog 不存在: $SKILLS_CSV" >&2; exit 2; }

if [ "$DRY_RUN" -eq 0 ] && [ ! -f "$INTAKE_CSV" ]; then
  mkdir -p "$(dirname "$INTAKE_CSV")"
  printf 'name,source_path,inbox_path,detected_at,status,notes\n' > "$INTAKE_CSV"
fi

found=0
copied=0
timestamp="$(date '+%Y%m%d-%H%M%S')"
detected_at="$(date '+%Y-%m-%dT%H:%M:%S%z')"

while IFS= read -r skill_dir; do
  name="$(basename "$skill_dir")"

  case "$name" in
    .system|scripts)
      continue
      ;;
  esac

  if [ -L "$skill_dir" ]; then
    continue
  fi

  if [ ! -f "$skill_dir/SKILL.md" ]; then
    continue
  fi

  found=$((found + 1))

  fm_name="$(frontmatter_value "$skill_dir/SKILL.md" name || true)"
  [ -n "$fm_name" ] && name="$fm_name"

  if csv_has_skill "$name" "$SKILLS_CSV"; then
    echo "[KEEP] $name (registered)"
    continue
  fi

  dest="$INBOX/$name/$timestamp"
  echo "[NEW ] $name -> $dest"
  run mkdir -p "$dest"
  run cp -a "$skill_dir"/. "$dest"/
  if [ "$DRY_RUN" -eq 0 ]; then
    printf '%s,%s,%s,%s,%s,%s\n' "$name" "$skill_dir" "$dest" "$detected_at" "pending_review" "scan-codex-skills" >> "$INTAKE_CSV"
  fi
  copied=$((copied + 1))
done < <(find "$SKILLS_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

echo "[INFO] scanned=$found intake=$copied inbox=$INBOX"
