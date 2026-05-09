#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PROFILE="${2:-}"
STATE_FILE="$ROOT/control/state/active-profile.env"

if [ -z "$PROFILE" ] && [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  source "$STATE_FILE"
fi

if [ -z "${PROFILE:-}" ]; then
  PROFILE="minimal"
fi

SKILLS_CSV="$ROOT/control/catalog/skills.csv"
AGENTS_CSV="$ROOT/control/catalog/agents.csv"
MCP_CSV="$ROOT/control/catalog/mcp.csv"
PLUGINS_CSV="$ROOT/control/catalog/plugins.csv"
RTK_POLICY_FILE="$ROOT/vendor/policies/rtk/1.0.0/RTK.md"
RULES_FILE="$ROOT/rules/default.rules"

errors=0
warnings=0

has_profile() {
  local field="$1"
  local profile="$2"
  local token
  IFS='|' read -r -a parts <<< "$field"
  for token in "${parts[@]}"; do
    if [ "$token" = "$profile" ]; then
      return 0
    fi
  done
  return 1
}

check_rtk_shell_config() {
  local cfg="$1"
  if [ ! -f "$cfg" ]; then
    return
  fi

  if ! grep -qE '^[[:space:]]*program[[:space:]]*=[[:space:]]*"rtk"' "$cfg"; then
    echo "[ERROR] shell 未使用 rtk 作为默认入口: ${cfg#$ROOT/}"
    errors=$((errors + 1))
  fi

  if ! grep -qE '^[[:space:]]*args[[:space:]]*=[[:space:]]*\["bash",[[:space:]]*"-lc"\]' "$cfg"; then
    echo "[ERROR] shell args 未配置为 [\"bash\", \"-lc\"]: ${cfg#$ROOT/}"
    errors=$((errors + 1))
  fi
}

check_links() {
  local csv="$1"
  local kind="$2"

  while IFS=, read -r name enabled _source_kind _version source_rel target_rel profiles _rest; do
    [ "$name" = "name" ] && continue
    [ -z "$name" ] && continue

    if [ "$enabled" != "1" ]; then
      continue
    fi

    if ! has_profile "$profiles" "$PROFILE"; then
      continue
    fi

    source_abs="$ROOT/$source_rel"
    target_abs="$ROOT/$target_rel"

    if [ ! -e "$source_abs" ]; then
      echo "[ERROR] 缺少 $kind 源: $source_rel"
      errors=$((errors + 1))
      continue
    fi

    if [ ! -L "$target_abs" ]; then
      echo "[WARN ] $kind 未激活为软链接: $target_rel"
      warnings=$((warnings + 1))
      continue
    fi

    current="$(readlink "$target_abs")"
    if [ "$current" != "$source_abs" ]; then
      echo "[WARN ] $kind 链接目标不一致: $target_rel -> $current (expected $source_abs)"
      warnings=$((warnings + 1))
    fi
  done < "$csv"
}

check_links "$SKILLS_CSV" "skill"
check_links "$AGENTS_CSV" "agent"

# 检查 ~/.codex 是否指向本仓库
CODEX_HOME="$HOME/.codex"
if [ -L "$CODEX_HOME" ]; then
  codex_target="$(readlink "$CODEX_HOME")"
  if [ "$codex_target" = "$ROOT" ]; then
    :  # 正常
  else
    echo "[WARN ] ~/.codex 指向 $codex_target，非当前 ROOT=$ROOT"
    warnings=$((warnings + 1))
  fi
elif [ -d "$CODEX_HOME" ] && [ "$CODEX_HOME" != "$ROOT" ]; then
  echo "[INFO ] ~/.codex 是独立目录（非软链接），当前 ROOT=$ROOT"
fi

if [ -d "$ROOT/agents" ]; then
  dup_names="$(awk -F'"' '/^name = /{print $2}' "$ROOT"/agents/*.toml 2>/dev/null | sort | uniq -d || true)"
  if [ -n "$dup_names" ]; then
    echo "[ERROR] 检测到重复 agent 角色名:"
    printf '%s\n' "$dup_names" | sed 's/^/[ERROR]   - /'
    errors=$((errors + 1))
  fi
fi

if [ -f "$PLUGINS_CSV" ]; then
  while IFS=, read -r pname _version _kind source_path vendor_path enabled _notes; do
    root_entry="$ROOT/$pname"
    [ "$pname" = "name" ] && continue
    [ "$enabled" = "1" ] || continue
    if [[ ! "$source_path" =~ ^vendor/ ]]; then
      echo "[WARN ] 插件 source_path 未落在 vendor/: $pname -> $source_path"
      warnings=$((warnings + 1))
    fi
    if [[ ! "$vendor_path" =~ ^vendor/ ]]; then
      echo "[ERROR] 插件 vendor_path 非 vendor 目录: $pname -> $vendor_path"
      errors=$((errors + 1))
    fi
    if [ -e "$root_entry" ] || [ -L "$root_entry" ]; then
      echo "[WARN ] 检测到根目录第三方入口: $pname（应仅通过 vendor/ 管理）"
      warnings=$((warnings + 1))
    fi
  done < "$PLUGINS_CSV"
else
  echo "[ERROR] 缺少插件 catalog: control/catalog/plugins.csv"
  errors=$((errors + 1))
fi

if [ ! -f "$RTK_POLICY_FILE" ]; then
  echo "[ERROR] 缺少 RTK 规则文档: vendor/policies/rtk/1.0.0/RTK.md"
  errors=$((errors + 1))
fi

if [ -f "$RULES_FILE" ]; then
  if ! grep -qF 'prefix_rule(pattern=["rtk"], decision="allow")' "$RULES_FILE"; then
    echo "[ERROR] rules/default.rules 缺少 RTK 前缀放行规则: prefix_rule(pattern=[\"rtk\"], decision=\"allow\")"
    errors=$((errors + 1))
  fi
else
  echo "[WARN ] 未发现 rules/default.rules（建议配置 RTK 前缀放行规则以减少提权确认）"
  warnings=$((warnings + 1))
fi

if [ -e "$ROOT/RTK.md" ] || [ -L "$ROOT/RTK.md" ]; then
  echo "[WARN ] 检测到根目录 RTK.md（建议仅保留 vendor/policies 下版本化文档）"
  warnings=$((warnings + 1))
fi

check_rtk_shell_config "$ROOT/config.toml"
check_rtk_shell_config "$ROOT/config.debug.toml"
check_rtk_shell_config "$ROOT/config.dev.toml"
check_rtk_shell_config "$ROOT/config.embedded.toml"
check_rtk_shell_config "$ROOT/config.max.toml"

if [ ! -f "$MCP_CSV" ]; then
  echo "[ERROR] 缺少 mcp catalog: control/catalog/mcp.csv"
  errors=$((errors + 1))
fi

if [ ! -f "$ROOT/control/generated/config-managed.toml" ]; then
  echo "[WARN ] 未发现渲染片段: control/generated/config-managed.toml"
  warnings=$((warnings + 1))
fi

echo "[INFO ] profile=$PROFILE errors=$errors warnings=$warnings"
if [ "$errors" -gt 0 ]; then
  exit 1
fi
