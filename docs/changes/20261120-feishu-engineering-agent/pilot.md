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
