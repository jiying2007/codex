#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SKILL_PATH=""
NAME=""
VERSION=""
PROFILES="solo-dev,team-collab"
TAGS="custom"
OWNER="global"
REPLACE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
用法: scripts/promote-skill.sh <skill-path> --version VERSION [options]

将 inbox 或第三方目录中的 skill 归档到 src/codex-home/vendor/skills，并更新 manifests/skills.json。

Options:
  --root PATH       仓库根目录（默认：脚本所在仓库）
  --name NAME       覆盖 skill 名称（默认读取 SKILL.md frontmatter name 或目录名）
  --version VER     归档版本号（必填，语义化版本）
  --profiles LIST   启用 profile，逗号或 | 分隔（默认：solo-dev,team-collab）
  --tags LIST       tags，逗号或 | 分隔（默认：custom）
  --owner OWNER     owner 元数据（默认：global）
  --replace         替换 manifests/skills.json 中同名条目
  --dry-run         只预览，不写入
  -h, --help        显示帮助
USAGE
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

SKILL_PATH="$1"
shift

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --profiles) PROFILES="$2"; shift 2 ;;
    --tags) TAGS="$2"; shift 2 ;;
    --owner) OWNER="$2"; shift 2 ;;
    --replace) REPLACE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SKILL_PATH="$(cd "$SKILL_PATH" && pwd)"

python3 - "$ROOT" "$SKILL_PATH" "$NAME" "$VERSION" "$PROFILES" "$TAGS" "$OWNER" "$REPLACE" "$DRY_RUN" <<'PY'
import json
import pathlib
import re
import shutil
import sys

root = pathlib.Path(sys.argv[1])
skill_path = pathlib.Path(sys.argv[2])
name_arg = sys.argv[3]
version = sys.argv[4]
profiles_arg = sys.argv[5]
tags_arg = sys.argv[6]
owner = sys.argv[7]
replace = sys.argv[8] == "1"
dry_run = sys.argv[9] == "1"

def fail(message):
    print(f"[FATAL] {message}", file=sys.stderr)
    raise SystemExit(2)

def split_list(value):
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]

def frontmatter_value(path, key):
    text = path.read_text(errors="ignore")
    match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""

def normalize(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

if "/skills/.system" in str(skill_path):
    fail(f"拒绝归档系统 skill: {skill_path}")
if not (skill_path / "SKILL.md").is_file():
    fail(f"缺少 SKILL.md: {skill_path}")
if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$", version):
    fail(f"version 必须是语义化版本: {version}")
if (skill_path / ".git").exists():
    fail(f"检测到内嵌 .git，请先移除: {skill_path / '.git'}")

text = "\n".join(p.read_text(errors="ignore") for p in skill_path.rglob("*") if p.is_file() and p.stat().st_size < 2_000_000)
if re.search(r"(sk-[A-Za-z0-9_-]{20,}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|api[_-]?key\s*=)", text):
    fail("疑似包含密钥或私钥，请先清理")

name = normalize(name_arg or frontmatter_value(skill_path / "SKILL.md", "name") or skill_path.name)
if not name:
    fail("无法确定 skill name")
for required in ["name", "description"]:
    if not frontmatter_value(skill_path / "SKILL.md", required):
        fail(f"SKILL.md frontmatter 缺少 {required}")

vendor_rel = f"vendor/skills/{name}/{version}"
dest = root / "src/codex-home" / vendor_rel
manifest_path = root / "manifests/skills.json"
manifest = json.loads(manifest_path.read_text())
items = manifest.setdefault("skills", [])
exists = [item for item in items if item.get("name") == name]
if exists and not replace:
    fail(f"manifest 已存在 skill: {name}（如需替换，加 --replace）")
if dest.exists():
    fail(f"目标版本目录已存在: {dest}")

entry = {
    "name": name,
    "enabled": True,
    "source_kind": "vendor",
    "version": version,
    "vendor_rel": vendor_rel,
    "target_rel": f"skills/{name}",
    "profiles": split_list(profiles_arg),
    "tags": split_list(tags_arg),
    "owner": owner,
}

print(f"[INFO] promote name={name} version={version}")
print(f"[INFO] source={skill_path}")
print(f"[INFO] dest={dest}")
if dry_run:
    print(f"[DRY ] copy {skill_path} -> {dest}")
    print(f"[DRY ] update {manifest_path}")
else:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_path, dest)
    items[:] = [item for item in items if item.get("name") != name]
    items.append(entry)
    items.sort(key=lambda item: item["name"])
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

print(f"[DONE] promoted {name}@{version}")
print("[INFO] 建议执行: rtk bash scripts/build.sh && rtk bash scripts/doctor.sh --scope build")
PY
