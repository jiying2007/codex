# Feishu Engineering Agent V2 — Verification plan

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
