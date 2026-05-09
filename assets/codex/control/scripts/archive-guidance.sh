#!/usr/bin/env bash
set -euo pipefail

ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${1:-$ROOT_DEFAULT}"
SOURCE="${2:-$ROOT/control/knowledge/codex-dev-collab-guide.md}"
ARCHIVE_DIR="${3:-$ROOT/control/archives/guidance}"
INDEX_FILE="${4:-$ARCHIVE_DIR/index.md}"
SLUG="${5:-codex-dev-collab-guide}"

if [ ! -d "$ROOT" ]; then
  echo "[ERROR] 根目录不存在: $ROOT" >&2
  exit 2
fi

if [ ! -f "$SOURCE" ]; then
  echo "[ERROR] 源文档不存在: $SOURCE" >&2
  exit 2
fi

mkdir -p "$ARCHIVE_DIR"

timestamp="$(date '+%Y-%m-%d %H:%M:%S %z')"
date_only="$(date '+%Y-%m-%d')"
output_file="$ARCHIVE_DIR/${date_only}-${SLUG}.md"
if [ -e "$output_file" ]; then
  output_file="$ARCHIVE_DIR/${date_only}-$(date '+%H%M%S')-${SLUG}.md"
fi

summary_lines="$(awk '
  /^## / {
    sub(/^## /, "", $0)
    print "- " $0
  }
' "$SOURCE")"

{
  echo "# 归档快照：${SLUG}"
  echo
  echo "- 归档时间：${timestamp}"
  echo "- 来源文件：\`${SOURCE}\`"
  echo
  echo "## 自动摘要（按二级标题提取）"
  if [ -n "$summary_lines" ]; then
    echo "$summary_lines"
  else
    echo "- （未提取到二级标题）"
  fi
  echo
  echo "## 正文快照"
  echo
  cat "$SOURCE"
} > "$output_file"

if [ ! -f "$INDEX_FILE" ]; then
  cat > "$INDEX_FILE" <<'EOF'
# 指南归档索引

> 自动维护：`control/scripts/archive-guidance.sh`

| 归档时间 | 归档文件 |
| --- | --- |
EOF
fi

index_rel="${INDEX_FILE#"$ROOT/"}"
index_dir="$(dirname "$INDEX_FILE")"
latest_link="$index_dir/latest.md"
index_link_target="$(basename "$output_file")"

printf "| %s | [%s](%s) |\n" \
  "$timestamp" \
  "$(basename "$output_file")" \
  "$index_link_target" >> "$INDEX_FILE"

ln -sfn "$(basename "$output_file")" "$latest_link"

echo "[INFO] 归档完成"
echo "[INFO] 归档文件: $output_file"
echo "[INFO] 索引文件: $INDEX_FILE"
echo "[INFO] 最新快照: $latest_link -> $(basename "$output_file")"
echo "[INFO] 索引相对路径: $index_rel"
