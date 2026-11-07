#!/usr/bin/env bash
set -euo pipefail

# Reject unauthenticated final gates BEFORE invoking an optional local shell
# wrapper such as rtk. This negative safety check must work on clean CI hosts.
gate=false
final=false
previous=
for argument in "$@"; do
  if [[ "$argument" == gate ]]; then
    gate=true
  elif [[ "$previous" == "--event" && "$argument" == final ]]; then
    final=true
  fi
  previous="$argument"
done
if [[ "$gate" == true && "$final" == true && -z "${CODEX_THREAD_ID:-}" ]]; then
  echo "execution-policy gate final requires CODEX_THREAD_ID" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
exec rtk python3 "$ROOT/tools/codex_assets/entrypoint.py" execution-policy --root "$ROOT" "$@"
