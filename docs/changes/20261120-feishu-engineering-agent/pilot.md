# Feishu Engineering Agent — Host qualification and rollout gate

This is a short operator contract for the existing **single Feishu Bot instance**. No second WebSocket consumer, scheduled monitor or new Codex model run is introduced by this change.

## Offline entrypoints

- `python -m tools.codex_assets.feishu_engineering_agent --dry-run --allow-repo robot-app --selected-repo robot-app --text '分析 sensor 初始化'`: deterministic proposal only.
- `python -m tools.codex_assets.feishu_engineering_agent --probe-runtime`: checks the installed `codex --version` and `codex app-server --help` on the **host actually running the Bot**. It **does not** authenticate to Codex, start App Server, resume a thread or call a model. The same command from CI is not evidence about vstrong100.
- Use a temporary 0600 SQLite path with `RunStore` for offline smoke. Never point offline code at the installed `feishu-codex-state.sqlite3`.

## Single-consumer card boundary

The legacy `FeishuTransport.start(on_message, card_callback=None)` retains its original behavior with no callback configured. Only an **explicitly enabled** same-process integration may pass `card_callback` to that method. The new `CardPublisher` must receive the existing transport and a private HMAC signing key outside Git. It marks `sending` in durable SQLite before sending a Card 2.0 interactive message and binds the returned message ID on success. Ambiguous external outcomes become **UNKNOWN** and are not automatically retried. Card display states read the `AgentRun` ledger, not the Feishu card message.

A valid `card.action.trigger` must pass authenticated transport validation, verification token, app ID, HMAC, tenant/chat/actor/message/card/revision matching and expiry. ACK is built synchronously, and only a pending intent is written. `request_execution` and `request_cancel` **do not approve** model quota, workspace edits, Git publication or device operations. A privileged worker must independently validate each effect and its owner/budget grant. Card interaction windows and callback timing require a **real desktop and phone test** before enabling the handler in production.

## Explicit acceptance gate

| Gate | Offline code evidence | Required real evidence | Status |
|---|---|---|---|
| C1: card | Signed JSON and idempotent send/click tests | Real callback delivery, response under three seconds, mobile/desktop, expiry and update | Pending |
| C2: exact session | Store, resume/interrupt request plan, help-only probe | vstrong100 app-server handshake, thread identity, approval, turn lifecycle, interrupt/restart semantics | Pending |
| C3: sources | Read-only TAPD/Meegle injected transport tests | One scoped Feishu Project requirement and one TAPD Bug read with actual app permission | Pending |
| C4: delivery | WorkItem/AgentRun ledger and verified-evidence gate | One feature and one bug through code/PR/CI and **independent** source-system QA | Pending |
| C5: migration | Existing Bot unchanged by default | Backup WAL/spool/config, restore proof, one active listener and rollback | Pending |

Codex shared/Work quota remains prohibited without separate fresh authorization. Real model transport, WorkItem source writes, Git push/merge, QA status and firmware flashing are out of scope for the offline module tests. CI green only proves the tested source code, not these gates.

## Remaining integration work

The live Bot source preserves the existing intake/queue; the optional card callback is wired behind `engineering_cards_enabled=false` by default, and no live host activation has been verified. The local WorkItem MCP bridge is source-integrated with the existing SQLite/spool/worker path, but it has not been installed or host-qualified on `vstrong100`. The linked WorkItem worker uses persistent `codex exec --json` and records the exact successful thread and turn receipt in the existing SessionRegistry. Ordinary jobs retain their previous execution mode. Exact remote follow-up/interrupt via App Server is not yet wired into the production Bot. Real source-system access, real PR/CI/QA, card callbacks, host credential identity and single-consumer rollback still require their separate gates. Do not silently switch the production consumer or mark C1–C5 complete.

## No enterprise API / no card permission: minimum viable operator path

**Feishu Project enterprise API is optional.** If the preexisting application bot can already receive and reply to messages, enable only `manual_workitems_enabled: true` in its existing private 0600 policy *after backing up the Bot's live state*. Keep `agent_intake_enabled` and model/card integrations unchanged. The same legacy WebSocket consumes `/wi` message commands, replies as text, and never asks the Project/TAPD API for data. It creates only an independent 0600 `feishu-engineering-agent.sqlite3` alongside the Bot state DB. Disabled mode safely rejects `/wi` without invoking Codex.

