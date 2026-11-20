# Feishu Engineering Agent — Proposal
Date: 2026-11-20. Scope: one deployed Bot on vstrong100, personal and 2–8 person development team.

## Brainstorm decision
Choose **strangler migration of the business core**: rewrite channel interaction, workitem association, session binding and delivery lifecycle as separate Python modules inside tools.codex_assets; reuse the tested security policies, private spool, SQLite fail-closed behavior, Git/worktree and Codex runtime. Do not create a second general agent platform.

| Option | Benefit | Decisive counterexample | Result |
|---|---|---|---|
| Grow current 2200-line Bot | No new deployment | Coupled card callbacks, WorkItem/Run, Codex sessions and DB make changes fragile | Legacy bridge only |
| Introduce universal agent platform | Many packaged workflows | Repeats eng/second billing, identities, state and permissions | Reject |
| Rewrite thin domain + Feishu channels | Domain-first, testable, existing safety reused | Must prove cutover, owner and schema migration | **Select** |
| Rebuild entire runtime/queue/runner | Uniformity | Reintroduces solved sandbox, credentials, UNKNOWN and duplicate-call bugs | Reject |

## Decision registry / evidence status
| ID | Choice and dependency | Status | Answer source and falsifier |
|---|---|---|---|
| D-01 | Replace business/channel core in Codex repository, keep single service | proposed | AI recommendation based on existing Bot source; falsify if isolation breaks vstrong100 migration |
| D-02 | Original Feishu Project/TAPD remains WorkItem authority | confirmed as user constraint | Actual product/test work starts in those systems, not GitHub Issue |
| D-03 | Card first, not streaming token UI | proposed | Official card limits; falsify with real phone/desktop user test |
| D-04 | App Server vs exact-ID CLI resume | unresolved | Depends on actual deployed CLI capability and model budget approval |
| D-05 | Read-only WorkItem adapter first; authenticated webhook later | proposed | Depends on real Meegle/TAPD tenant access and inbound network evidence |
| D-06 | No unapproved shared Codex/Work quota; no autonomous model loops | confirmed as existing resource boundary | Any paid turn requires separate current authorization |

## Canonical Change Contract
REQ-001 → ADDED → natural-language ingress → ACC-001 → TASK-001 → VERIFY-001;
REQ-002 → ADDED → scoped project context → ACC-002 → TASK-001 → VERIFY-002;
REQ-003 → ADDED → typed external WorkItem identity → ACC-003 → TASK-001 → VERIFY-003;
REQ-004 → ADDED → fail-closed proposal/approval → ACC-004 → TASK-001 → VERIFY-004;
REQ-005 → ADDED → idempotent receipts → ACC-005 → TASK-001 → VERIFY-005;
REQ-006 → ADDED → Feishu cards → ACC-006 → TASK-002 → VERIFY-006;
REQ-007 → ADDED → exact Codex thread → ACC-007 → TASK-003 → VERIFY-007;
REQ-008 → ADDED → Feishu Project and TAPD read-only adapters → ACC-008 → TASK-004 → VERIFY-008;
REQ-009 → ADDED → Feature/Bug PR/CI/QA lifecycle → ACC-009 → TASK-005 → VERIFY-009;
REQ-010 → ADDED → recovery/remote unknown outcomes → ACC-010 → TASK-005 → VERIFY-010;
REQ-011 → MODIFIED → single-consumer Bot cutover → ACC-011 → TASK-006 → VERIFY-011;
REQ-012 → ADDED → cost/runtime/device authorization → ACC-012 → TASK-006 → VERIFY-012.

## User-facing goal
Chinese natural language, current project context, task card, exact continuous Codex thread. Real requirements and defects from Feishu Project or TAPD drive brainstorming, SDD, authorized implementation, PR/CI, real QA/device verification and feedback to the original work item. No need to duplicate a GitHub Issue.

## Irreducible facts and ownership
- WorkItem is an external requirement/defect with provider, tenant, workspace, kind, ID and version; original system is canonical.
- AgentRun is a bounded analysis/edit/test attempt with its own run ID, actor, approved scope, exact workspace, session, outcome, Git/CI and device evidence.
- Chat and cards are interaction, not the WorkItem source of truth; Codex sessions are not Product/QA status.
- Natural language does not authorize edit, merge, device flash or paid model calls.
- The current prohibition on shared Codex/ChatGPT Work model quota remains unless separately approved; no new timers or faux "continuous" check jobs.
- No production code/config/systemd write is in TASK-001.

