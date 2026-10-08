#!/usr/bin/env bash
set -euo pipefail

HUB_ROOT="${KNOWLEDGE_HUB_ROOT:-$HOME/knowledge-hub}"
CMD="${1:-status}"
shift || true

blocked() {
  printf '{"status":"BLOCKED","provider":"knowledge-hub","reason":"%s"}\n' "$1"
  exit 2
}

require_surface() {
  local path="$1"
  [[ -x "$path" || -f "$path" ]] || blocked "provider surface unavailable: $path"
}

case "$CMD" in
  status)
    if [[ ! -d "$HUB_ROOT" ]]; then
      blocked "provider root unavailable"
    fi
    for name in knowledge-context.sh knowledge-evidence-pack.sh knowledge-action-check.sh knowledge-proposal-route.sh knowledge-capture.sh knowledge-activity.sh; do
      require_surface "$HUB_ROOT/tools/$name"
    done
    exec bash "$HUB_ROOT/tools/knowledge-capture.sh" --provider-capabilities --json
    ;;
  context)
    require_surface "$HUB_ROOT/tools/knowledge-context.sh"
    exec bash "$HUB_ROOT/tools/knowledge-context.sh" "$@"
    ;;
  evidence-pack)
    require_surface "$HUB_ROOT/tools/knowledge-evidence-pack.sh"
    exec bash "$HUB_ROOT/tools/knowledge-evidence-pack.sh" "$@"
    ;;
  action-check)
    require_surface "$HUB_ROOT/tools/knowledge-action-check.sh"
    exec bash "$HUB_ROOT/tools/knowledge-action-check.sh" "$@"
    ;;
  proposal-route)
    require_surface "$HUB_ROOT/tools/knowledge-proposal-route.sh"
    exec bash "$HUB_ROOT/tools/knowledge-proposal-route.sh" "$@"
    ;;
  archive)
    require_surface "$HUB_ROOT/tools/knowledge-capture.sh"
    exec bash "$HUB_ROOT/tools/knowledge-capture.sh" --provider-archive "$@"
    ;;
  activity-capture)
    require_surface "$HUB_ROOT/tools/knowledge-activity.sh"
    exec bash "$HUB_ROOT/tools/knowledge-activity.sh" capture "$@"
    ;;
  *)
    echo "usage: $0 {status|context|evidence-pack|action-check|proposal-route|archive|activity-capture} [args...]" >&2
    exit 2
    ;;
esac
