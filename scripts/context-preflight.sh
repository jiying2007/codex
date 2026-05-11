#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-}"

if [[ -z "$OUT" ]]; then
  TS="$(rtk date +%Y%m%d-%H%M%S | tr -d '\r\n')"
  OUT="scratch/${TS}-context-preflight.md"
fi

OUT_PATH="$(rtk realpath -m "$OUT")"
OUT_DIR="$(rtk dirname "$OUT_PATH")"
rtk mkdir -p "$OUT_DIR"

REPO_ROOT="$(rtk git rev-parse --show-toplevel 2>/dev/null || rtk pwd)"
BRANCH="$(rtk git branch --show-current 2>/dev/null || true)"
STATUS="$(rtk git status --short 2>/dev/null || true)"
DIFF_STAT="$(rtk git diff --stat 2>/dev/null || true)"
RECENT_LOG="$(rtk git log --oneline -5 2>/dev/null || true)"

{
  printf "%s\n\n" "# Context Compression Preflight"
  printf "%s\n" "## 目标"
  printf "%s\n" "- 本轮目标："
  printf "%s\n\n" "- 期望输出："

  printf "%s\n" "## 当前状态"
  printf -- "- 仓库：%s\n" "$REPO_ROOT"
  printf -- "- 分支：%s\n" "${BRANCH:-unknown}"
  printf "%s\n" "- 关键文件："
  printf "%s\n" "- 已完成："
  printf "%s\n\n" "- 未完成："

  printf "%s\n\n" "### 工作区状态"
  printf "%s\n%s\n%s\n\n" '```text' "${STATUS:-<empty>}" '```'

  printf "%s\n\n" "### 变更规模"
  printf "%s\n%s\n%s\n\n" '```text' "${DIFF_STAT:-<empty>}" '```'

  printf "%s\n\n" "### 最近提交"
  printf "%s\n%s\n%s\n\n" '```text' "${RECENT_LOG:-<empty>}" '```'

  printf "%s\n" "## 关键决策（只保留可复用）"
  printf "%s\n" "- 决策 1："
  printf "%s\n\n" "- 决策 2："

  printf "%s\n" "## 自动结晶（Crystallized Insights）"
  printf "%s\n" "- Insight 1："
  printf "%s\n" "- 为什么重要："
  printf "%s\n\n" "- 是否应提升到 AGENTS / archive / memory："

  printf "%s\n" "## 未决张力（Open Tensions）"
  printf "%s\n" "- Tension 1："
  printf "%s\n" "- 为什么还没闭环："
  printf "%s\n\n" "- 下次恢复时先验证什么："

  printf "%s\n" "## 约束与风险"
  printf "%s\n" "- 约束："
  printf "%s\n\n" "- 风险："

  printf "%s\n" "## 下一步（可执行）"
  printf "%s\n" "- Step 1:"
  printf "%s\n" "- Step 2:"
  printf "%s\n\n" "- Step 3:"

  printf "%s\n" "## 验证命令"
  printf "%s\n" "- \`rtk bash scripts/check.sh\`"
  printf "%s\n\n" "- \`rtk git diff --check\`"

  printf "%s\n" "## 恢复提示（Resume Prompt）"
  printf "%s\n" "继续处理：<一句话任务>"
  printf "%s\n" "从这些文件继续：<path1>, <path2>"
  printf "%s\n" "先执行：<第一条命令>"
} > "$OUT_PATH"

printf "[DONE] context-preflight=%s\n" "$OUT_PATH"
