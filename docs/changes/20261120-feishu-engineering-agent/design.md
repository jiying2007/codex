# Feishu Engineering Agent — Design

## Boundary
Build a slim domain core inside tools/codex_assets/feishu_engineering_agent, consistent with repository AGENTS instructions. It is NOT wired to the production Bot until phased cutover. The existing Feishu Bot still owns runtime, private spool and its SQLite state. First SDD slice has zero model/network side effects.

Logical components, not separate processes: Channel adapter (Feishu message/card; future external webhook) -> deterministic identity/intent -> WorkItem registry/AgentRun -> gated Codex native adapter -> Git/CI/QA evidence -> Feishu card response.

## Distinguish source and execution
WorkItemKey = (provider: feishu_project | tapd, tenant, workspace, kind: requirement | defect, item_id).
Provider data, actual user approval and external status remain in provider. Never copy the whole WorkItem into an authoritative local ticket.
AgentRun = own run ID + actor, repo, approved action, evidence IDs, exact Codex thread/host/CODEX_HOME, status. One WorkItem can have multiple Runs, and multiple repos can have independent Runs; one UART/API contract is a single versioned artifact for SoC/MCU.

## S1 deterministic ingress and security
Input = authenticated InboundEvent(source, tenant, chat, actor, event_id, text) plus explicit allowlisted aliases. This core does not authenticate a Feishu wire event itself; adapter must verify the source.
Output = decision(kind, repo, task_id?, requires_approval, run_enqueued=false, reason).
Recognition includes status/help, project show/switch, read/review proposal, write proposal, exact task ID status/continue/cancel. No arbitrary username or issue link can assign a worktree or model turn. Unknown input returns CLARIFY.
Defaults to read-only suggestion. A write verb NEVER auto-executes. If no project has been explicitly selected, return a need-project result. Invalid or unauthorized aliases fail closed.

Private offline store only for TASK-001: actor project selection key=(tenant,chat,actor); processed event key=(source,tenant,chat,actor,event_id), with sha256 digest and resulting action/repo, BEGIN IMMEDIATE transaction. No prompt text persisted, raw prompts and secrets are not logged. This database uses a separate tempfile in tests, never production SQLite.

## Later state and cards
AgentRun lifecycle NEW -> READY -> QUEUED -> RUNNING -> WAITING_CI -> WAITING_QA -> COMPLETED, plus BLOCKED/NEEDS_INPUT/FAILED/UNKNOWN/CANCELED. External provider owner validates actual feature/Bug closure; status reports never fabricate closure.
Feishu card action: verified operator, card/run binding, idempotency key, persist command, immediate ACK; async runner does actual approved work and updates status from durable outbox. Card 2.0 14-day validity; expired cards should be replaced or fall back to safe text status.
External WorkItem webhook: dedicated authenticated ingress, tenant/provider/version/UUID idempotency, no public anonymous port. vstrong100 chat WS cannot receive Meegle/TAPD webhooks automatically. Start with user-pasted link and scoped read-only API.

## Codex execution qualification
Prefer native App Server if real 0.170.0 (or next deployed version) passes protocol/approval/resume qualification; CLI exec with exact context is read-only fallback. Never resume by --last or arbitrary session file. Fees and actual model turns remain disabled pending explicit permission.
Actual edit requires allowlisted repo + separate explicit action approval + isolated worktree + Git verification; merge/flash/release is never part of general chat intent.

## Migration
0. No model: new code and tests; no production import.
1. Capability test using authorized non-production Feishu app and single test consumer; verify cards/buttons.
2. Real runtime session compatibility, identity and interrupt; no model call without budget authority.
3. Feishu Project and TAPD read-only WorkItem evidence; one real feature/one Bug with PR/CI/QA.
4. Freeze old queued/running/UNKNOWN, preserve WAL/spool/keys outside Git, backup+restore, shadow compare decisions without duplicate consuming, switch only one active listener and keep rollback.

Explicitly avoid new Redis, Postgres, UI admin panel, second state owner, scheduled checks or agent orchestration framework.

## Implemented offline extension and explicit non-goals
- `state.py`: private RunStore (a sibling of the separate offline intake DB); optional external WorkItem fingerprint, many AgentRuns per WorkItem, optimistic state transitions, immutable source evidence refs. No original ticket status mutation.
- `cards.py`: JSON 2.0 signing uses a host-private HMAC secret and stores source card, exact posted message and requester identities; an authenticated callback records one intent per revision in a single transaction and returns a fast toast. `request_execution` is a **request** only and does not grant a Codex budget or edit permission. Sender must bind the returned message id and later update card from durable truth.
- `sessions.py`: exact actor/tenant/chat/repo/host/repo_path/CODEX_HOME/thread_id binding; read-only resume request builder and interrupt builder; turn planner is disabled without a fresh non-shared in-memory RuntimeGrant and a default-off runtime switch. Request planning does not prove transport, approvals or actual model spend.
- `workitems.py`: fixed/provider-configured API origin, injected transport, read-only query, strict tenant/project/kind/id/version comparison; response text is untrusted input, not permission.
- No second consumer, no webhook listener, no scheduler, no Codex model process and no PR/QA/firmware operations are introduced by this extension.

