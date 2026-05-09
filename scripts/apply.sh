#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
BUILD=""
TARGET="$HOME/.codex"
PROFILE=""
DRY_RUN=0
OVERWRITE=0
BACKUP_ROOT=""
RUN_BUILD=1

usage() {
  cat <<'USAGE'
用法: scripts/apply.sh [options]

将 build/codex-home 安全注入到 ~/.codex。默认先执行 build。

Options:
  --root PATH        仓库根目录（默认：脚本所在仓库）
  --build PATH       构建目录（默认：<root>/build/codex-home）
  --target PATH      注入目标（默认：~/.codex）
  --profile NAME     构建 profile
  --no-build         不自动构建，直接使用现有 build
  --overwrite        已存在文件先备份再覆盖；默认保留已有普通文件
  --backup-root PATH 备份目录（默认：<root>/.backups/apply/<timestamp>）
  --dry-run          只预览，不写入
  -h, --help         显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --build) BUILD="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --no-build) RUN_BUILD=0; shift ;;
    --overwrite) OVERWRITE=1; shift ;;
    --backup-root) BACKUP_ROOT="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
BUILD="${BUILD:-$ROOT/build/codex-home}"
TARGET="${TARGET/#\~/$HOME}"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT/.backups/apply/$(date +%Y%m%d-%H%M%S)}"

if [ "$RUN_BUILD" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
  args=("--root" "$ROOT" "--build" "$BUILD")
  [ -z "$PROFILE" ] || args+=("--profile" "$PROFILE")
  "$ROOT/scripts/build.sh" "${args[@]}"
fi

python3 - "$ROOT" "$BUILD" "$TARGET" "$BACKUP_ROOT" "$DRY_RUN" "$OVERWRITE" <<'PY'
import filecmp
import fnmatch
import os
import pathlib
import shutil
import sys

root = pathlib.Path(sys.argv[1])
build = pathlib.Path(sys.argv[2])
target = pathlib.Path(sys.argv[3])
backup_root = pathlib.Path(sys.argv[4])
dry_run = sys.argv[5] == "1"
overwrite = sys.argv[6] == "1"
policies = __import__("json").loads((root / "manifests/policies.json").read_text())
protected = policies.get("protected_paths", [])
generated = {"skills/registry.csv", "control/state/active-profile.env", "control/state/managed-files.json"}

def fail(message):
    print(f"[FATAL] {message}", file=sys.stderr)
    raise SystemExit(2)

def is_match(rel):
    for pattern in protected:
        base = pattern[:-3] if pattern.endswith("/**") else pattern
        if rel == base or fnmatch.fnmatch(rel, pattern):
            return True
    return False

def run(label, fn=None):
    if dry_run:
        print(f"[DRY ] {label}")
    else:
        if fn:
            fn()

def backup(rel, dest):
    if not dest.exists() and not dest.is_symlink():
        return
    backup_dest = backup_root / rel
    def do_backup():
        backup_dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            if backup_dest.exists() or backup_dest.is_symlink():
                backup_dest.unlink()
            backup_dest.symlink_to(os.readlink(dest))
        elif dest.is_dir():
            if backup_dest.exists():
                shutil.rmtree(backup_dest)
            shutil.copytree(dest, backup_dest, symlinks=True)
        else:
            shutil.copy2(dest, backup_dest)
    run(f"backup {rel} -> {backup_dest}", do_backup)

def copy_path(src, dest, rel):
    if src.is_symlink():
        link_target = os.readlink(src)
        def do_copy():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                if dest.is_dir() and not dest.is_symlink():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            dest.symlink_to(link_target)
        run(f"link {rel} -> {link_target}", do_copy)
    elif src.is_dir():
        run(f"mkdir {rel}", lambda: dest.mkdir(parents=True, exist_ok=True))
    else:
        def do_copy():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        run(f"copy {rel}", do_copy)

if not build.is_dir():
    fail(f"构建目录不存在: {build}")
run(f"mkdir {target}", lambda: target.mkdir(parents=True, exist_ok=True))

copied = kept = skipped = 0
for src in sorted(build.rglob("*")):
    rel = src.relative_to(build).as_posix()
    if is_match(rel):
        print(f"[SKIP] {rel} (protected)")
        skipped += 1
        continue
    dest = target / rel
    if src.is_dir() and not src.is_symlink():
        copy_path(src, dest, rel)
        continue
    should_overwrite = overwrite or src.is_symlink() or rel in generated
    if dest.exists() or dest.is_symlink():
        if src.is_symlink() and dest.is_symlink() and os.readlink(src) == os.readlink(dest):
            kept += 1
            continue
        if not src.is_symlink() and src.is_file() and dest.is_file() and filecmp.cmp(src, dest, shallow=False):
            kept += 1
            continue
        if should_overwrite:
            backup(rel, dest)
            copy_path(src, dest, rel)
            copied += 1
        else:
            print(f"[KEEP] {rel} (exists)")
            kept += 1
    else:
        copy_path(src, dest, rel)
        copied += 1

print(f"[DONE] apply target={target} copied={copied} kept={kept} skipped={skipped} dry_run={int(dry_run)}")
PY