Examples (text commands in the **already-authorized** Feishu Bot chat):

```text
/wi help
/wi add tapd 缺陷 10104801 123456 repo=robot-app | 复现：低速回充过流；预期：不会误触发；请先评估
/wi add feishu_project 需求 project123 98765 repo=robot-app | 提升传感器初始化恢复；验收：断电重试正常
/wi list
/wi status <完整32字符AgentRun ID>
```

If `repo=` is omitted, the existing user's selected/default repository applies, still constrained by the sender's current allowlist. Input summary is **not persisted** (only hash, source message ID and WorkItem identity); paste fresh current requirement/bug context when separately asking for authorized Codex analysis/edit. `/wi add` only creates a proposed AgentRun and **does not** authorize a Codex call, code write, PR, QA or source-system closure. A missing trustworthy tenant identity in the actual SDK message must fail closed, not invent a tenant.

If **all Feishu app messaging scopes are unavailable**, a custom webhook bot cannot read incoming user chat or provide interactive cards. Use a Linux host-local CLI with no Feishu connection (type the command on stdin, finish with EOF; do not put sensitive summary on argv):

```bash
python -m tools.codex_assets.feishu_engineering_agent --manual \
  --db /absolute/private/feishu-engineering-agent.sqlite3 \
  --event-id local_bug_001 --allow-repo robot-app --selected-repo robot-app
```

Then enter `/wi add tapd 缺陷 10104801 123456 repo=robot-app | <完整问题与验收摘要>` on stdin. Repeat the same event ID + content only to check idempotency; use a new unique event ID for another command. `--manual` works only with the local UID's private SQLite file and never invokes Feishu or Codex. The filesystem directory must be privately owned and protected; do not use the existing Bot DB as `--db`.

| Gate | Minimal no-API mode | Extra API/card privilege |
|---|---|---|
| WorkItem intake | Local CLI or existing Bot text `/wi` | Project/TAPD read-only adapter optional |
| Run status | `/wi list`, `/wi status` | Card JSON 2.0 optional |
| Session | No model call in intake; independently authorized Codex CLI remains available | App Server exact-thread continuity requires host qualification |
| QA | Human verifies original requirement/bug in source system | Provider status update only after explicit policy/permission |
| Cutover | Do not replace old Bot/consumer without backup/restore | Same single-consumer invariant |

This changes the earlier C3 gate: **manual/source-provenance accuracy and access-control evidence** is required for the no-API path. Actual Project/TAPD API read is an independent optional enhancement, not a no-API launch blocker. A real low-risk message test still requires the existing authorized bot; all provider/source-system closure remains human-owned.

Sources for capability limits:
- https://open.feishu.cn/document/home/introduction-to-scope-and-authorization/overview
- https://open.feishu.cn/document/client-docs/bot-v3/bot-overview

## Local MCP handoff into the existing Bot worker

The source now includes a local stdio MCP bridge. It does not start a second Bot, network listener or Codex process. It writes a scoped task into the **existing Bot SQLite + private spool**; the existing single Bot worker remains the only executor.

Operator prerequisites (all private, never commit these values):

- Existing Bot policy: `agent_intake_enabled=true` and `manual_workitems_enabled=true`.
- The target repository's `agent_allowed_modes` must include the requested mode. Agent `edit` additionally requires `edit_strategy=worktree`, a separate `worktree_root`, and `commit_enabled=true`.
- Private `feishu.env`: `FEISHU_AGENT_BILLING_SOURCE=external_api_key` and `OPENAI_API_KEY`. For a non-OpenAI gateway or self-hosted endpoint, use `external_gateway` or `self_hosted` and set `OPENAI_BASE_URL` plus its API key.
- Private `FEISHU_AGENT_CODEX_HOME`: a pre-created directory owned by the Bot service UID with mode 0700 or stricter, separate from the normal `~/.codex`, outside repositories/worktrees, and with **no `auth.json`**. The Agent worker overrides both `HOME` and `CODEX_HOME` to this directory and passes only the dedicated API key / configured base URL; it does not inherit the interactive user's Codex home or ChatGPT login tokens. Shared `codex_shared` / `work_shared` identities are rejected.
- Run `scripts/feishu-agent-mcp.sh` as the **same Unix UID** as the Bot service. This is a local stdio process, not an exposed HTTP/MCP server.

