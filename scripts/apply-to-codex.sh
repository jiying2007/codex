#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SOURCE=""
TARGET="$HOME/.codex"
MANIFEST=""
DRY_RUN=0
OVERWRITE=0
BACKUP=1
ONLY=""
BACKUP_ROOT=""
ACTIVATE_PROFILE=""

usage() {
  cat <<'USAGE'
用法: scripts/apply-to-codex.sh [options]

将当前仓库中登记的 Codex 资产安全注入到 ~/.codex。

Options:
  --root PATH        源仓库根目录（默认：脚本所在仓库）
  --source PATH      资产源目录（默认：<root>/assets/codex）
  --target PATH      注入目标目录（默认：~/.codex）
  --manifest PATH    资产清单（默认：<source>/control/catalog/assets.txt）
  --only LIST        只注入逗号分隔的顶层路径，如 skills,prompts,vendor
  --overwrite        已存在文件先备份再覆盖；默认跳过已存在文件
  --no-backup        覆盖时不备份（不推荐）
  --backup-root PATH 备份根目录（默认：<root>/.backups/apply-to-codex/<timestamp>）
  --activate-profile PROFILE
                     注入后在目标目录激活 profile，并渲染 config
  --dry-run          只预览，不写入
  -h, --help         显示帮助

固定规则:
  - 始终跳过 skills/.system，以 ~/.codex 中已有系统技能为准。
  - 始终跳过 symlink；profile 激活链接应由 control/scripts/activate-profile.sh 生成。
  - 始终跳过 secrets、sessions、logs、cache、tmp、state、.git 等运行时/本机文件。
  - 目录采用递归合并，不整体替换目标目录。
USAGE
}

log() {
  printf '%s\n' "$*"
}

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[DRY ] %s\n' "$*"
  else
    "$@"
  fi
}

fail() {
  printf '[FATAL] %s\n' "$*" >&2
  exit 2
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
    if [ "$part" = "$item" ]; then
      return 0
    fi
  done
  return 1
}

