#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

ROOT="$ROOT_DEFAULT"
SCOPE="all"
BUILD=""
TARGET="$HOME/.codex"

usage() {
  cat <<'USAGE'
用法: scripts/doctor.sh [options]

检查 v2 Codex 资产仓库。

Options:
  --scope repo|build|live|all  检查范围（默认：all）
  --root PATH                  仓库根目录（默认：脚本所在仓库）
  --build PATH                 构建目录（默认：<root>/build/codex-home）
  --target PATH                运行目录（默认：~/.codex）
  -h, --help                   显示帮助
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scope) SCOPE="$2"; shift 2 ;;
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

for script in "$ROOT"/scripts/*.sh; do
  [ -f "$script" ] || continue
  bash -n "$script"
done

python3 - "$ROOT" "$BUILD" "$TARGET" "$SCOPE" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
build = pathlib.Path(sys.argv[2])
target = pathlib.Path(sys.argv[3])
scope = sys.argv[4]
errors = 0
warnings = 0

def error(message):
    global errors
    errors += 1
    print(f"[ERROR] {message}")

def warn(message):
    global warnings
    warnings += 1
    print(f"[WARN ] {message}")

def info(message):
    print(f"[INFO ] {message}")

def load(path):
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        error(f"manifest 无法读取: {path}: {exc}")
        return {}

def check_repo():
    info("scope=repo")
    if (root / "assets").exists():
        error("旧 assets/ 入口仍存在")
    for name in ["assets.json", "profiles.json", "skills.json", "agents.json", "policies.json"]:
        if not (root / "manifests" / name).is_file():
            error(f"缺少 manifest: {name}")
    assets = load(root / "manifests/assets.json")
    source = root / assets.get("source_root", "src/codex-home")
    if not source.is_dir():
        error(f"源资产目录不存在: {source}")
    for path in ["skills/.system", "auth.json", "sessions", "cache", "tmp", "log"]:
        if (source / path).exists():
            error(f"源资产包含受保护运行态路径: {path}")
    for old in ["scripts/apply-to-codex.sh", "scripts/diff-codex.sh", "scripts/doctor-assets.sh"]:
        if (root / old).exists():
            error(f"旧脚本入口仍存在: {old}")

def check_build():
    info("scope=build")
    if not build.is_dir():
        error(f"构建目录不存在: {build}")
        return
    state = build / "control/state/managed-files.json"
    if not state.is_file():
        error("build 缺少 control/state/managed-files.json")
    if (build / "skills/.system").exists():
        error("build 不应包含 skills/.system")
    skills = load(root / "manifests/skills.json").get("skills", [])
    profile_file = build / "control/state/active-profile.env"
    profile = "team-collab"
    if profile_file.is_file():
        for line in profile_file.read_text().splitlines():
            if line.startswith("PROFILE="):
                profile = line.split("=", 1)[1]
    for item in skills:
        if item.get("enabled", True) and profile in item.get("profiles", []):
            link = build / item["target_rel"]
            if not link.is_symlink():
                error(f"build skill 未激活为 symlink: {item['target_rel']}")

def check_live():
    info("scope=live")
    if not target.is_dir():
        error(f"运行目录不存在: {target}")
        return
    if not (target / "skills/.system").is_dir():
        warn("live 缺少 skills/.system；系统 skill 可能不可用")
    state = target / "control/state/managed-files.json"
    if not state.is_file():
        warn("live 缺少 managed-files.json；尚未通过 v2 apply 完整注入")
    profile_file = target / "control/state/active-profile.env"
    if profile_file.is_file():
        info(profile_file.read_text().strip())

if scope not in {"repo", "build", "live", "all"}:
    error(f"未知 scope: {scope}")
else:
    if scope in {"repo", "all"}:
        check_repo()
    if scope in {"build", "all"}:
        check_build()
    if scope in {"live", "all"}:
        check_live()

print(f"[INFO ] errors={errors} warnings={warnings}")
raise SystemExit(1 if errors else 0)
PY