Operator flow:

1. Register the external requirement/bug with `/wi add`, then prepare a source-linked handoff with `/wi handoff <RunID> | ...`.
2. Create an execution proposal with `/wi attempt <sourceRunID> edit | <精确范围与验收>`. This records only the SHA-256 of the scope, not the raw summary.
3. From the trusted local MCP client, call `submit_workitem_task(run_id, task)` with the exact same scope text. The bridge rechecks the WorkItem owner/repository/mode, scope hash, current policy digest, dedicated billing identity and Unix UID, then binds the AgentRun to one existing Bot task. A missing/ambiguous receipt becomes UNKNOWN; it is never rebound or replayed.
4. In Feishu, use `/wi status <sourceRunID>` for the most recent five linked attempts, or `/wi status <attemptRunID>` for an exact attempt and its recorded native thread ID (if available). Use `get_workitem_task(run_id)` on the trusted local MCP client to inspect the linked task and AgentRun receipt. `cancel_queued_task(task_id)` cancels only a queued task; a running Codex process is not falsely reported as interrupted.

The MCP process itself makes **no model call**. The existing Bot worker runs the queued task through its current Codex CLI runner. For linked WorkItems it uses persistent `codex exec --json`, requires a single successful terminal turn and canonical thread ID, and binds the receipt to the launched workspace, host and dedicated CODEX_HOME. `get_workitem_task` exposes the binding only to the authorized local Unix UID. The native transcript stays in the dedicated private CODEX_HOME; it is not copied to the task ledger. Receipt inspection is not authorization to resume a terminal run. Read/review may finish at AgentRun `completed`; edit finishes at `waiting_ci` with an unverified local commit receipt. This does not create a PR, claim CI/QA success, close the original Feishu Project/TAPD item or flash hardware. Those remain separately authorized delivery steps.

If the dedicated API identity is not configured, keep using `/wi add` and `/wi handoff` for no-model intake; do not set a fake billing-source label to bypass the gate.

## No-model handoff from the registered defect/requirement

Once `/wi add` replies with an exact `AgentRun` identifier, send this in the same authorized chat:

```text
/wi handoff <完整32字符AgentRun ID> | 最新问题、复现步骤、预期效果和独立验收要求
```

Or use the same `/wi handoff` input on the local `--manual` stdin CLI with a **new** `--event-id` (the original ID is for idempotency, not for a different command). It returns a copyable, source-linked, read-only SDD/bug-analysis brief **without** invoking Codex. When actually ready to develop, the engineer starts or resumes an independently authorized Codex CLI session in the target allowlisted repository and supplies fresh source context. The run remains `proposed` until independently verified work/evidence is recorded; no automatic QA closure or CI PASS is claimed.

## Source implementation prepared: operator-facing invocation

**Text mode (no enterprise API):** `/wi add` → `/wi handoff <RunID> | ...` → `/wi attempt <sourceRunID> edit | scope/acceptance`. The attempt is **proposed**, not executed. It can be handed to either (a) the native App Server path, which requires a separately signed `ExecutionApproval`, or (b) the local MCP bridge above, which requires explicit same-UID tool invocation, exact scope hash, current repo policy and a dedicated non-shared API identity. The chat command itself never approves or starts a model turn.

**Optional interactive card (same existing Bot only):** keep `engineering_cards_enabled=false` unless the authorized Feishu app has been configured for Card 2.0 callback. To enable in private, existing Bot policy must have `manual_workitems_enabled=true` plus `engineering_cards_enabled=true` and the service's **private** environment must contain `FEISHU_CARD_VERIFICATION_TOKEN` and `FEISHU_CARD_SIGNING_KEY_HEX` (>=32 random bytes encoded as hex). These are never committed. Validate actual SDK compatibility and 3-second ACK before the unique Bot is restarted; cards never grant model access.

**Local migration prep (no model/network calls):**