## Single-consumer integration implementation
`channel.py` adds a default-off, injectable same-process publisher and card callback factory; `FeishuTransport.start` optionally registers `card.action.trigger` with its **existing** WebSocket event dispatcher, but `FeishuCodexBot.start` still uses only its original message callback. The publisher persists a send attempt before remote I/O and treats lost ACK as UNKNOWN, without retry. The callback follows the provider's **nested** `event.context` and `event.host` envelope, checks provider identity, message binding, HMAC, replay and 14-day expiry, and ACKs only after persisting an unprivileged intent. No additional model executor, connection, service or timer is started.
`--probe-runtime` is a host-local help/version-only Codex CLI capability check. It does not qualify authenticated App Server protocol, restore or a paid model call. See [pilot.md](pilot.md) for manual gates and rollback.

## Card interaction UX reconciliation
A read-only `status` click is idempotently receipted but **does not consume the card revision**; independent status clicks remain usable. A `request_execution` or `request_cancel` click consumes the previous card revision, persists an unprivileged pending intent, and the callback returns an updated raw Card 2.0 view with the mutating buttons hidden until a trusted worker reconciles the intent. A repeated callback ID returns a duplicate toast. A later distinct click on the consumed revision fails closed. This is an offline interaction contract; a real mobile/desktop callback test is still required.

## No enterprise API path
`manual_items.py` is the minimal trusted-transport input adapter for two situations: optional same-process Feishu chat `/wi` commands, and local stdin CLI with no Feishu connection. It accepts **explicit** provider (TAPD / Feishu Project), requirement/defect kind, workspace, item ID and bound repository; the user supplies a summary but this is **not** a fetched WorkItem. It persists a private 0600 SQLite `fea_manual_claims` event receipt and an AgentRun in one transaction. The receipt stores SHA-256 of summary, message ID and provenance `user_supplied_unverified`, **not** the description. Crash/duplicate delivery never starts a paid turn. The existing private queue/spool continues to own any separately authorized Codex job.
The feature is controlled by `manual_workitems_enabled=false` in the existing Bot policy. When enabled the new ledger uses the sibling `feishu-engineering-agent.sqlite3`, never the Bot's task DB. The existing WebSocket listener intercepts only the reserved `/wi` prefix; it rechecks authenticated tenant header, chat, actor and repo allowlist before inserting. When disabled it fails with a text help reply rather than spending models. No second listener, scheduler, callback permission or WorkItem API is requested.
The local `--manual --db /absolute/private.sqlite3 --event-id ID --allow-repo alias --selected-repo alias` command takes the `/wi` body exclusively from stdin; scope is the local Unix UID, not a spoofable requested actor. For work needing the original description after a restart, the user must provide current text again in an authorized development request; the prior summary is not stored. Source verification, approval to execute, PR/CI proof and independent QA are different gates.

The optional message bridge also has an independent bounded per-sender limiter. A burst of authorized `/wi` submissions cannot bypass the legacy Bot's rate protection or enqueue paid Codex turns; rate-limit rejection is a text-only outcome.

## Bounded chat event callback
The reserved `/wi` handler validates sender, tenant and command prefix on the SDK callback thread but **dispatches its SQLite transaction to a bounded-rate daemon worker**. The listener can return before a SQLite busy timeout; the persistent unique receipt prevents duplicate Run creation under Feishu event replay. The worker sends only the resulting text reply. If work failed or remote reply delivery is unknown, no model/Git action is attempted. There is still one WebSocket consumer and no new polling process.

## No-API WorkItem-to-development handoff
The smallest useful step after `/wi add` is **`/wi handoff <run_id> | <fresh current requirement/bug details>`**, served by the same no-API text-command handler and the local stdin CLI. It reads the owner's already registered WorkItem metadata, checks original tenant/chat/actor and current repository permissions, requires that the Run is not UNKNOWN/CANCELED/BLOCKED and generates a bounded, copyable read-only research/SDD brief in the response. The latest supplied contents remain ephemeral. No Codex turn, PR, status transition, card, external API or device action is launched. Actual implementation requires a separate authorized Codex CLI/SDD workflow and new evidence; the original source owner performs QA/closure.

