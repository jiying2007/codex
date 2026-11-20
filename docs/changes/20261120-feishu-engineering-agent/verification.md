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
- Official `card.action.trigger` callback schema has `event.host` and `event.context`, not top-level fields.
- Interactive send records `sending` before I/O; lost receipt becomes UNKNOWN without resend.
- No-model `--probe-runtime` success/failure paths and invalid combined arguments.
- All new checks require a fresh exact-SHA CI receipt. They do not qualify real callbacks or tenant permissions.

## No-enterprise-API regression (new coverage)
- `test_feishu_engineering_manual_items.py`: strict manual parsing, real provider identity isolation, read-only status/list, user/tenant/chat/repo isolation, SQLite 0600/no raw prompt, atomic duplicate/conflict receipt, local CLI stdin without an SDK or API.
- `test_feishu_engineering_manual_bot.py`: optional same-consumer message interception, disabled mode never reaches Codex gate, bad tenant/actor/chat or repo is denied, old non-`/wi` intake unchanged, legacy queue has no new jobs.
- These offline tests **cannot** prove enterprise tenant permissions, SDK message-event header shape on vstrong100, a real Lark send, or any QA/PR success. Record their exact successful workflow run IDs only after current HEAD CI.

Manual message rate-limit negative test: six unique `/wi add` events under default 5-per-window must create only five proposed runs, never a legacy queued/model job.

Additional regression: the Feishu message listener enqueues at most one bounded manual-intake worker and returns before SQLite I/O; the test invokes the captured worker separately to prove no synchronous database transaction or Codex job inside the event callback.
