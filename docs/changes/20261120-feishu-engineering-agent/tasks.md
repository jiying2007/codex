# Feishu Engineering Agent — Tasks
Status is evidence based. This file is planning, not proof of implementation.

## TASK-000 Brainstorm and SDD freeze
[x] Read production first-generation Bot and AGENTS constraints.
[x] Compare patching 2200-line Bot / generic platform / rewrite thin core / rewrite runtime.
[x] Verify official Feishu cards, Meegle/TAPD event and Codex native integration boundaries.
[x] Freeze REQ-001..012, acceptance criteria, failure gates and cutover.
[ ] Independent implementation/tenant review.

## TASK-001 First vertical slice (verified on original SHA)
[ ] Implement safe natural-language router + explicit project selection; unknown intent clarifies.
[ ] Implement typed WorkItemKey and no-auto-execute decision.
[ ] Implement scoped user preference + event dedupe in offline temp SQLite with failure rollback.
[ ] Create no-network no-model dry-run CLI; verify from non-repository cwd.
[ ] Run Python 3.8, 3.11, 3.12 unit/full repository regression and record exact HEAD/run IDs.
[ ] Review, merge only if CI and scope gates pass.

## TASK-002 Feishu card/event adapter
[ ] Test in a dedicated authorized Feishu app, no second live production consumer.
[ ] Card 2.0 render/update, 3s ACK, callback identity and replay defense.
[ ] Expired card, late callback, network failure and duplicate click cases.

## TASK-003 Session and run coordinator
[ ] Validate deployed App Server capability without a paid turn.
[ ] Exact actor/repo/host/CODEX_HOME/thread binding, no --last.
[ ] Separate authorization for edits; fail closed on unknown model effect.

## TASK-004 WorkItem adapters
[ ] One real Feishu Project requirement and one TAPD Bug read-only, with tenant/workspace permissions.
[ ] No webhook until verified authenticated ingestion; no fixed polling cron.

## TASK-005 SDLC
[ ] A real feature and a real Bug through brainstorming/SDD, implementation, PR/CI and independent QA.
[ ] Cross-repo contract test + device evidence where applicable; no fake HIL PASS.

## TASK-006 Production cutover
[ ] Snapshot actual current service/systemd/DB/spool and unknown work with checksums.
[ ] Verify restore/rollback and only one active event consumer.
[ ] Separate permission/model billing/host smoke from CI results.

**No Codex/ChatGPT Work quota, new scheduled tasks or external writes authorized by this document.**

## Evidence checkpoint: offline implementation extension
- TASK-001 source and 9/9 CI checks previously passed at `5f2ca425fc92ccb7c70b7d0e94fe30237915f4f0`; merging remains a separate decision.
- TASK-002: Card rendering and signed callback storage implemented for offline tests. Real card send/update/3-second callback on Feishu desktop and mobile **open**.
- TASK-003: exact session records and RPC planning implemented for offline tests. vstrong100 App Server handshake/resume/approval/interrupt **open**; no model quota used.
- TASK-004: API read adapters and fail-closed responses implemented with injected transports. Tenant authorization and real one requirement/one bug read **open**.
- TASK-005: run state/evidence contracts implemented; real feature and Bug PR/CI and independent QA **open**.
- TASK-006: **not started**; no production service/config, consumer or private DB touched.

## No-enterprise-API path (implementation increment)
- [x] Implement strict `/wi` WorkItem manual registration/list/status with digest-only summary retention and exact provider/tenant/workspace/kind/item ID.
- [x] Implement private transactional source receipt + independent AgentRun in `manual_items.py`; replay is no-op, conflict fails closed, and repo permissions are rechecked.
- [x] Extend the **same** existing Bot handler under disabled-by-default `manual_workitems_enabled`; reserved `/wi` never becomes a Codex prompt when disabled.
- [x] Add no-API local stdin CLI; no provider credentials, card callback or model turn needed.
- [ ] Verify new code and tests on exact GitHub Actions SHA.
- [ ] Enable and validate a single existing Feishu Bot's real message receive/reply with trusted tenant ID, using a redacted low-risk workitem (if already permitted).
- [ ] If bot message scopes are unavailable, verify local CLI on vstrong100 without connecting Feishu.
- [ ] Real PR/CI, independent source-system QA, production cutover and App Server qualification remain separately unverified.
