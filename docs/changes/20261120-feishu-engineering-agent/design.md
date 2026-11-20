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
