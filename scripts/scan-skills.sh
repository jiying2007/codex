#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
CODEX_HOME="$HOME/.codex"
INBOX=""
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法: scripts/scan-skills.sh [options]

扫描 ~/.codex/skills 中尚未登记到 manifests/skills.json 的真实 skill，复制到 inbox 等待审核。

Options:
  --root PATH       仓库根目录（默认：脚本所在仓库）
  --codex-home PATH Codex 运行目录（默认：~/.codex）
  --inbox PATH      候选 skill 目录（默认：<root>/inbox/skills）
  --dry-run         只预览，不写入
  -h, --help        显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --codex-home) CODEX_HOME="$2"; shift 2 ;;
    --inbox) INBOX="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
CODEX_HOME="${CODEX_HOME/#\~/$HOME}"
INBOX="${INBOX:-$ROOT/inbox/skills}"

python3 - "$ROOT" "$CODEX_HOME" "$INBOX" "$DRY_RUN" <<'PY'
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime

root = pathlib.Path(sys.argv[1])
codex_home = pathlib.Path(sys.argv[2])
inbox = pathlib.Path(sys.argv[3])
dry_run = sys.argv[4] == "1"
skills_dir = codex_home / "skills"
manifest = root / "manifests/skills.json"

if not skills_dir.is_dir():
    print(f"[FATAL] skills 目录不存在: {skills_dir}", file=sys.stderr)
    raise SystemExit(2)

registered = {item["name"] for item in json.loads(manifest.read_text()).get("skills", [])}

def frontmatter_name(path):
    text = path.read_text(errors="ignore")
    match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""

found = copied = 0
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
for skill in sorted(skills_dir.iterdir(), key=lambda p: p.name):
    if skill.name in {".system", "scripts"} or skill.is_symlink() or not skill.is_dir():
        continue
    if not (skill / "SKILL.md").is_file():
        continue
    found += 1
    name = frontmatter_name(skill / "SKILL.md") or skill.name
    if name in registered:
        print(f"[KEEP] {name} (registered)")
        continue
    dest = inbox / name / timestamp
    print(f"[NEW ] {name} -> {dest}")
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, dest)
    copied += 1

print(f"[INFO] scanned={found} intake={copied} inbox={inbox}")
PY
