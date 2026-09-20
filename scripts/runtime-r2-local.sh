#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/runtime-r2-local.sh \
    --digital-worker-root /path/to/digital-worker \
    --target-root /path/to/frozen-target \
    --frozen-plan /path/to/frozen-plan.json \
    --out /path/to/output \
    [--runtime-home /path/to/existing-codex-home] \
    [--model gpt-5.3-codex]

The script must be run from an exact Codex runtime-binding checkout that matches
frozen-plan.json. It uses a local Codex CLI login only; no provider credential is
read from or written to GitHub. By default it reuses the caller's existing
CODEX_HOME, or ~/.codex when CODEX_HOME is unset; it does not create an isolated
runtime home under the evidence directory.
EOF
}

DW_ROOT=
TARGET_ROOT=
PLAN=
OUT=
RUNTIME_HOME=
MODEL=gpt-5.3-codex
PYTHON_BIN=${PYTHON_BIN:-python3}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --digital-worker-root) DW_ROOT=$2; shift 2 ;;
    --target-root) TARGET_ROOT=$2; shift 2 ;;
    --frozen-plan) PLAN=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --runtime-home) RUNTIME_HOME=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for value in "$DW_ROOT" "$TARGET_ROOT" "$PLAN" "$OUT"; do
  if [ -z "$value" ]; then
    usage >&2
    exit 2
  fi
done

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DW_ROOT=$(cd "$DW_ROOT" && pwd)
TARGET_ROOT=$(cd "$TARGET_ROOT" && pwd)
PLAN=$(cd "$(dirname "$PLAN")" && pwd)/$(basename "$PLAN")
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

if [ -n "$RUNTIME_HOME" ]; then
  mkdir -p "$RUNTIME_HOME"
  R2_HOME=$(cd "$RUNTIME_HOME" && pwd)
elif [ -n "${CODEX_HOME:-}" ]; then
  mkdir -p "$CODEX_HOME"
  R2_HOME=$(cd "$CODEX_HOME" && pwd)
else
  mkdir -p "$HOME/.codex"
  R2_HOME=$(cd "$HOME/.codex" && pwd)