## Integration constraints verified from primary documentation
Feishu application cards support persistent-connection callbacks and update APIs. The callback must respond quickly (documented 3-second deadline); card 2.0 interactions/updates have a finite 14-day window. Expired cards are not task state authority.
Feishu Project/Meegle has distinct plugin/workitem API permissions and WorkItem webhooks; TAPD has separate Story/Bug API and webhook configuration. The chat WebSocket will not magically deliver these provider webhooks. Start with explicitly authorized read-only fetch by workitem link; add an authenticated webhook gateway only if required.
Codex exec is appropriate for isolated jobs; Codex App Server exposes thread, turn, approval and streaming event control. Actual deployed version and transport must be qualified before switching.

## Rebuild boundaries
Rebuild: Feishu adapter, deterministic intent, project context, WorkItem canonical keys, AgentRun lifecycle, cards, exact session binding and slim delivery coordinator.
Reuse: existing Codex CLI and eventual App Server, current sandbox/denied paths, worktree, commit safety, SQLite fail-closed invariants, existing ADK and project CI/HIL.
Do not build: generic agent graph engine, multi-model provider broker, PM duplicate, Redis/Postgres/K8s cluster, self-managed approval website.

## Real scenarios for final acceptance
- Personal project switch and Chinese code analysis with default read-only.
- Feishu Project requirement → SDD → authorized code/PR/CI → product verification.
- TAPD Bug → reproduction/negative test → fix/PR/CI → QA retest.
- SoC/MCU protocol contracts across repositories with independent verification; device proof cannot be inferred from CI.
- Long-running KWS/Audio uses the existing Actions experiments, not a new Feishu scheduler.

## Source references
- https://developers.openai.com/blog/codex-as-a-platform
- https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/quick-start
- https://open.feishu.cn/document/feishu-cards/configuring-card-interactions
- https://www.feishu.cn/content/49fq0rvm
- https://www.feishu.cn/content/60bl79n2
- https://open.tapd.cn/document/api-doc/

Source facts do NOT certify access to the user's tenant, running Card callback, App Server or model billing.

## Current implementation boundary (2026-11-20)
The PR now adds an **offline** AgentRun ledger, Card JSON 2.0 builder and signed callback-intent store, exact Codex thread binding/RPC planner, and injected read-only TAPD/Meegle readers. No production Feishu event handler is subscribed; no Codex App Server is spawned for a turn; no remote source item or QA account has been accessed. Full task completion still depends on production capability/permissions and end-to-end tests. A successful callback only records an intent, not an execution approval or a running model. Historical TASK-001 CI evidence remains tied to its original SHA.

## Deployment decision: enterprise WorkItem API is optional
User may not have the Feishu Project enterprise API. Shipping this helper must not require it. The existing application bot can continue using already approved message receive/reply scopes; the Feishu Project OpenAPI, interactive card callbacks and TAPD API are separate optional privileges. Without even the bot's messaging scope, use local stdin CLI only; an incoming-only webhook-only custom group bot cannot act as a two-way user-message listener. No credential scraping or simulated provider verification.
Minimum delivery: typed WorkItem source metadata + manual free-text summary + user-supplied provenance + independent AgentRun + text status. Never equate a pasted description with provider truth or QA acceptance. No change to source WorkItem until the original product/test owner acts in that system. External source API read is an optional later enhancement and shall not gate no-API registration.
Sources: https://open.feishu.cn/document/home/introduction-to-scope-and-authorization/overview and https://open.feishu.cn/document/client-docs/bot-v3/bot-overview .

## Source-complete delivery cut (no live tenant/host qualification)
This PR implements TASK-001..006 at the **source/isolated contract level**, not as a parallel platform or a replacement for the Codex native harness. The user can register and hand off work without the Feishu Project/TAPD enterprise API; separately approved operations use the *same* WorkItem identity and distinct AgentRun records.

Native Codex App Server, source comments, PR writes, card sending, QA attestation and Bot cutover are off by default and cannot inherit authorization from chat. The existing Bot remains the only active production consumer. The available source-level gateway is deliberately transport-injected; the real network, model and HIL field evidence will be collected in a later centralized campaign.