```bash
python -m tools.codex_assets.feishu_engineering_agent.migration_cli inspect \
  --db /absolute/private/feishu-codex-state.sqlite3 \
  --spool /absolute/private/feishu-pending-jobs

# Only after operator confirms the old Bot consumer is paused:
python -m tools.codex_assets.feishu_engineering_agent.migration_cli backup \
  --db /absolute/private/feishu-codex-state.sqlite3 \
  --spool /absolute/private/feishu-pending-jobs \
  --private-policy /absolute/private/bot.json \
  --backup-dir /absolute/new/private-backup-folder --consumer-paused

python -m tools.codex_assets.feishu_engineering_agent.migration_cli rehearse \
  --backup-dir /absolute/new/private-backup-folder
```

Paths are placeholders, not discovered production paths. The backup intentionally contains **sensitive private files** and must remain 0700/0600, outside Git or chat uploads. The tool neither stops a service nor creates a second Feishu listener; the operator must prove the systemd/lock single-consumer gate and verify the actual restore/restart separately.

**Future authorized SDK/API tests:** `SourceReconciler` requires a verified tenant-scoped reader; absent the API it returns `user_supplied_unverified`. `DeliveryCoordinator` uses an independent observer of PR/CI, short-lived explicitly approved PR publishing and a separate QA signer; source feedback is comment-only and optional. Explicit host verification is mandatory before promoting any of these source-level entrypoints.

**Optional concrete GitHub adapter:** `GitHubForge` takes an approved repository alias/full name, an injected `GitHubTransport` (fixed HTTPS API host, private token), an approved base branch and a disabled-by-default remote write switch. It verifies an already-pushed exact branch SHA and only then prepares a draft PR (not push or merge); `DeliveryCoordinator` independently requires a valid signed `PublicationGrant` and persists a remote effect receipt first. Read-only PR and CI observation each requires source SHA identity and completed CI status. GitLab or an internal forge may implement the same injected contract without changing WorkItem identity; no GitHub Issues are created. Private GitHub tokens, QA attestation HMAC keys, Feishu/TAPD creds and model billing identities must not be placed in repository config, chat or Codex child environment.

**Offline native protocol qualification before any real model turn:** On vstrong100 inspect the installed Codex version and generate its app-server JSON Schema to a **private temporary directory**, then compare `UserInput` and `SandboxPolicy` required keys with `sessions.py`. Generating a schema is not a model call. A green GitHub CI job does not prove that the host's installed Codex and schema match. Do not write or log host tokens while inspecting the schema. Only after the real host's approval routing, exact thread resume and sandbox are verified may a separately budget-approved model turn be considered.

Local MCP publication keeps the task row, exact Run link and private payload under a single Bot SQLite writer transaction; the worker only sees a queued row after the spool write succeeds. Failures retain UNKNOWN, concurrent duplicate submissions do not create a second task, and startup orphan cleanup is serialized with publication. The source ledger is separate; an unobserved crash still requires reconciliation, not automatic execution.

In the existing authorized chat, `/wi cancel <attemptRunID>` cancels only the linked queued task or requests termination of the exact active local Codex CLI subprocess. It never cancels all tasks sharing the service UID. An accepted termination request is not rollback or final cancellation; query `/wi status <attemptRunID>` afterward. Startup/finalization without a live process cannot be reported as interrupted. This is CLI subprocess cancellation, not native App Server turn/interrupt.

## Continue the same local Codex session
Use `/wi continue <previousAttemptRunID> | <new exact scope>` after a successful local read/review or an unpublished edit in `waiting_ci`. This creates a new proposed attempt under the same WorkItem with the same mode. Submit its new Run ID and exact scope through the existing trusted MCP `submit_workitem_task` (no model call from the MCP). The Bot worker resolves the prior completed task, original thread, host, CODEX_HOME, unchanged runtime policy, and original task worktree. For edit, the worktree must be clean and at the exact previous local branch/commit; the worker invokes `codex exec --json --sandbox ... -C <original cwd> resume <exact UUID> <prompt>`, requires the same returned UUID, verifies and commits the new result. There is no implicit `--last` or fresh worktree. One successor per successful predecessor prevents divergent/concurrent use of the same session; uncertain/failed/canceled predecessors cannot be replayed. An edit with reserved successor cannot be published by the old Run; existing PR/CI evidence blocks reuse of that delivery branch. A new independent attempt remains available if the chain is abandoned. Real host/provider and CLI version qualification are still required.