## Source-complete implementation map (small team, one process)
The **existing** `FeishuCodexBot` remains the only listener. `manual_items` handles reserved `/wi` text commands and `CardPublisher` is opt-in under private keys. `EngineeringWorkflow` creates independently scoped development attempts from the exact original WorkItem. `SessionRegistry` and `NativeTurnCoordinator` attach only a qualified host and exact native Codex thread; `StdioAppServer` provides bounded stdio RPC framing and does not decide permissions. `DeliveryCoordinator`, `SourceFeedback` and `ContractRegistry` coordinate Git, independent QA and multi-repository evidence, not model tools or an alternative PM system.

**Effects:** `proposed → queued` requires signed host policy scope with SDD review for editing, current repo authorization and non-shared billing source. A queued run is not an executed turn. A turn/start and external PR/comment send persist an effect receipt **before** remote I/O; interrupted, timed out or lost replies become UNKNOWN and cannot be replayed. A turn/start ACK is not completed; only correlated `turn/completed` can progress to CI. PR/CI evidence from an independent Git observer plus independent signed QA can close an AgentRun, **never** a source WorkItem. Source feedback is manually copyable without API; authorized API comments do not change original item status.

**Cross repo:** `ContractRegistry` stores immutable contract version and content hash for 2–8 repositories. Each repo must provide exact-version/CI evidence. It does not report device verification or product release without actual HIL/QA.

**Privileged boundary:** host-provided HMAC grant keys, card signing keys, QA verifier keys and provider tokens live outside Git. A user-entered text/card action alone never becomes a runtime grant. SDK callback, App Server and actual model/remote effects are separately qualified. No extra recurring worker, Redis, PostgreSQL, Kubernetes, second consumer or generic Agent graph is added.

**Bot config:** `engineering_cards_enabled=false` and `manual_workitems_enabled=false` by default. Enabling cards additionally requires existing message permission, manual workitem mode and private `FEISHU_CARD_VERIFICATION_TOKEN` plus at least 32-byte `FEISHU_CARD_SIGNING_KEY_HEX`. Card send uses the existing FeishuTransport. Callback only stores action intent; `CardActionQueue` can resolve it, but model execution remains behind independent HMAC+runtime gates.

**Migration:** `migration_cli.py` inspects private state, creates WAL-consistent backup after the operator has paused the existing consumer, and rehearses restore into a disposable location. `cutover_gate` stays false until independent host/backup/restore/singleton evidence is provided. It never starts or stops the real service itself.

**Concrete Git option:** `GitHubForge` offers a fixed-origin, repo-allowlisted REST adapter for draft PR creation and exact-head PR/Actions read. No Git push, merge, repo settings or Issue mutation. PR publication in `DeliveryCoordinator` additionally requires an independent private HMAC signature over the exact short-lived `PublicationGrant`. `SourceFeedback.post_once` analogously requires a separate source-comment signature scoped to original work item, revision, actor and operation; its effect can never close the source item. Without these signatures or writable credentials, both remain disabled.

## Source security convergence — canonical evidence and native sequencing
- Delivery has one per-AgentRun exact, immutable commit SHA pinned by independently observed PR/CI evidence and, if available, the acknowledged publication attempt. The Git observation and pin are one SQLite transaction. Independent signed QA must attest to **that same SHA**; combining PR, CI and QA from different revisions cannot mark an edit complete.
- A read/review AgentRun can finish from its own correlated native terminal event without demanding a code PR or product QA. An **edit** transitions to waiting_ci and can complete only after independently observed PR, CI, matching-head signed QA. In all cases external WorkItem closure remains a product/test action.
- The native turn execution boundary requires a durable, separately issued signed approval receipt in addition to an in-memory grant and the explicit model-calls-enabled switch. Replays cannot rebind a WorkItem or reuse an approval after the Run began; no new shared quota is authorized.
- App Server notifications, including terminal events delivered before turn-start acknowledgement, are buffered in a bounded queue. Only the existing host event loop drains them after the exact turn is persisted. Overflow fails closed as UNKNOWN; the stdout reader never blocks on user callback/model operations.
- Optional source reads always recheck the current repository allowlist before attempting a provider API request; revoked access cannot disclose source data.

## Codex App Server v2 request serialization (source review)
Compared against upstream `openai/codex` TypeScript protocol definitions for `v2/UserInput.ts`, `v2/SandboxPolicy.ts`, `v2/TurnStartParams.ts` and `v2/ThreadResumeParams.ts`. A text `turn/start` input needs `text_elements: []`; read-only sandbox explicitly specifies `networkAccess: false`, and workspace-write sandbox specifies `writableRoots`, `networkAccess`, `excludeTmpdirEnvVar` and `excludeSlashTmp`. No direct `--last` or guessed thread resume is allowed. This is **source schema consistency only**; the deployed vstrong100 executable may differ. During later field qualification, generate the exact installed version's schema with `codex app-server generate-json-schema` and compare before enabling model calls. Tool approval requests are never auto-approved.
