#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
TARGET="$HOME/.codex"
BACKUP_ROOT=""

usage() {
  cat <<'USAGE'
用法: scripts/backup.sh [options]

备份当前 ~/.codex 到仓库 .backups 目录，排除运行态缓存。

Options:
  --root PATH        仓库根目录（默认：脚本所在仓库）
  --target PATH      要备份的 Codex 目录（默认：~/.codex）
  --backup-root PATH 备份输出目录（默认：<root>/.backups/codex-home/<timestamp>）
  -h, --help         显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --backup-root) BACKUP_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
TARGET="${TARGET/#\~/$HOME}"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT/.backups/codex-home/$(date +%Y%m%d-%H%M%S)}"

[ -d "$TARGET" ] || { echo "[FATAL] 目标目录不存在: $TARGET" >&2; exit 2; }
mkdir -p "$BACKUP_ROOT"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.git/' \
    --exclude 'cache/' \
    --exclude 'log/' \
    --exclude 'sessions/' \
    --exclude 'shell_snapshots/' \
    --exclude 'tmp/' \
    --exclude '.tmp/' \
    --exclude 'logs_*.sqlite*' \
    --exclude 'state_*.sqlite*' \
    "$TARGET"/ "$BACKUP_ROOT"/
else
  cp -a "$TARGET"/. "$BACKUP_ROOT"/
fi

echo "[DONE] backup: $BACKUP_ROOT"
