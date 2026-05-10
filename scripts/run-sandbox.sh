#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: rtk bash scripts/run-sandbox.sh [--ro-bind SRC:DEST] [--ro-bind-try SRC:DEST] [--rw-bind SRC:DEST] [--tmpfs PATH[:SIZE[:PERMS]]] -- <command> [args...]" >&2
  exit 2
fi

ro_binds=()
ro_bind_tries=()
rw_binds=()
tmpfs_specs=()
cmd=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ro-bind)
      ro_binds+=("$2")
      shift 2
      ;;
    --ro-bind-try)
      ro_bind_tries+=("$2")
      shift 2
      ;;
    --rw-bind)
      rw_binds+=("$2")
      shift 2
      ;;
    --tmpfs)
      tmpfs_specs+=("$2")
      shift 2
      ;;
    --)
      shift
      cmd=("$@")
      break
      ;;
    *)
      echo "[FATAL] 未知参数: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ${#cmd[@]} -eq 0 ]]; then
  echo "[FATAL] 缺少命令。使用 -- <command> 传入待执行命令" >&2
  exit 2
fi

help_text="$(rtk bwrap --help 2>/dev/null || true)"
supports_perms=0
supports_size=0
supports_ro_bind_try=0
[[ "$help_text" == *"--perms"* ]] && supports_perms=1
[[ "$help_text" == *"--size"* ]] && supports_size=1
[[ "$help_text" == *"--ro-bind-try"* ]] && supports_ro_bind_try=1

args=(--unshare-user --uid 0 --gid 0 --ro-bind / / --proc /proc --dev /dev)

parse_bind_pair() {
  local pair="$1"
  local src="${pair%%:*}"
  local dst="${pair#*:}"
  if [[ -z "$src" || -z "$dst" || "$src" == "$dst" ]]; then
    echo "[FATAL] 绑定参数格式错误: $pair（需为 SRC:DEST）" >&2
    exit 2
  fi
  printf "%s\n%s\n" "$src" "$dst"
}

for pair in "${ro_binds[@]}"; do
  mapfile -t parsed < <(parse_bind_pair "$pair")
  args+=(--ro-bind "${parsed[0]}" "${parsed[1]}")
done

for pair in "${rw_binds[@]}"; do
  mapfile -t parsed < <(parse_bind_pair "$pair")
  args+=(--bind "${parsed[0]}" "${parsed[1]}")
done

for pair in "${ro_bind_tries[@]}"; do
  mapfile -t parsed < <(parse_bind_pair "$pair")
  src="${parsed[0]}"
  dst="${parsed[1]}"
  if [[ "$supports_ro_bind_try" -eq 1 ]]; then
    args+=(--ro-bind-try "$src" "$dst")
  elif [[ -e "$src" ]]; then
    args+=(--ro-bind "$src" "$dst")
  else
    echo "[WARN] ro-bind-try 降级后源不存在，已跳过: $src"
  fi
done

for spec in "${tmpfs_specs[@]}"; do
  IFS=':' read -r path size perms <<<"$spec"
  if [[ -z "${path:-}" ]]; then
    echo "[FATAL] tmpfs 参数格式错误: $spec（需为 PATH[:SIZE[:PERMS]]）" >&2
    exit 2
  fi
  if [[ -n "${perms:-}" ]]; then
    if [[ "$supports_perms" -eq 1 ]]; then
      args+=(--perms "$perms")
    else
      echo "[WARN] 当前 bwrap 不支持 --perms，忽略 tmpfs perms=$perms"
    fi
  fi
  if [[ -n "${size:-}" ]]; then
    if [[ "$supports_size" -eq 1 ]]; then
      args+=(--size "$size")
    else
      echo "[WARN] 当前 bwrap 不支持 --size，忽略 tmpfs size=$size"
    fi
  fi
  args+=(--tmpfs "$path")
done

echo "[INFO] sandbox.command=${cmd[*]}"
rtk bwrap "${args[@]}" -- "${cmd[@]}"
