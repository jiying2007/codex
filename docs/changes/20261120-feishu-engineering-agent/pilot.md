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

The live Bot's message handler still follows its existing intake/queue and `FeishuCodexBot.start` still calls `transport.start(self.on_message)`; **the new card callback is not yet activated**. The real integration requires a guarded configuration flag, deployment-managed credential, trusted event identity adapter, effects/outbox dispatcher and a checked rollback plan. Do not silently switch the production consumer or mark C1–C5 complete.

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

## No-model handoff from the registered defect/requirement

Once `/wi add` replies with an exact `AgentRun` identifier, send this in the same authorized chat:

```text
/wi handoff <完整32字符AgentRun ID> | 最新问题、复现步骤、预期效果和独立验收要求
```

Or use the same `/wi handoff` input on the local `--manual` stdin CLI with a **new** `--event-id` (the original ID is for idempotency, not for a different command). It returns a copyable, source-linked, read-only SDD/bug-analysis brief **without** invoking Codex. When actually ready to develop, the engineer starts or resumes an independently authorized Codex CLI session in the target allowlisted repository and supplies fresh source context. The run remains `proposed` until independently verified work/evidence is recorded; no automatic QA closure or CI PASS is claimed.

## Source implementation prepared: operator-facing invocation

**Text mode (no enterprise API):** `/wi add` → `/wi handoff <RunID> | ...` → `/wi attempt <sourceRunID> edit | scope/acceptance`. The attempt is **proposed**, not executed. A trusted host policy issuer must separately sign an `ExecutionApproval` containing actor, tenant, chat, repository, mode, reviewed SDD, billing identity and expiry. A Codex model turn cannot be triggered directly by this chat command.

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
