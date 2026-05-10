#!/usr/bin/env bash
set -euo pipefail

require_modern=0
json_out=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --require-modern)
      require_modern=1
      shift
      ;;
    --json-out)
      if [[ $# -lt 2 ]]; then
        echo "[FATAL] --json-out 需要路径参数" >&2
        exit 2
      fi
      json_out="$2"
      shift 2
      ;;
    *)
      echo "[FATAL] 未知参数: $1" >&2
      exit 2
      ;;
  esac
done

default_bin="$(rtk bash -lc 'command -v bwrap || true' | tr -d '\r\n')"
if [[ -z "$default_bin" ]]; then
  echo "[FAIL] bwrap 不存在于 PATH"
  exit 1
fi

default_ver="$(rtk bash -lc 'bwrap --version 2>/dev/null || true' | tr -d '\r\n')"
usr_bin_ver="$(rtk bash -lc 'if [[ -x /usr/bin/bwrap ]]; then /usr/bin/bwrap --version; fi' | tr -d '\r\n')"
usr_local_ver="$(rtk bash -lc 'if [[ -x /usr/local/bin/bwrap ]]; then /usr/local/bin/bwrap --version; fi' | tr -d '\r\n')"
help_text="$(rtk bwrap --help 2>/dev/null || true)"

supports_perms=0
supports_size=0
supports_ro_bind_try=0

[[ "$help_text" == *"--perms"* ]] && supports_perms=1
[[ "$help_text" == *"--size"* ]] && supports_size=1
[[ "$help_text" == *"--ro-bind-try"* ]] && supports_ro_bind_try=1

userns_clone="$(rtk bash -lc 'cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo unknown' | tr -d '\r\n')"
max_userns="$(rtk bash -lc 'cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo unknown' | tr -d '\r\n')"

runtime_ok=0
if rtk bwrap --unshare-user --uid 0 --gid 0 --ro-bind / / --proc /proc --dev /dev /bin/true >/dev/null 2>&1; then
  runtime_ok=1
fi

modern_ok=0
if [[ "$supports_perms" -eq 1 && "$supports_size" -eq 1 && "$supports_ro_bind_try" -eq 1 && "$userns_clone" == "1" && "$runtime_ok" -eq 1 ]]; then
  modern_ok=1
fi

echo "[INFO] bwrap.path=$default_bin"
echo "[INFO] bwrap.version.default=${default_ver:-unknown}"
echo "[INFO] bwrap.version./usr/bin=${usr_bin_ver:-missing}"
echo "[INFO] bwrap.version./usr/local/bin=${usr_local_ver:-missing}"
echo "[INFO] supports.--ro-bind-try=$supports_ro_bind_try"
echo "[INFO] supports.--perms=$supports_perms"
echo "[INFO] supports.--size=$supports_size"
echo "[INFO] kernel.unprivileged_userns_clone=$userns_clone"
echo "[INFO] user.max_user_namespaces=$max_userns"
echo "[INFO] runtime.minimal_sandbox_ok=$runtime_ok"

if [[ -n "$json_out" ]]; then
  out_dir="$(rtk dirname "$json_out")"
  rtk mkdir -p "$out_dir"
  cat >"$json_out" <<EOF
{
  "bwrap_path": "$default_bin",
  "default_version": "${default_ver:-}",
  "usr_bin_version": "${usr_bin_ver:-}",
  "usr_local_bin_version": "${usr_local_ver:-}",
  "supports_ro_bind_try": $supports_ro_bind_try,
  "supports_perms": $supports_perms,
  "supports_size": $supports_size,
  "unprivileged_userns_clone": "$userns_clone",
  "max_user_namespaces": "$max_userns",
  "minimal_runtime_ok": $runtime_ok,
  "modern_sandbox_ready": $modern_ok
}
EOF
  echo "[INFO] json_out=$json_out"
fi

if [[ "$modern_ok" -eq 1 ]]; then
  echo "[PASS] 通过新沙箱参数要求"
  exit 0
fi

echo "[WARN] 未通过新沙箱参数要求（缺少 --perms/--size 或运行态不满足）"
if [[ "$require_modern" -eq 1 ]]; then
  echo "[FAIL] 已启用 --require-modern，返回失败"
  exit 1
fi
exit 0
