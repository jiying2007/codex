# Feishu Engineering Agent — SDD Requirements

## Canonical Change Contract
| REQ | Delta and owner | Acceptance | Task | Evidence |
|---|---|---|---|---|
| 001 | ADDED natural-language deterministic intake, routing | ACC-001 | TASK-001 | VERIFY-001 |
| 002 | ADDED user+tenant+chat scoped project context | ACC-002 | TASK-001 | VERIFY-002 |
| 003 | ADDED typed external WorkItem source identity, not a second PM authority | ACC-003 | TASK-001 | VERIFY-003 |
| 004 | ADDED fail-closed edit/approval and source authorization | ACC-004 | TASK-001 | VERIFY-004 |
| 005 | ADDED idempotent message receipts and private context storage | ACC-005 | TASK-001 | VERIFY-005 |
| 006 | ADDED task cards and bounded callback, card refresh | ACC-006 | TASK-002 | VERIFY-006 |
| 007 | ADDED exact Codex thread continuity and version capability check | ACC-007 | TASK-003 | VERIFY-007 |
| 008 | ADDED Feishu Project and TAPD read-only WorkItem adapters | ACC-008 | TASK-004 | VERIFY-008 |
| 009 | ADDED feature/bug SDD-to-PR/CI-to-QA delivery | ACC-009 | TASK-005 | VERIFY-009 |
| 010 | ADDED external-effect recovery, no replay on UNKNOWN | ACC-010 | TASK-005 | VERIFY-010 |
| 011 | MODIFIED old Bot cutover: single consumer/restore | ACC-011 | TASK-006 | VERIFY-011 |
| 012 | ADDED explicit model quota, git and device authorization | ACC-012 | TASK-006 | VERIFY-012 |

## Acceptance criteria
ACC-001: Chinese commands such as 切换到 robot-app 项目 and 分析 sensor 初始化 result in bounded project/read-only proposals; unknown or ambiguous wording never implicitly starts a model.
ACC-002: preference is isolated by tenant+chat+user; unauthorized repo never selected; no global mutable last-project.
ACC-003: exact provider+tenant+workspace+kind+item ID is required; same number in TAPD and Feishu or different workspaces never conflicts; bare text is not a verified WorkItem.
ACC-004: 修复/开发/实现 yields a WRITE_PROPOSAL requiring separate execution approval; explicit task continuation needs task ID; no bypass via card callback.
ACC-005: same inbound event and same digest produces one decision and one preference transaction; conflicting content with same event ID is rejected; private SQLite contains no prompt body.
ACC-006: true queued/running/terminal card; stale card/click duplicate/wrong user denied; Feishu 3s ACK and 14-day update expiry respected.
ACC-007: resume bound to actor, tenant, repo, target host, CODEX_HOME, exact session/thread and state; no guessing --last.
ACC-008: verified read-only Meegle/TAPD WorkItem payload/version/permission; 403/404 or unknown scope fail closed.
ACC-009: one low-risk feature and one low-risk bug must produce real source, checks, PR and independent QA evidence; CI alone is not QA/HIL.
ACC-010: event, card, PR and external write receipt idempotent, running after restart UNKNOWN and no blind model repeat.
ACC-011: old service queue, WAL, spool, source and systemd captured with restore proof; only one active consumer.
ACC-012: external billing identity, per-repo policy, model and quota explicitly approved; no use of Work/Codex shared allowance without fresh authority.

## Initial no-model scope: TASK-001
Pure deterministic no-model router, typed WorkItem identity, isolated SQLite event receipts and project context, offline dry-run CLI and Python 3.8/3.11/3.12 full regression. No Feishu events subscription, webhook, real Codex turn, Git push, server restart or new permission in this PR.

## Implementation extension in PR #73 (offline)
- TASK-002 code: signed Card JSON 2.0 callbacks, verified envelope, card/message/actor binding, 14-day expiry and SQLite click receipts; **no real client or 3-second field test**.
- TASK-003 code: exact host/repo/CODEX_HOME/thread binding, resume/interrupt request builders, explicit quota and model-turn gates, no-model host capability probe; **no live App Server protocol turn**.
- TASK-004 code: injected read-only TAPD GET stories/bugs and Meegle plugin-scoped query; typed source snapshot and version check; **no tenant credentials or real source response yet**.
- TASK-005 code: separate WorkItem/AgentRun ledger, immutable evidence references, guarded transitions, independent QA proof requirement; **no real feature or bug PR/CI/QA evidence**.
- TASK-006 deliberately unmodified: production Bot remains the only active consumer.
