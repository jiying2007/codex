#!/usr/bin/env bash
set -euo pipefail

provider_commit=c41f7c933f653dd702b0d8042ae9df38807430dc
archive_sha=66107c68a2ac76488cd06238bc582114dcc4c595aa691da3d6114743b534d59b
trust_sha=6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66
branch=automation/adk-11.4.16-signed-source-import

[[ "$GITHUB_REPOSITORY" == jiying2007/codex && "$GITHUB_REF" == "refs/heads/$branch" ]]
git checkout -B "$branch" "$GITHUB_SHA"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]]

git clone --depth 1 --branch v11.4.16 https://github.com/jiying2007/agent-dev-kit.git "$RUNNER_TEMP/adk-exact"
[[ "$(git -C "$RUNNER_TEMP/adk-exact" rev-parse HEAD)" == "$provider_commit" ]]
[[ -z "$(git -C "$RUNNER_TEMP/adk-exact" status --porcelain=v1 --untracked-files=all)" ]]
mkdir -p "$RUNNER_TEMP/adk-evidence" "$RUNNER_TEMP/adk-release"
gh release download v11.4.16 --repo jiying2007/agent-dev-kit --pattern 'agent-dev-kit-11.4.16.tar.gz' --pattern 'agent-dev-kit-11.4.16.tar.gz.sha256' --pattern 'release-contract.json' --dir "$RUNNER_TEMP/adk-release"
printf '%s  %s\n' "$archive_sha" "$RUNNER_TEMP/adk-release/agent-dev-kit-11.4.16.tar.gz" | sha256sum --check --strict
(cd "$RUNNER_TEMP/adk-release" && sha256sum --check --strict agent-dev-kit-11.4.16.tar.gz.sha256)
gh run download 44700552832 --repo jiying2007/agent-dev-kit --name "adk-promotion-evidence-$provider_commit" --dir "$RUNNER_TEMP/adk-evidence"
[[ -s "$RUNNER_TEMP/adk-evidence/promotion-evidence.json" && -s "$RUNNER_TEMP/adk-evidence/promotion-attestation.json" ]]
curl --fail --silent --show-error --location --retry 2 https://tuf-repo-cdn.sigstore.dev/targets/trusted_root.json --output "$RUNNER_TEMP/adk-evidence/trusted_root.json"
printf '%s  %s\n' "$trust_sha" "$RUNNER_TEMP/adk-evidence/trusted_root.json" | sha256sum --check --strict
cosign verify-blob --bundle "$RUNNER_TEMP/adk-evidence/promotion-attestation.json" --trusted-root "$RUNNER_TEMP/adk-evidence/trusted_root.json" --certificate-identity https://github.com/jiying2007/agent-dev-kit/.github/workflows/ci.yml@refs/heads/main --certificate-oidc-issuer https://token.actions.githubusercontent.com "$RUNNER_TEMP/adk-evidence/promotion-evidence.json"

import_adk() {
  python -m tools.codex_assets.adk_source_import --root . --provider-root "$RUNNER_TEMP/adk-exact" --expected-provider-commit "$provider_commit" --promotion-evidence "$RUNNER_TEMP/adk-evidence/promotion-evidence.json" --promotion-attestation "$RUNNER_TEMP/adk-evidence/promotion-attestation.json" --trusted-root "$RUNNER_TEMP/adk-evidence/trusted_root.json" --release-artifact-sha256 "$archive_sha" --allow-reviewed-native-ui --preserve-execution-policy "$@"
}
import_adk --summary-json > "$RUNNER_TEMP/plan.json"
python - "$RUNNER_TEMP/plan.json" "$provider_commit" <<'PY'
import json,sys
plan=json.load(open(sys.argv[1]))
for key,value in {'status':'planned','version':'11.4.16','skill_count':41,'agent_count':9,'policy_mode':'preserve-independent','provider_commit':sys.argv[2]}.items():
    assert plan[key]==value,(key,plan.get(key),value)
print('Signed plan verified: 41 Skills / 9 Agents, policy preserved')
PY
import_adk --apply --summary-json > "$RUNNER_TEMP/apply.json"
import_adk --write-source-fixture --baseline-provider-version 11.2.1 --summary-json > "$RUNNER_TEMP/fixture.json"
python -m unittest tests.test_adk_source_import tests.test_adk_skill_audit tests.test_adk_skill_distribution tests.test_adk_daily_core_import tests.test_execution_policy_source_set tests.test_local_skill_chinese_ui -q
python -m tools.codex_assets.adk_skill_audit --summary-json > "$RUNNER_TEMP/source-audit.json"
python - "$RUNNER_TEMP/source-audit.json" "$provider_commit" <<'PY'
import json,sys
from pathlib import Path
report=json.load(open(sys.argv[1])); assert report['status']=='consistent',report
manifest=json.loads(Path('manifests/skills.json').read_text())
active=[s for s in manifest['skills'] if s.get('enabled') is True and s.get('owner')=='agent-dev-kit']
assert len(active)==41 and all(s['source_ref']==sys.argv[2] and s['source_release']=='v11.4.16' for s in active)
policy=json.loads(Path('manifests/execution_policy.json').read_text())
assert policy['engine']['behavior_baseline']['version']=='8.2.0'
print('Authenticated source import and independent Python policy verified; not a native CLI live test')
PY

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add manifests/skills.json manifests/agents.json manifests/provider-locks/agent-dev-kit.json manifests/provider-locks/agent-dev-kit-execution-policy.json src/codex-home/skills/registry.csv src/codex-home/vendor/skills src/codex-home/vendor/agents/agent-dev-kit tests/fixtures/adk-skill-sources-11.4.16.json
git diff --cached --check
[[ -n "$(git diff --cached --name-only)" ]]
git commit -m 'chore(adk): signed exact-source 11.4.16 Skills/Agents import'
git push origin "HEAD:refs/heads/$branch"
echo 'Signed exact-source import committed to isolated branch; ~/.codex remains untouched'
