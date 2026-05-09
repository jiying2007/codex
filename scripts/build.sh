#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
PROFILE=""
SOURCE=""
BUILD=""

usage() {
  cat <<'USAGE'
用法: scripts/build.sh [options]

从 src/codex-home 与 manifests 生成 build/codex-home。

Options:
  --root PATH       仓库根目录（默认：脚本所在仓库）
  --profile NAME    构建 profile（默认：manifests/assets.json default_profile）
  --source PATH     源资产目录（默认：<root>/src/codex-home）
  --build PATH      构建输出目录（默认：<root>/build/codex-home）
  -h, --help        显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --build) BUILD="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] 未知参数: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SOURCE="${SOURCE:-$ROOT/src/codex-home}"
BUILD="${BUILD:-$ROOT/build/codex-home}"

python3 - "$ROOT" "$SOURCE" "$BUILD" "$PROFILE" <<'PY'
import csv
import fnmatch
import hashlib
import json
import os
import pathlib
import shutil
import sys

root = pathlib.Path(sys.argv[1])
source = pathlib.Path(sys.argv[2])
build = pathlib.Path(sys.argv[3])
profile_arg = sys.argv[4]
manifests = root / "manifests"

def fail(message):
    print(f"[FATAL] {message}", file=sys.stderr)
    raise SystemExit(2)

def load(name):
    path = manifests / name
    if not path.is_file():
        fail(f"manifest 不存在: {path}")
    return json.loads(path.read_text())

assets = load("assets.json")
policies = load("policies.json")
skills = load("skills.json")["skills"]
agents = load("agents.json")["agents"]
profiles = load("profiles.json")["profiles"]

profile = profile_arg or assets.get("default_profile") or "team-collab"
profile_names = {item["name"] for item in profiles}
if profile not in profile_names:
    fail(f"profile 未定义: {profile}")
if not source.is_dir():
    fail(f"源资产目录不存在: {source}")

protected = policies.get("protected_paths", [])
skip_source = policies.get("skip_source_paths", [])

def is_match(rel, patterns):
    rel = rel.as_posix() if isinstance(rel, pathlib.Path) else str(rel)
    for pattern in patterns:
        base = pattern[:-3] if pattern.endswith("/**") else pattern
        if rel == base or fnmatch.fnmatch(rel, pattern):
            return True
    return False

def copy_entry(src, dst, rel):
    if is_match(rel, protected) or is_match(rel, skip_source):
        return
    if src.is_symlink():
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir(), key=lambda p: p.name):
            copy_entry(child, dst / child.name, rel / child.name)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

if build.exists() or build.is_symlink():
    shutil.rmtree(build)
build.mkdir(parents=True)

for rel_text in assets.get("copy_roots", []):
    rel = pathlib.Path(rel_text)
    copy_entry(source / rel, build / rel, rel)

def active(item):
    return item.get("enabled", True) and profile in item.get("profiles", [])

def replace_with_symlink(link, target):
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    rel_target = os.path.relpath(target, start=link.parent)
    link.symlink_to(rel_target)

for item in skills:
    if not active(item):
        continue
    src_rel = pathlib.Path(item["vendor_rel"])
    dst_rel = pathlib.Path(item["target_rel"])
    src_path = build / src_rel
    if not src_path.exists():
        fail(f"skill 源不存在: {src_rel}")
    replace_with_symlink(build / dst_rel, src_path)

for item in agents:
    if not active(item):
        continue
    src_rel = pathlib.Path(item["vendor_rel"])
    dst_rel = pathlib.Path(item["target_rel"])
    src_path = build / src_rel
    if not src_path.exists():
        fail(f"agent 源不存在: {src_rel}")
    replace_with_symlink(build / dst_rel, src_path)

registry_path = build / "skills/registry.csv"
registry_path.parent.mkdir(parents=True, exist_ok=True)
with registry_path.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["name", "version", "status", "owner"])
    for item in skills:
        if active(item):
            writer.writerow([item["name"], item.get("version", ""), "active", item.get("source_kind", "managed")])

state_dir = build / "control/state"
state_dir.mkdir(parents=True, exist_ok=True)
(state_dir / "active-profile.env").write_text(f"PROFILE={profile}\n")

managed = []
for path in sorted(build.rglob("*")):
    rel = path.relative_to(build).as_posix()
    if is_match(rel, protected):
        continue
    if path.is_symlink():
        managed.append({"path": rel, "type": "symlink", "target": os.readlink(path)})
    elif path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        managed.append({"path": rel, "type": "file", "sha256": digest})
    elif path.is_dir():
        managed.append({"path": rel, "type": "dir"})

(state_dir / "managed-files.json").write_text(json.dumps({
    "schema_version": 2,
    "profile": profile,
    "source": str(source),
    "managed": managed,
}, ensure_ascii=False, indent=2) + "\n")

print(f"[DONE] build profile={profile} output={build} managed={len(managed)}")
PY