A continuation proposal can be revoked with `/wi cancel <proposedContinuationRunID>` before any execution approval. The same ledger transaction records cancellation and releases the predecessor's successor slot, so an abandoned draft does not block the previous branch forever. Approved, queued, running or uncertain turns are never released by this path. Status shows the previous and active successor Run IDs without exposing workspace paths.

## Actual local worker delivery (GitHub, optional)

Configure an explicit repository mapping in the existing private Bot JSON, for example under the relevant repositories entry:
~~~json
"github_delivery": {
  "repository": "owner/repository",
  "base_branch": "main",
  "required_workflows": [".github/workflows/test.yml", ".github/workflows/lint.yml"]
}
~~~
Absent this config, remote verification is disabled. The existing engineer's Git tooling publishes the exact worker branch/commit and opens a PR; this MCP does not push, create or merge PRs. For private GitHub read access configure FEISHU_AGENT_GITHUB_READ_TOKEN in the existing private MCP environment file (least-privilege PR/Actions read only; never place it in a chat, prompt, repo, or logs). Use a private env file covered by the existing deny_read_paths and protect the same-UID trusted operator boundary. No new listener or model call.

1. Use get_workitem_task(run_id) to inspect the completed local edit commit and branch. Submit verify_workitem_delivery(run_id, pr_number, ci_run_ids) with exactly one completed successful run ID per configured workflow. The adapter uses fixed GitHub GET endpoints, verifies repository/base/branch/head and PR association for pull_request workflows, and re-reads PR identity after the CI checks. Only pull_request/push events qualify. All proof references are stored together and the Run advances to waiting_qa, not product acceptance. Do not substitute a successful unrelated workflow.
2. An independently trusted QA reviewer may attest the same exact head using the existing DeliveryCoordinator.qa_message canonical payload and HMAC-SHA256. Configure FEISHU_AGENT_QA_REVIEWER and FEISHU_AGENT_QA_KEY_HEX (at least 32 random bytes, only in the protected verifier environment; reviewer holds signing key out-of-band). The MCP does not issue signatures; the same-UID host/operator is trusted, not a cryptographic isolation boundary against a compromised host. Submit accept_workitem_qa(run_id, reviewer, evidence_ref, attested_at, signature); the verifier rechecks the recorded GitHub evidence and validates the independent configured reviewer and exact signed head, then completes the engineering Run. Use get_workitem_task for the WorkItem fingerprint, head and proof. A lost response is resolved by querying status. Never accept your own engineering actor as QA.
3. Use /wi feedback <attemptRunID> from the authorized Feishu chat for a copyable status/evidence report. The source item is not automatically updated or closed. GitHub workflow success is a source observation, not device validation, fresh-main verification or product acceptance.

Existing signed PR publication adapters remain explicit, separately reviewed operations; this new path observes an already published branch and PR, and needs no GitHub write token.

The same GitHub GET-only verification is available directly in the existing authorized Feishu chat: `/wi delivery <attemptRunID> <PR-number> <CI-run-ID> ...`. It resolves the caller's exact local Run first and uses only the configured repository, required workflow set and private read token. The message does not accept arbitrary URLs, caller-supplied commit SHA, or a success claim. The existing private environment supplies the optional read token to both Bot and MCP; the Feishu-prefixed token is excluded from child process environment. Keep the private file under the masked deny_read_paths. QA remains independently attested through the trusted local MCP path.

## Consolidated deployment and backup contract
The only live-source executor is the existing Bot CLI worker. App Server `experimentalApi`, persistent `thread/start`, and exact `thread/resume` checks from #79 are retained only as offline native protocol primitives; no live process manager is required or launched for the CLI pilot. Freeze the Bot **and trusted local MCP submissions** before backup. The migration CLI now detects the sibling `feishu-engineering-agent.sqlite3`, snapshots both WAL-aware ledgers, checks their task/run/repository/mode links, and optionally copies `--private-env` with private policy. A missing ledger when links exist or inconsistent identities prevents verification. The isolated rehearsal does not alter source files or restart systemd. Preserve the actual dedicated CODEX_HOME and all active worktrees separately; this is a database/spool/config snapshot, not a full host image. Existing `--consumer-paused` is operator attestation, not proof that the service stopped. Do not run a live model or cutover without separate host evidence.
