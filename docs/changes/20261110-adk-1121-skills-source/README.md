# ADK 11.2.1 Skills-only consumer import

- Canonical source: jiying2007/agent-dev-kit v11.2.1, a5ba89065b163594571cc673dd436a23524725a6.
- Signed source: ADK Actions run 42651528457, source artifact 13690606665; exact Sigstore trust root verified.
- 41 source Skills copied with complete references, new immutable version directories and current manifests/registry; old active vendor version directories retired in the isolated candidate.
- Nine Agent blobs have equal upstream content and are rebound to the new source without model/runtime certification.
- Execution Policy remains separately pinned to ADK v8.2.0 as an explicit Python 3.8-compatible runtime boundary; new ADK Python 3.12 policy modules are NOT installed into Codex.
- This is source/distribution only, not a write to ~/.codex, native trigger evidence, or product release readiness.
- Rollback: review and revert this consumer PR to the previous immutable exact source set; no old upstream tag is moved.

## Independent fail-closed execution-policy identity

The original policy code remains bound by `ENGINE_BASELINE` plus exact Git blob modes/digests. When the active Skills provider differs, `manifests/provider-locks/agent-dev-kit-execution-policy.json` must bind both current signed consumer release identity and the immutable ADK v8.2.0 policy source (including tree, manifest and archive). Doctor and runtime reject a missing/drifting independent lock, source bytes, provider commit or invalid permission policy. This deliberately changes only the source identity contract, not Python runtime behavior or ADK release authority.
