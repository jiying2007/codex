#!/usr/bin/env bash
# install.sh — 新机器首次安装 / 迁移到新路径
#
# 用法：
#   control/scripts/install.sh                  # 使用脚本所在仓库根目录，profile=team-collab
#   control/scripts/install.sh [ROOT]           # 指定根目录，profile=team-collab
#   control/scripts/install.sh [ROOT] [profile] # 指定根目录和 profile
#
# 功能：
#   1. 将 ROOT 链接到 ~/.codex（可选，若 ~/.codex 已存在则跳过）
#   2. 激活指定 profile 的 skills / agents 软链接
#   3. 渲染 config.toml 的 MCP 托管区块
#   4. 运行体检（doctor.sh）
#   5. 输出下一步操作提示

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DEFAULT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "用法: $(basename "$0") [ROOT] [profile]"
  echo "  ROOT    仓库根目录（默认：脚本所在仓库根）"
  echo "  profile 激活的配置 profile（默认：team-collab）"
  echo ""
  echo "示例："
  echo "  $(basename "$0")                       # 使用当前仓库，team-collab"
  echo "  $(basename "$0") ~/codex               # 指定根目录"
  echo "  $(basename "$0") ~/codex solo-dev      # 指定根目录和 profile"
  exit 0
fi

ROOT="${1:-$ROOT_DEFAULT}"
PROFILE="${2:-team-collab}"

echo "================================================"
echo "  Codex Framework Install"
echo "  ROOT    : $ROOT"
echo "  PROFILE : $PROFILE"
echo "================================================"
echo ""

# ---- 1. ~/.codex 链接 ----
CODEX_HOME="$HOME/.codex"
if [ -L "$CODEX_HOME" ]; then
  current_target="$(readlink "$CODEX_HOME")"
  if [ "$current_target" = "$ROOT" ]; then
    echo "[OK] ~/.codex 已指向 $ROOT"
  else
    echo "[WARN] ~/.codex 当前指向 $current_target，非本仓库根目录"
    echo "       如需重定向，请手动执行："
    echo "       ln -sfn $ROOT $CODEX_HOME"
  fi
elif [ -d "$CODEX_HOME" ] && [ "$CODEX_HOME" != "$ROOT" ]; then
  echo "[INFO] ~/.codex 是实际目录（非软链接），跳过链接步骤"
  echo "       如需管理：此仓库自带脚本已使用 ROOT=$ROOT 运行"
elif [ ! -e "$CODEX_HOME" ]; then
  ln -sfn "$ROOT" "$CODEX_HOME"
  echo "[OK] 已创建 ~/.codex -> $ROOT"
fi

echo ""

# ---- 2. 同步 registry.csv ----
echo "[INFO] 同步 skills/registry.csv ..."
"$ROOT/control/scripts/gen-registry.sh" "$ROOT"
echo ""

# ---- 3. 激活 profile ----
echo "[INFO] 激活 profile: $PROFILE ..."
"$ROOT/control/scripts/activate-profile.sh" "$ROOT" "$PROFILE"
echo ""

# ---- 4. 体检 ----
echo "[INFO] 执行体检 ..."
if "$ROOT/control/scripts/doctor.sh" "$ROOT" "$PROFILE"; then
  echo ""
  echo "================================================"
  echo "  安装成功！"
  echo "================================================"
else
  echo ""
  echo "================================================"
  echo "  安装完成，但体检有错误，请检查上方输出"
  echo "================================================"
fi

echo ""
echo "下一步建议："
echo "  查看当前状态    : git -C $ROOT status"
echo "  切换 profile    : $ROOT/control/scripts/activate-profile.sh $ROOT <profile>"
echo "  体检            : $ROOT/control/scripts/doctor.sh $ROOT $PROFILE"
echo "  可用 profiles   : $(awk -F, 'NR>1{printf "%s ", $1}' "$ROOT/control/catalog/profiles.csv")"
