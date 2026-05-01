#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SKILLS_DIR="$ROOT/skills"
VENDOR_DIR="$ROOT/vendor/skills"
PLUGINS_CSV="$ROOT/control/catalog/plugins.csv"
BACKUP_DIR="$ROOT/control/state/backup/sync-$(date '+%Y%m%d-%H%M%S')"
backup_created="0"

mkdir -p "$VENDOR_DIR"

ensure_backup_dir() {
  if [ "$backup_created" != "1" ]; then
    mkdir -p "$BACKUP_DIR"
    backup_created="1"
  fi
}

cleanup_root_plugin_entries() {
  if [ ! -f "$PLUGINS_CSV" ]; then
    return
  fi

  local pname enabled entry backup_name
  while IFS=, read -r pname _version _kind _source_path _vendor_path enabled _notes; do
    [ "$pname" = "name" ] && continue
    [ "$enabled" = "1" ] || continue

    entry="$ROOT/$pname"
    if [ ! -e "$entry" ] && [ ! -L "$entry" ]; then
      continue
    fi

    if [ -L "$entry" ] || [ -f "$entry" ]; then
      rm -f "$entry"
      echo "[INFO] 已清理根目录第三方入口: $pname"
      continue
    fi

    if [ -d "$entry" ]; then
      ensure_backup_dir
      backup_name="root-plugin-$pname"
      mv "$entry" "$BACKUP_DIR/$backup_name"
      echo "[WARN] 根目录第三方目录已移入备份: $BACKUP_DIR/$backup_name"
    fi
  done < "$PLUGINS_CSV"
}

cleanup_root_plugin_entries

for path in "$SKILLS_DIR"/*; do
  [ -e "$path" ] || continue
  name="$(basename "$path")"

  case "$name" in
    .system|scripts) continue ;;
  esac

  if [ -L "$path" ]; then
    echo "[INFO] 已是软链接，跳过: skills/$name"
    continue
  fi

  if [ ! -d "$path" ]; then
    continue
  fi

  version="0.0.0"
  if [ -f "$path/SKILL.md" ]; then
    parsed="$(sed -n 's/^version:[[:space:]]*//p' "$path/SKILL.md" | head -n1 | tr -d '"' | xargs || true)"
    if [ -n "$parsed" ]; then
      version="$parsed"
    fi
  fi

  target="$VENDOR_DIR/$name/$version"
  mkdir -p "$(dirname "$target")"

  if [ -e "$target" ]; then
    ensure_backup_dir
    mv "$path" "$BACKUP_DIR/$name"
    ln -sfn "$target" "$path"
    echo "[INFO] 已同步: skills/$name -> vendor/skills/$name/$version（原目录已备份）"
    continue
  fi

  mv "$path" "$target"
  ln -sfn "$target" "$path"
  echo "[INFO] 已同步: skills/$name -> vendor/skills/$name/$version"
done

if [ ! -f "$ROOT/vendor/README.md" ]; then
  cat > "$ROOT/vendor/README.md" <<'DOC'
# vendor 目录

第三方能力实体统一放在 `vendor/`，根目录不保留第三方入口链接。
`skills/` 与 `agents/` 仅通过软链接激活。

- `vendor/skills/`：技能实体（按 name/version 分层）
- `vendor/agents/`：代理定义实体
- `vendor/plugins/`：外部插件镜像入口
- `vendor/lock/`：版本锁与来源记录
DOC
fi
