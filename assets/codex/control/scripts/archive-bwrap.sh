#!/usr/bin/env bash
set -euo pipefail

ROOT_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT="${1:-$ROOT_DEFAULT}"
ARCHIVE_DIR="${2:-$ROOT/control/archives/knowledge/bwrap}"
INDEX_FILE="${3:-$ARCHIVE_DIR/index.md}"
SLUG="${4:-bwrap-knowledge}"

if [ ! -d "$ROOT" ]; then
  echo "[ERROR] 根目录不存在: $ROOT" >&2
  exit 2
fi

mkdir -p "$ARCHIVE_DIR"

timestamp="$(date '+%Y-%m-%d %H:%M:%S %z')"
date_only="$(date '+%Y-%m-%d')"
time_only="$(date '+%H%M%S')"
output_file="$ARCHIVE_DIR/${date_only}-${SLUG}.md"
if [ -e "$output_file" ]; then
  output_file="$ARCHIVE_DIR/${date_only}-${time_only}-${SLUG}.md"
fi

bwrap_path="$(command -v bwrap 2>/dev/null || true)"
bwrap_version="$(bwrap --version 2>/dev/null | head -n1 | tr -d '\r' || true)"
usr_bin_version="$([ -x /usr/bin/bwrap ] && /usr/bin/bwrap --version 2>/dev/null | head -n1 | tr -d '\r' || true)"
usr_local_version="$([ -x /usr/local/bin/bwrap ] && /usr/local/bin/bwrap --version 2>/dev/null | head -n1 | tr -d '\r' || true)"
dpkg_bwrap_version="$(dpkg-query -W -f='${Version}' bubblewrap 2>/dev/null | tr -d '\r' || true)"
userns_clone="$(cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "N/A")"
has_perms="no"
has_size="no"
has_ro_bind_try="no"
help_flags="$(bwrap --help 2>/dev/null | grep -E -- '--perms|--size|--ro-bind-try' || true)"

if bwrap --help 2>/dev/null | grep -q -- '--perms'; then
  has_perms="yes"
fi
if bwrap --help 2>/dev/null | grep -q -- '--size'; then
  has_size="yes"
fi
if bwrap --help 2>/dev/null | grep -q -- '--ro-bind-try'; then
  has_ro_bind_try="yes"
fi

binary_sha256="N/A"
if [ -n "$bwrap_path" ] && [ -f "$bwrap_path" ]; then
  binary_sha256="$(sha256sum "$bwrap_path" | awk '{print $1}')"
fi

{
  echo "# bwrap 运行时归档快照"
  echo
  echo "- 归档时间：$timestamp"
  echo "- 归档脚本：\`control/scripts/archive-bwrap.sh\`"
  echo
  echo "## 摘要"
  echo
  echo "| 项目 | 值 |"
  echo "| --- | --- |"
  echo "| bwrap 路径 | \`${bwrap_path:-N/A}\` |"
  echo "| 当前 bwrap 版本 | \`${bwrap_version:-N/A}\` |"
  echo "| /usr/bin/bwrap 版本 | \`${usr_bin_version:-N/A}\` |"
  echo "| /usr/local/bin/bwrap 版本 | \`${usr_local_version:-N/A}\` |"
  echo "| dpkg bubblewrap 版本 | \`${dpkg_bwrap_version:-N/A}\` |"
  echo "| 支持 --perms | \`${has_perms}\` |"
  echo "| 支持 --size | \`${has_size}\` |"
  echo "| 支持 --ro-bind-try | \`${has_ro_bind_try}\` |"
  echo "| unprivileged_userns_clone | \`${userns_clone}\` |"
  echo "| 当前二进制 SHA256 | \`${binary_sha256}\` |"
  echo
  echo "## 知识结论"
  echo
  if [ "$has_perms" = "yes" ]; then
    echo "1. 当前默认 bwrap 已支持 \`--perms\`，可满足新沙箱参数要求。"
  else
    echo "1. 当前默认 bwrap 不支持 \`--perms\`，存在沙箱参数兼容风险。"
  fi
  if [ -n "$usr_bin_version" ] && [ -n "$usr_local_version" ] && [ "$usr_bin_version" != "$usr_local_version" ]; then
    echo "2. \`/usr/bin/bwrap\` 与 \`/usr/local/bin/bwrap\` 版本不一致，需关注硬编码路径调用风险。"
  else
    echo "2. 系统路径上的 bwrap 版本一致或缺少可比对信息。"
  fi
  if [ "$userns_clone" = "1" ]; then
    echo "3. 内核允许 unprivileged user namespace，可优先使用非 setuid 模式。"
  else
    echo "3. 内核 user namespace 开关非 1，运行行为可能依赖额外权限策略。"
  fi
  echo
  echo "## bwrap 关键 help 片段"
  echo
  if [ -n "$help_flags" ]; then
    echo '```text'
    echo "$help_flags"
    echo '```'
  else
    echo "> 未提取到 --perms/--size/--ro-bind-try 关键片段"
  fi
  echo
  echo "## 系统信息"
  echo
  echo '```text'
  cat /etc/os-release 2>/dev/null || true
  echo '```'
} > "$output_file"

if [ ! -f "$INDEX_FILE" ]; then
  cat > "$INDEX_FILE" <<'EOF'
# bwrap 知识归档索引

> 自动维护：`control/scripts/archive-bwrap.sh`

| 归档时间 | 文件 | 当前版本 | --perms | 路径 |
| --- | --- | --- | --- | --- |
EOF
fi

printf '| %s | [%s](%s) | `%s` | `%s` | `%s` |\n' \
  "$timestamp" \
  "$(basename "$output_file")" \
  "$(basename "$output_file")" \
  "${bwrap_version:-N/A}" \
  "$has_perms" \
  "${bwrap_path:-N/A}" >> "$INDEX_FILE"

ln -sfn "$(basename "$output_file")" "$ARCHIVE_DIR/latest.md"

echo "[INFO] 归档完成"
echo "[INFO] 归档文件: $output_file"
echo "[INFO] 索引文件: $INDEX_FILE"
echo "[INFO] 最新快照: $ARCHIVE_DIR/latest.md -> $(basename "$output_file")"
