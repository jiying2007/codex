# Feishu Engineering Agent — Verification plan

| VERIFY | Test/observation | Status |
|---|---|---|
| 001 | Natural Chinese intent/unknown/bad whitespace/malformed command, no subprocess | pending CI |
| 002 | Different tenant/chat/user project scopes, unauthorized alias rejected | pending CI |
| 003 | Typed provider+tenant+workspace+type+id identity, cross-space collision negatives | pending CI |
| 004 | Write proposal requires approval, continue/cancel exact ID, no model call | pending CI |
| 005 | BEGIN IMMEDIATE dedupe, conflicting event digest fail closed, no raw prompt stored | pending CI |
| 006 | Real card callback within 3 sec, retry/wrong user/expiry | not performed |
| 007 | Exact Codex thread/host/user resume and approved budget | not performed |
| 008 | Real scoped Feishu Project and TAPD WorkItem API read | not performed |
| 009 | One feature and one Bug actual PR/CI/QA; devices separately | not performed |
| 010 | Remote UNKNOWN/outbox replay fault injection and recovery | not performed |
| 011 | vstrong100 single Bot consumer live migration and backup restore | not performed |
| 012 | Explicit runtime cost identity and per-scope approval | not performed |

Current PR source/CI may prove only VERIFY-001..005. CI success is NOT evidence of real Feishu, card, App Server, billing, project API, GitHub PR publication, device HIL or QA.
Every reported PASS must include exact SHA, command+exit, time, environment, source reference and checked scope.

## Next exact-HEAD receipt requirements
The additional offline tests in `tests/test_feishu_engineering_workflows.py` cover card signatures/replay/actor/message/expiry, run transitions/independent QA, Codex exact session and budget gates, and TAPD/Meegle source validation. They are **not counted as passed** until this PR's new commit CI completes. The 9/9 prior checks apply only to the prior SHA. Real Feishu, deployed App Server, tenant API, PR publication, QA and production cutover are separately marked unverified regardless of CI.

## Channel and protocol regression cases
- Same existing WebSocket consumer, optional callback disabled by default.
- Card callbacks accept either top-level or event-nested host/context only when identities agree; conflicting or missing fields fail closed.
- Interactive send records `sending` before I/O; lost receipt becomes UNKNOWN without resend.
- No-model `--probe-runtime` success/failure paths and invalid combined arguments.
- All new checks require a fresh exact-SHA CI receipt. They do not qualify real callbacks or tenant permissions.

## No-enterprise-API regression (new coverage)
- `test_feishu_engineering_manual_items.py`: strict manual parsing, real provider identity isolation, read-only status/list, user/tenant/chat/repo isolation, SQLite 0600/no raw prompt, atomic duplicate/conflict receipt, local CLI stdin without an SDK or API.
- `test_feishu_engineering_manual_bot.py`: optional same-consumer message interception, disabled mode never reaches Codex gate, bad tenant/actor/chat or repo is denied, old non-`/wi` intake unchanged, legacy queue has no new jobs.
- These offline tests **cannot** prove enterprise tenant permissions, SDK message-event header shape on vstrong100, a real Lark send, or any QA/PR success. Record their exact successful workflow run IDs only after current HEAD CI.

Manual message rate-limit negative test: six unique `/wi add` events under default 5-per-window must create only five proposed runs, never a legacy queued/model job.

Additional regression: the Feishu message listener enqueues at most one bounded manual-intake worker and returns before SQLite I/O; the test invokes the captured worker separately to prove no synchronous database transaction or Codex job inside the event callback.

## VERIFY-017/018 (offline tests; not field qualification)
- Manual WorkItem `handoff` includes current supplied acceptance but no new Run/receipt or prompt storage.
- Different tenant, chat, actor or no-longer-authorized repository cannot read handoff; UNKNOWN/CANCELED/BLOCKED cannot be handed off.
- Requirement handoff suggests brainstorming/SDD, defect handoff prioritizes reproduction/negative testing; neither auto-launches Codex, Git, card or API.
- Bot no-API reply uses existing authorized text route and retains a zero-model-call invariant. Validate on exact new SHA before marking PASS.

