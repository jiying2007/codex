#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STRICT_WARN="${STRICT_WARN:-0}"
REGISTRY_FILE="${REGISTRY_FILE:-$ROOT/registry.csv}"

if [ ! -d "$ROOT" ]; then
  echo "[FATAL] skills 根目录不存在: $ROOT" >&2
  exit 2
fi

if ! command -v rg >/dev/null 2>&1; then
  # rg 不可用时降级为 grep
  _rg_grep() { grep -qE "$1"; }
else
  _rg_grep() { rg -q "$1"; }
fi

declare -A REG_VERSIONS=()
declare -A REG_SEEN=()

if [ -f "$REGISTRY_FILE" ]; then
  while IFS=, read -r name version status owner; do
    [ -n "$name" ] || continue
    [ "$name" = "name" ] && continue
    case "$name" in
      \#*) continue ;;
    esac
    name="$(echo "$name" | xargs)"
    version="$(echo "$version" | xargs)"
    [ -n "$name" ] || continue
    REG_VERSIONS["$name"]="$version"
    REG_SEEN["$name"]=0
  done < "$REGISTRY_FILE"
fi

errors=0
warnings=0
checked=0

while IFS= read -r skill_dir; do
  skill_name="$(basename "$skill_dir")"
  skill_file="$skill_dir/SKILL.md"
  readme_file="$skill_dir/README.md"

  if [ ! -f "$skill_file" ]; then
    continue
  fi

  checked=$((checked + 1))

  frontmatter="$(awk '
    BEGIN { in_frontmatter=0 }
    /^---[[:space:]]*$/ {
      if (in_frontmatter==0) { in_frontmatter=1; next }
      exit
    }
    in_frontmatter==1 { print }
  ' "$skill_file")"

  for key in name description; do
    if ! printf '%s\n' "$frontmatter" | grep -qE "^${key}:"; then
      echo "[ERROR] ${skill_name}: SKILL.md frontmatter 缺少 ${key}"
      errors=$((errors + 1))
    fi
  done

  skill_version="$(printf '%s\n' "$frontmatter" | sed -n 's/^version:[[:space:]]*//p' | head -n1 | tr -d '"' | xargs)"

  if [ -f "$REGISTRY_FILE" ]; then
    if [ -z "${REG_VERSIONS[$skill_name]+x}" ]; then
      echo "[ERROR] ${skill_name}: registry.csv 未登记该技能"
      errors=$((errors + 1))
    else
      REG_SEEN["$skill_name"]=1
      expected="${REG_VERSIONS[$skill_name]}"
      if [ -n "$expected" ] && [ -n "$skill_version" ] && [ "$skill_version" != "$expected" ]; then
        echo "[ERROR] ${skill_name}: version 与 registry 不一致 (skill=${skill_version}, registry=${expected})"
        errors=$((errors + 1))
      fi
    fi
  fi

  if [ -d "$skill_dir/.git" ]; then
    echo "[ERROR] ${skill_name}: 检测到内嵌 .git，建议移除"
    errors=$((errors + 1))
  fi

  if [ ! -f "$skill_dir/agents/openai.yaml" ]; then
    echo "[WARN ] ${skill_name}: 缺少 agents/openai.yaml"
    warnings=$((warnings + 1))
  fi

  if [ -f "$readme_file" ] && grep -qF "~/.agents/skills" "$readme_file"; then
    echo "[WARN ] ${skill_name}: README 包含非当前标准路径 ~/.agents/skills"
    warnings=$((warnings + 1))
  fi

  while IFS= read -r rel_path; do
    [ -n "$rel_path" ] || continue
    if [ ! -e "$skill_dir/$rel_path" ]; then
      echo "[ERROR] ${skill_name}: 引用不存在 -> ${rel_path}"
      errors=$((errors + 1))
    fi
  done < <(grep -oE '(scripts|references)/[A-Za-z0-9._/-]+' "$skill_file" | sort -u)

done < <(find -L "$ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '.*' ! -name 'scripts' | sort)

if [ -f "$REGISTRY_FILE" ]; then
  for reg_name in "${!REG_VERSIONS[@]}"; do
    if [ "${REG_SEEN[$reg_name]:-0}" -ne 1 ]; then
      echo "[ERROR] registry: 已登记但目录缺失 -> ${reg_name}"
      errors=$((errors + 1))
    fi
  done
else
  echo "[WARN ] 未找到 registry.csv: ${REGISTRY_FILE}"
  warnings=$((warnings + 1))
fi

echo "[INFO ] 检查完成: skills=${checked}, errors=${errors}, warnings=${warnings}"

if [ "$errors" -gt 0 ]; then
  exit 1
fi

if [ "$STRICT_WARN" = "1" ] && [ "$warnings" -gt 0 ]; then
  exit 1
fi

exit 0