fi
case "$R2_HOME" in
  "$OUT"|"$OUT"/*)
    echo "runtime home must be a shared user Codex home outside the evidence directory: $R2_HOME" >&2
    exit 2
    ;;
esac

for cmd in git codex tar sha256sum; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "missing command: $cmd" >&2; exit 2; }
done
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "missing Python 3 interpreter: $PYTHON_BIN" >&2; exit 2; }
"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python >= 3.11 required, got {sys.version}")
PY

read_plan() {
  "$PYTHON_BIN" - "$PLAN" "$1" <<'PY'
import json, pathlib, sys
value=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for part in sys.argv[2].split("."):
    value=value[part]
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

EXPECTED_BINDING=$(read_plan runtime_bindings.codex.commit)
EXPECTED_DW=$(read_plan digital_worker_governance.provider_commit)
EXPECTED_BASE=$(read_plan controlled_task.exact_base_commit)
TARGET_REPOSITORY=$(read_plan controlled_task.repo_root)

test "$(git -C "$ROOT" rev-parse HEAD)" = "$EXPECTED_BINDING" || {
  echo "Codex binding checkout does not match frozen plan" >&2
  exit 2
}
test "$(git -C "$DW_ROOT" rev-parse HEAD)" = "$EXPECTED_DW" || {
  echo "Digital Worker checkout does not match frozen plan" >&2
  exit 2
}
test "$(git -C "$TARGET_ROOT" rev-parse HEAD)" = "$EXPECTED_BASE" || {
  echo "target checkout does not match frozen base" >&2
  exit 2
}
test -z "$(git -C "$TARGET_ROOT" status --porcelain=v1 --untracked-files=all)" || {
  echo "target checkout must be clean before R2 execution" >&2
  exit 2
}

"$PYTHON_BIN" "$DW_ROOT/scripts/runtime_r2_evidence.py" prepare \
  --root "$DW_ROOT" \
  --target-root "$TARGET_ROOT" \
  --output "$OUT/recomputed-plan.json"

"$PYTHON_BIN" - "$PLAN" "$OUT/recomputed-plan.json" <<'PY'
import json, pathlib, sys
a=json.loads(pathlib.Path(sys.argv[1]).read_text())
b=json.loads(pathlib.Path(sys.argv[2]).read_text())
if a["frozen_inputs_sha256"] != b["frozen_inputs_sha256"]:
    raise SystemExit("recomputed frozen inputs do not match supplied plan")
if a["controlled_task"] != b["controlled_task"]:
    raise SystemExit("recomputed controlled task does not match supplied plan")
PY

BUILD="$OUT/codex-build"
PYTHONPATH="$ROOT" "$PYTHON_BIN" -m tools.codex_assets build \
  --root "$ROOT" \
  --profile default \
  --build "$BUILD"
PYTHONPATH="$ROOT" "$PYTHON_BIN" -m tools.codex_assets apply \
  --root "$ROOT" \
  --build "$BUILD" \
  --target "$R2_HOME"
PYTHONPATH="$ROOT" "$PYTHON_BIN" -m tools.codex_assets diff \
  --root "$ROOT" \
  --build "$BUILD" \
  --target "$R2_HOME"

"$PYTHON_BIN" - "$ROOT" "$BUILD" "$R2_HOME" "$EXPECTED_BINDING" "$OUT/codex-install.json" <<'PY'
import fnmatch, hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
build=pathlib.Path(sys.argv[2])
home=pathlib.Path(sys.argv[3])
binding_commit=sys.argv[4]
out=pathlib.Path(sys.argv[5])
managed_path=build / "control/state/managed-files.json"
managed=json.loads(managed_path.read_text(encoding="utf-8"))
policies=json.loads((root / "manifests/policies.json").read_text(encoding="utf-8"))
allowed=[str(x) for x in policies.get("allowed_live_drift_paths", [])]
def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
def allowed_drift(path):
    return any(fnmatch.fnmatch(path, pattern) for pattern in allowed)
effective=[
    item for item in managed.get("managed", [])
    if not allowed_drift(str(item.get("path", "")))
]
source={
    "runtime_binding_repository":"jiying2007/codex",
    "runtime_binding_commit":binding_commit,
    "profile":managed.get("profile"),
    "source_fingerprint":managed.get("source_fingerprint"),
    "managed_state_sha256":hashlib.sha256(managed_path.read_bytes()).hexdigest(),
}
receipt={
    "schema":"codex-r2-runtime-install/v2",
    "runtime_home_mode":"shared-user-home",
    "source_set_identity_ref":"sha256:"+hashlib.sha256(canonical(source)).hexdigest(),
    "runtime_distribution_identity_ref":"sha256:"+hashlib.sha256(canonical(effective)).hexdigest(),
    "profile":managed.get("profile"),
    "managed_entries":len(managed.get("managed", [])),
    "identity_entries":len(effective),
    "local_state_exclusions":allowed,
    "credential_state_in_evidence":False,
}
out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
PY

"$PYTHON_BIN" - "$PLAN" "$OUT/provider-authorization.json" <<'PY'
import hashlib, json, pathlib, sys
plan_path=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
plan=json.loads(plan_path.read_text())
value={
    "schema":"codex-r2-provider-authorization/v1",
    "authorized":True,
    "authorization_mode":"explicit-local-operator-execution",
    "actor":"local-operator",
    "runtime_host":"local-terminal",
    "frozen_plan_sha256":hashlib.sha256(plan_path.read_bytes()).hexdigest(),
    "frozen_inputs_sha256":plan["frozen_inputs_sha256"],
    "scope":"codex-provider-execution-only",
    "verification_or_release_authority":False,
    "github_provider_credential_used":False,
}
out.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")
PY

"$PYTHON_BIN" - "$PLAN" "$OUT/prompt.txt" <<'PY'
import json, pathlib, sys
plan=json.loads(pathlib.Path(sys.argv[1]).read_text())
pathlib.Path(sys.argv[2]).write_text(plan["prompt"]+"\n", encoding="utf-8")
PY

date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/started-at.txt"
set +e
(
  cd "$TARGET_ROOT"
  CODEX_HOME="$R2_HOME" codex exec \
    --ephemeral \
    --json \
    --sandbox workspace-write \
    --model "$MODEL" \
    -o "$OUT/codex-final.txt" \
    "$(cat "$OUT/prompt.txt")"
) > "$OUT/codex-events.jsonl" 2> "$OUT/codex-stderr.log"
RC=$?
set -e
if [ "$RC" -ne 0 ]; then
  cat >&2 <<EOF
Codex local R2 execution failed with exit code $RC.
The run reused the existing shared Codex home:
  CODEX_HOME="$R2_HOME"
Fix the normal Codex CLI authentication/network/provider configuration, then rerun
this script from a clean frozen target checkout.
EOF
  exit "$RC"
fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT/finished-at.txt"

CODEX_HOME="$R2_HOME" codex --version > "$OUT/codex-version.txt"
git -C "$TARGET_ROOT" status --porcelain=v1 --untracked-files=all > "$OUT/codex-status.txt"
git -C "$TARGET_ROOT" diff --binary > "$OUT/codex.patch"
tar --exclude=.git -C "$TARGET_ROOT" -czf "$OUT/result-tree.tar.gz" .

"$PYTHON_BIN" - "$PLAN" "$OUT/provider-authorization.json" "$OUT/codex-install.json" \
  "$TARGET_ROOT" "$OUT/result-tree.tar.gz" "$OUT/codex-native.json" "$MODEL" "$TARGET_REPOSITORY" <<'PY'
import hashlib, json, pathlib, sys
plan_path,auth_path,install_path,target,result_archive,out=map(pathlib.Path,sys.argv[1:7])
model=sys.argv[7]
target_repository=sys.argv[8]
plan=json.loads(plan_path.read_text())
auth=json.loads(auth_path.read_text())
install=json.loads(install_path.read_text())
if auth["authorized"] is not True or auth["frozen_inputs_sha256"] != plan["frozen_inputs_sha256"]:
    raise SystemExit("local provider authorization does not match frozen plan")
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def tree_digest(root):
    rows=[]
    for p in sorted(x for x in root.rglob("*") if x.is_file() and ".git" not in x.parts):
        rows.append((p.relative_to(root).as_posix(),sha(p)))
    return hashlib.sha256(json.dumps(rows,separators=(",",":")).encode()).hexdigest()
controlled=plan["controlled_task"]
governance=controlled["digital_worker_governance_identity_ref"].removeprefix("sha256:")
version=pathlib.Path(out.parent,"codex-version.txt").read_text().strip()
receipt={
    "schema_version":2,
    "work_item_id":controlled["work_item_id"],
    "run_id":controlled["run_id"],
    "execution_source_set_identity":controlled["runtime_source_set_identity_ref"],
    "digital_worker_governance_identity":governance,
    "runtime_binding":{
        "repository":"jiying2007/codex",
        "commit":plan["runtime_bindings"]["codex"]["commit"],
        "target":"codex-cli",
        "runtime_profile":install["profile"],
        "runtime_host":"local-terminal",
        "source_set_identity_ref":install["source_set_identity_ref"],
        "runtime_distribution_identity_ref":install["runtime_distribution_identity_ref"],
    },
    "agent_assets":{
        "provider_repository":plan["adk_release_identity"]["repository"],
        "release_version":plan["adk_release_identity"]["version"],
        "release_tag":plan["adk_release_identity"]["tag"],
        "release_commit":plan["adk_release_identity"]["commit"],
        "asset_profile":controlled["adk_asset_profile"],
        "source_set_identity":install["source_set_identity_ref"],
    },
    "runtime":{
        "provider":"openai",
        "cli_version":version,
        "model":model,
        "model_provider":"openai",
    },
    "permissions":{
        "sandbox":"workspace-write",
        "approval":"explicit-local-operator-execution",
        "network":"local-codex-provider-transport",
    },
    "repository":{
        "repository":target_repository,
        "base_commit":controlled["exact_base_commit"],
        "result_commit":None,
    },
    "execution":{
        "status":"completed",
        "runtime_local_gates":["exact-base","source-set-applied","codex-cli-success","replay-bundle-complete"],
        "started_at":pathlib.Path(out.parent,"started-at.txt").read_text().strip(),
        "finished_at":pathlib.Path(out.parent,"finished-at.txt").read_text().strip(),
    },
    "evidence_refs":[
        "provider-authorization:sha256:"+sha(auth_path),
        "provider-events:sha256:"+sha(pathlib.Path(out.parent,"codex-events.jsonl")),
        "provider-output:sha256:"+sha(pathlib.Path(out.parent,"codex-final.txt")),
        "worktree-result:sha256:"+tree_digest(target),
        "replay-result-archive:sha256:"+sha(result_archive),
    ],
}
out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
PY

"$PYTHON_BIN" - "$ROOT/schemas/runtime-execution-receipt.v2.schema.json" "$OUT/codex-native.json" <<'PY'
import json, pathlib, sys
try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    raise SystemExit("jsonschema is required: python3 -m pip install jsonschema") from exc
schema=json.loads(pathlib.Path(sys.argv[1]).read_text())
receipt=json.loads(pathlib.Path(sys.argv[2]).read_text())
Draft202012Validator(schema).validate(receipt)
PY

"$PYTHON_BIN" "$DW_ROOT/scripts/runtime_r2_evidence.py" project-receipt \
  --root "$DW_ROOT" \
  --runtime codex \
  --native-receipt "$OUT/codex-native.json" \
  --frozen-plan "$PLAN" \
  --output "$OUT/codex-portable.json"

"$PYTHON_BIN" - "$OUT" <<'PY'
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
files=[]
for p in sorted(x for x in root.iterdir() if x.is_file() and x.name != "bundle-manifest.json"):
    files.append({"path":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
manifest={
    "schema":"codex-r2-local-evidence-bundle/v1",
    "runtime":"codex",
    "execution_venue":"local-terminal",
    "github_provider_credential_used":False,
    "verification_pass_claimed":False,
    "r2_qualified":False,
    "files":files,
}
(root/"bundle-manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
PY

tar -C "$OUT" -czf "$OUT/codex-r2-local-evidence.tar.gz" \
  bundle-manifest.json provider-authorization.json codex-install.json codex-native.json \
  codex-portable.json codex-status.txt codex.patch codex-version.txt codex-final.txt \
  codex-events.jsonl result-tree.tar.gz
sha256sum "$OUT/codex-r2-local-evidence.tar.gz" > "$OUT/codex-r2-local-evidence.tar.gz.sha256"

echo "Codex local R2 execution evidence ready: $OUT/codex-portable.json"
