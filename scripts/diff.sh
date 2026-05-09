#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
BUILD=""
TARGET="$HOME/.codex"

usage() {
  cat <<'USAGE'
用法: scripts/diff.sh [options]

对比 build/codex-home 与 ~/.codex 中的 managed 文件。

Options:
  --root PATH    仓库根目录（默认：脚本所在仓库）
  --build PATH   构建目录（默认：<root>/build/codex-home）
  --target PATH  目标目录（默认：~/.codex）
  -h, --help     显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --build) BUILD="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
BUILD="${BUILD:-$ROOT/build/codex-home}"
TARGET="${TARGET/#\~/$HOME}"

python3 - "$BUILD" "$TARGET" <<'PY'
import filecmp
import os
import pathlib
import sys

build = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
if not build.is_dir():
    print(f"[FATAL] 构建目录不存在: {build}", file=sys.stderr)
    raise SystemExit(2)

same = diff = missing = 0
for src in sorted(p for p in build.rglob("*") if p.is_file() or p.is_symlink()):
    rel = src.relative_to(build)
    dest = target / rel
    if not dest.exists() and not dest.is_symlink():
        print(f"[MISS] {rel.as_posix()}")
        missing += 1
    elif src.is_symlink():
        if dest.is_symlink() and os.readlink(src) == os.readlink(dest):
            same += 1
        else:
            print(f"[DIFF] {rel.as_posix()}")
            diff += 1
    elif dest.is_file() and filecmp.cmp(src, dest, shallow=False):
        same += 1
    else:
        print(f"[DIFF] {rel.as_posix()}")
        diff += 1

print(f"[INFO] same={same} diff={diff} missing={missing}")
raise SystemExit(1 if diff or missing else 0)
PY
