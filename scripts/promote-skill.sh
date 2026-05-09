#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SOURCE=""
SKILL_PATH=""
NAME=""
VERSION=""
PROFILES="solo-dev|team-collab"
TAGS="custom"
OWNER="global"
REPLACE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法: scripts/promote-skill.sh <skill-path> --version VERSION [options]

将 inbox 或第三方目录中的 skill 归档到 assets/codex/vendor/skills，并更新 catalog/registry。

Options:
  --root PATH     仓库根目录（默认：脚本所在仓库）
  --source PATH   资产源目录（默认：<root>/assets/codex）
  --name NAME     覆盖 skill 名称（默认读取 SKILL.md frontmatter name 或目录名）
  --version VER   归档版本号（必填，语义化版本）
  --profiles LIST 启用 profile（默认：solo-dev|team-collab）
  --tags TAGS     catalog tags（默认：custom）
  --owner OWNER   registry owner（默认：global）
  --replace       若 catalog 中已存在同名 skill，替换该行
  --dry-run       只预览，不写入
  -h, --help      显示帮助

要求:
  - skill-path 必须包含 SKILL.md。
  - 不允许归档 skills/.system。
  - 归档目标不能已存在，除非使用 --replace 且目标版本目录不存在。
USAGE
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[DRY ] %s\n' "$*"
  else
    "$@"
  fi
}

fail() {
  echo "[FATAL] $*" >&2
  exit 2
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

normalize_name() {
  printf '%s\n' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'
}

validate_semver() {
  printf '%s\n' "$1" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$'
}

csv_has_skill() {
  local name="$1"
  local csv="$2"
  awk -F, -v n="$name" 'NR > 1 && $1 == n { found=1 } END { exit(found ? 0 : 1) }' "$csv"
}

update_skills_csv() {
  local csv="$1"
  local name="$2"
  local version="$3"
  local vendor_rel="$4"
  local profiles="$5"
  local tags="$6"
  local line
  line="$name,1,vendor,$version,$vendor_rel,skills/$name,$profiles,$tags"

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY ] update $csv: $line"
    return 0
  fi

  if csv_has_skill "$name" "$csv"; then
    [ "$REPLACE" -eq 1 ] || fail "catalog 已存在 skill: $name（如需替换，加 --replace）"
    tmp="$(mktemp)"
    awk -F, -v OFS=, -v n="$name" -v line="$line" 'NR == 1 { print; next } $1 == n { print line; next } { print }' "$csv" > "$tmp"
    mv "$tmp" "$csv"
  else
    printf '%s\n' "$line" >> "$csv"
  fi
}

update_registry_csv() {
  local csv="$1"
  local name="$2"
  local version="$3"
  local owner="$4"
  local line
  line="$name,$version,active,$owner"

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[DRY ] update $csv: $line"
    return 0
  fi

  if [ ! -f "$csv" ]; then
    printf 'name,version,status,owner\n' > "$csv"
  fi

  if csv_has_skill "$name" "$csv"; then
    [ "$REPLACE" -eq 1 ] || fail "registry 已存在 skill: $name（如需替换，加 --replace）"
    tmp="$(mktemp)"
    awk -F, -v OFS=, -v n="$name" -v line="$line" 'NR == 1 { print; next } $1 == n { print line; next } { print }' "$csv" > "$tmp"
    mv "$tmp" "$csv"
  else
    printf '%s\n' "$line" >> "$csv"
  fi
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

SKILL_PATH="$1"
shift

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
    --name)
      NAME="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --profiles)
      PROFILES="$2"
      shift 2
      ;;
    --tags)
      TAGS="$2"
      shift 2
      ;;
    --owner)
      OWNER="$2"
      shift 2
      ;;
    --replace)
      REPLACE=1
      shift
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
      fail "未知参数: $1"
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SOURCE="${SOURCE:-$ROOT/assets/codex}"
SOURCE="$(cd "$SOURCE" && pwd)"
SKILL_PATH="$(cd "$SKILL_PATH" && pwd)"

case "$SKILL_PATH" in
  */skills/.system|*/skills/.system/*)
    fail "拒绝归档系统 skill: $SKILL_PATH"
    ;;
esac

[ -f "$SKILL_PATH/SKILL.md" ] || fail "缺少 SKILL.md: $SKILL_PATH"
[ -n "$VERSION" ] || fail "必须提供 --version"
validate_semver "$VERSION" || fail "version 必须是语义化版本: $VERSION"

if [ -z "$NAME" ]; then
  NAME="$(frontmatter_value "$SKILL_PATH/SKILL.md" name || true)"
fi
[ -n "$NAME" ] || NAME="$(basename "$SKILL_PATH")"
NAME="$(normalize_name "$NAME")"
[ -n "$NAME" ] || fail "无法确定 skill name"

for required_key in name description; do
  value="$(frontmatter_value "$SKILL_PATH/SKILL.md" "$required_key" || true)"
  [ -n "$value" ] || fail "SKILL.md frontmatter 缺少 $required_key"
done

if [ -d "$SKILL_PATH/.git" ]; then
  fail "检测到内嵌 .git，请先移除: $SKILL_PATH/.git"
fi

if grep -R -nE '(sk-[A-Za-z0-9_-]{20,}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|api[_-]?key[[:space:]]*=)' "$SKILL_PATH" >/tmp/promote-skill-secret-scan.log 2>/dev/null; then
  cat /tmp/promote-skill-secret-scan.log >&2
  fail "疑似包含密钥或私钥，请先清理"
fi

VENDOR_REL="vendor/skills/$NAME/$VERSION"
DEST="$SOURCE/$VENDOR_REL"
SKILLS_CSV="$SOURCE/control/catalog/skills.csv"
REGISTRY_CSV="$SOURCE/skills/registry.csv"

[ -f "$SKILLS_CSV" ] || fail "catalog 不存在: $SKILLS_CSV"

if [ -e "$DEST" ]; then
  fail "目标版本目录已存在: $DEST"
fi

echo "[INFO] promote name=$NAME version=$VERSION"
echo "[INFO] source=$SKILL_PATH"
echo "[INFO] dest=$DEST"

run mkdir -p "$(dirname "$DEST")"
run cp -a "$SKILL_PATH" "$DEST"

update_skills_csv "$SKILLS_CSV" "$NAME" "$VERSION" "$VENDOR_REL" "$PROFILES" "$TAGS"
update_registry_csv "$REGISTRY_CSV" "$NAME" "$VERSION" "$OWNER"

echo "[DONE] promoted $NAME@$VERSION"
echo "[INFO] 建议执行: rtk bash scripts/apply-to-codex.sh --dry-run --activate-profile team-collab"