## Consolidated offline verification matrix
All new tests use in-memory/mock transports, private temporary SQLite files and no model/Feishu/TAPD/Git network credentials.

| Test file | Contract |
|---|---|
| `test_feishu_engineering_native.py` | initialize/initialized, exact thread, turn ACK≠completed, bad actor/home, no implicit budget, interrupt/UNKNOWN, tool approval refusal |
| `test_feishu_engineering_delivery.py` | one-shot PR, trusted PR/CI, independent QA HMAC, original WorkItem remains open, optional source comment/UNKNOWN |
| `test_feishu_engineering_cards_complete.py` | both documented callback layouts, conflict fail-closed, request vs grant separation, pre-run cancel, existing Bot opt-in |
| `test_feishu_engineering_workflow.py` | source WorkItem → several separate Run attempts, event idempotence, signed SDD/billing/repo scope, disabled model by default |
| `test_feishu_engineering_contracts.py` | immutable multi-repo version, per-participant verification, no fake device/HIL |
| `test_feishu_engineering_source_bridge.py` | optional provider read, exact identity/version, no raw provider body persisted |
| `test_feishu_engineering_migration.py` | SQLite/spool/policy private backup, checksum tamper, restore rehearsal, fail-closed cutover |
| `test_feishu_engineering_end_to_end.py` | mock Feature + Bug from source registration through native turn, PR/CI, independent QA and human-owned source acceptance |

Required offline CI: Python 3.8/3.11/3.12 full repository tests, profile context, runtime binding, pre-apply, isolated apply/no-op/rollback on **exact** final HEAD. No offline test is evidence of paid Codex behavior, live app-server protocol, tenant permissions, actual Git publication, SoC/MCU HIL or independent product/test closure.

**Centralized field campaign, to be scheduled after code integration:** (1) vstrong100 host and Codex version/identity/charge; (2) real Feishu message/card permissions & callback timing; (3) TAPD/Meegle optional read; (4) one Feature + one Bug actual Git/CI/QA; (5) one multi-repo contract + device proof when relevant; (6) single-consumer migration/rollback. For any inaccessible API, record a blocked gate with an explicit manual path, not fabricated PASS.

- `test_feishu_engineering_github_adapter.py`: fixed GitHub API origin, repo/ref/head identity, PR draft POST only after remote branch proof, independent read-only PR/CI results, no default remote writes. PR and source-comment unsigned effect negatives verified in delivery test. Real GitHub publishing requires live host access and separate permission; no source-side field proof is inferred.

## P0 exact-SHA negative regressions (source-only)
- Confirm a PR at SHA A + CI at SHA B is rejected even when each remote observer separately reports success; QA's correctly signed attestation at SHA B is rejected when the pinned delivery SHA is A. Published head and later source proof must also agree.
- Confirm read/review native turns can finish at their own terminal event with no forced PR/CI/QA, but edit attempts cannot complete before matching PR/CI and independent QA.
- Confirm a forged in-memory RuntimeGrant cannot start an actual native model turn without a durable, independently signed WorkItem execution approval receipt; replay after Run started cannot mint another grant.
- Confirm app-server terminal notification sent before turn-start ACK is queued for later exact-thread reconciliation. Notification queue overflow blocks subsequent RPC instead of dropping evidence.
- Confirm source workitem replay cannot switch to another source Run and current repository access revocation blocks provider reading before any API I/O.
These tests must pass under the exact final HEAD across Python 3.8, 3.11 and 3.12; actual network/model/Feishu/device evidence remains pending field verification.

- Verify exact Codex app-server v2 `turn/start` input contains `text_elements: []`, and read-only/workspace-write `sandboxPolicy` supplies all required properties; this is a source-schema assertion, not live protocol proof. The vstrong100-installed version's generated JSON Schema and live handshake remain separate gates.

- Negative test: a valid queued WorkItem with a real signed approval cannot dispatch a model turn using a fabricated RuntimeGrant whose expiry has been extended beyond the persisted signed receipt; no native sender invocation or Run state change is permitted.