is_excluded_rel() {
  local rel="$1"
  case "$rel" in
    .|""|.git|.git/*|.codex|.codex/*|.tmp|.tmp/*|tmp|tmp/*|cache|cache/*|log|log/*|sessions|sessions/*|shell_snapshots|shell_snapshots/*|memories|memories/*)
      return 0
      ;;
    auth.json|history.jsonl|installation_id|models_cache.json|session_index.jsonl|version.json|tasks.codex.json)
      return 0
      ;;
    logs_*.sqlite|logs_*.sqlite-shm|logs_*.sqlite-wal|state_*.sqlite|state_*.sqlite-shm|state_*.sqlite-wal)
      return 0
      ;;
    skills/.system|skills/.system/*)
      return 0
      ;;
    mcp/secrets|mcp/secrets/*)
      return 0
      ;;
    control/state/active-profile.env|control/state/backup|control/state/backup/*|control/generated/config-managed.toml)
      return 0
      ;;
    *.secret|*.key|*.pem|config.local.*)
      return 0
      ;;
  esac
  return 1
}

ensure_safe_rel() {
  local rel="$1"
  case "$rel" in
    ""|/*|*..*)
      fail "不安全的相对路径: $rel"
      ;;
  esac
}

backup_existing() {
  local rel="$1"
  local dest="$2"

  [ "$BACKUP" -eq 1 ] || return 0
  [ -e "$dest" ] || [ -L "$dest" ] || return 0
  [ -n "$BACKUP_ROOT" ] || fail "BACKUP_ROOT 未设置"

  local backup_dest="$BACKUP_ROOT/$rel"
  run mkdir -p "$(dirname "$backup_dest")"
  run cp -a "$dest" "$backup_dest"
  log "[BACK] $rel -> $backup_dest"
}

copy_one() {
  local rel="$1"
  local src="$SOURCE/$rel"
  local dest="$TARGET/$rel"

  ensure_safe_rel "$rel"

  if is_excluded_rel "$rel"; then
    log "[SKIP] $rel (excluded)"
    return 0
  fi

  if [ ! -e "$src" ] && [ ! -L "$src" ]; then
    log "[WARN] $rel (source missing)"
    return 0
  fi

  if [ -L "$src" ]; then
    log "[SKIP] $rel (symlink)"
    return 0
  fi

  if [ -d "$src" ]; then
    run mkdir -p "$dest"
    return 0
  fi

  run mkdir -p "$(dirname "$dest")"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if [ "$OVERWRITE" -eq 1 ]; then
      backup_existing "$rel" "$dest"
      run cp -a "$src" "$dest"
      log "[COPY] $rel (overwritten)"
    else
      log "[KEEP] $rel (exists)"
    fi
  else
    run cp -a "$src" "$dest"
    log "[COPY] $rel"
  fi
}

copy_tree() {
  local base="$1"
  local top

  ensure_safe_rel "$base"
  top="${base%%/*}"
  if ! csv_contains "$ONLY" "$top"; then
    log "[SKIP] $base (--only)"
    return 0
  fi

  if is_excluded_rel "$base"; then
    log "[SKIP] $base (excluded)"
    return 0
  fi

  if [ ! -e "$SOURCE/$base" ] && [ ! -L "$SOURCE/$base" ]; then
    log "[WARN] $base (source missing)"
    return 0
  fi

  if [ -L "$SOURCE/$base" ]; then
    copy_one "$base"
  elif [ -d "$SOURCE/$base" ]; then
    copy_one "$base"
    while IFS= read -r path; do
      rel="${path#$SOURCE/}"
      copy_one "$rel"
    done < <(
      find "$SOURCE/$base" \
        \( -path "$SOURCE/skills/.system" -o -path "$SOURCE/mcp/secrets" -o -path "$SOURCE/control/state/backup" \) -prune \
        -o \( -type d -o -type f -o -type l \) -print | sort
    )
  else
    copy_one "$base"
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
    --overwrite)
      OVERWRITE=1
      shift
      ;;
    --no-backup)
      BACKUP=0
      shift
      ;;
    --backup-root)
      BACKUP_ROOT="$2"
      shift 2
      ;;
    --activate-profile|--profile)
      ACTIVATE_PROFILE="$2"
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
      fail "未知参数: $1"
      ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SOURCE="${SOURCE:-$ROOT/assets/codex}"
SOURCE="$(cd "$SOURCE" && pwd)"
TARGET="${TARGET/#\~/$HOME}"
MANIFEST="${MANIFEST:-$SOURCE/control/catalog/assets.txt}"

[ -f "$MANIFEST" ] || fail "资产清单不存在: $MANIFEST"

if [ -z "$BACKUP_ROOT" ]; then
  BACKUP_ROOT="$ROOT/.backups/apply-to-codex/$(date +%Y%m%d-%H%M%S)"
fi

log "================================================"
log "  Codex Asset Apply"
log "  ROOT     : $ROOT"
log "  SOURCE   : $SOURCE"
log "  TARGET   : $TARGET"
log "  MANIFEST : $MANIFEST"
log "  MODE     : $([ "$OVERWRITE" -eq 1 ] && echo overwrite || echo keep-existing)"
log "  DRY_RUN  : $DRY_RUN"
log "================================================"

run mkdir -p "$TARGET"

while IFS= read -r raw || [ -n "$raw" ]; do
  rel="${raw%%#*}"
  rel="${rel#"${rel%%[![:space:]]*}"}"
  rel="${rel%"${rel##*[![:space:]]}"}"
  [ -n "$rel" ] || continue
  copy_tree "$rel"
done < "$MANIFEST"

if [ -n "$ACTIVATE_PROFILE" ]; then
  log ""
  log "[INFO] 激活目标 profile: $ACTIVATE_PROFILE"
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[DRY ] $TARGET/control/scripts/gen-registry.sh $TARGET"
    log "[DRY ] $TARGET/control/scripts/activate-profile.sh $TARGET $ACTIVATE_PROFILE"
  elif [ -x "$TARGET/control/scripts/gen-registry.sh" ] && [ -x "$TARGET/control/scripts/activate-profile.sh" ]; then
    "$TARGET/control/scripts/gen-registry.sh" "$TARGET"
    "$TARGET/control/scripts/activate-profile.sh" "$TARGET" "$ACTIVATE_PROFILE"
  else
    log "[WARN] 目标目录缺少可执行 profile 激活脚本，跳过激活"
  fi
fi

if [ "$DRY_RUN" -eq 0 ] && [ -x "$TARGET/skills/scripts/check-skills.sh" ]; then
  log ""
  log "[INFO] 运行目标 skills 自检 ..."
  "$TARGET/skills/scripts/check-skills.sh" "$TARGET/skills" || log "[WARN] skills 自检失败，请检查上方输出"
fi

log ""
log "[DONE] 注入流程完成"
if [ "$OVERWRITE" -eq 1 ] && [ "$BACKUP" -eq 1 ]; then
  log "[INFO] 覆盖备份目录: $BACKUP_ROOT"
fi
