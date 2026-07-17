---
name: wechat-account-research
description: Batch-discover, verify, deduplicate, and metadata-archive public WeChat account articles by named account, date window, and technical topics. Use when Codex is asked for 微信公众号批量搜索、公众号近半年文章、搜狗微信检索、指定公众号专题归档、WeChat account research, or a reproducible article evidence pack. This workflow may reuse a Hermes discovery index or use bounded read-only agent-browser access; it must stop at CAPTCHA/login gates, must not rotate proxies or identities, and must never persist article bodies.
version: 0.1.0
last_updated: 2026-07-16
---

# WeChat Account Research

Build a reviewable evidence pack for public WeChat account research. Keep discovery, page verification, editorial selection, and long-term archive promotion as separate stages.

## Route correctly

- Use `browser-reader` for one user-authorized page or manual verification.
- Use `multi-search-engine` for ordinary cross-source research without account-level batch collection.
- Use this skill for bounded account × topic × date-window collection.
- After collection, use `external-practice-absorption` to decide whether findings should change local assets.
- Use `adk-knowledge-archive` only after the evidence pack has been reviewed and sanitized.

## Required inputs

Record before execution:

- canonical account names and known display aliases;
- inclusive `date_from` and `date_to`;
- topic terms or approval to use the default technical query matrix;
- output directory outside runtime, cache, credential, session, and source-asset paths;
- maximum queries, results per query, and candidates;
- stable seed URLs, if supplied by the user.

Treat a request without a bounded account/window/query budget as exploration. Do not start collection until it is bounded.

## Workflow

### 1. Plan

Create a deterministic query plan without network access:

```bash
rtk bash "$HOME/codex/scripts/wechat-archive.sh" plan \
  --account '腾讯技术工程' \
  --account '阿里云开发者|阿里开发者' \
  --date-from 2026-01-16 \
  --date-to 2026-07-16 \
  --output-dir /tmp/wechat-research
```

Inspect `plan.json`. Reject unbounded plans or a query matrix over the tool's hard cap.

### 2. Collect and verify

Prefer an already-authorized Hermes discovery index when available:

```bash
rtk bash "$HOME/codex/scripts/wechat-archive.sh" collect \
  --plan-file /tmp/wechat-research/plan.json \
  --discovery-index /path/to/hermes/articles.json \
  --output-dir /tmp/wechat-research
```

Without an index, omit `--discovery-index`; the tool uses bounded, read-only `agent-browser` access to public Sogou and WeChat pages. It records account/date/title/content-hash evidence but discards the body before writing JSONL.

Stop the run when a CAPTCHA, login, anti-spider, paywall, or safety-verification gate appears. Report partial evidence; do not retry through proxy rotation, UA rotation, cookies, saved sessions, or automated user verification.

### 3. Review states

Treat only `direct-read` as account-and-date verified. Keep `account-mismatch`, `out-of-window`, `date-unknown`, `search-unresolved`, `redirect-unresolved`, `fetch-inaccessible`, and `access-gated` as negative evidence.

Do not infer account ownership from a search snippet or mirror. An official company mirror may be added manually as `official-mirror-verified`, with its provenance kept distinct from WeChat direct-read evidence.

### 4. Generate and check the evidence pack

```bash
rtk bash "$HOME/codex/scripts/wechat-archive.sh" report \
  --plan-file /tmp/wechat-research/plan.json \
  --output-dir /tmp/wechat-research

rtk bash "$HOME/codex/scripts/wechat-archive.sh" check \
  --plan-file /tmp/wechat-research/plan.json \
  --output-dir /tmp/wechat-research
```

Review `README.md`, `catalog.jsonl`, `coverage.json`, `evidence.jsonl`, and `run-summary.json`. Every catalog record remains `review-required`; the tool does not assign adoption decisions.

### 5. Archive or absorb after review

- Archive the sanitized research note through `adk-knowledge-archive` or `archive-note.sh`.
- For local optimization, invoke `external-practice-absorption` and compare every candidate against existing skills, workflows, manifests, tests, and runbooks.
- Use explicit `ADOPT / MERGE / ENHANCE / REJECT / REFERENCE_ONLY` decisions.
- Never promote article prose, popularity claims, installation snippets, or unverified product claims into durable rules.

## Hard boundaries

- Public, read-only sources only; no login, form submission, message sending, publishing, or external write API.
- No CAPTCHA bypass, proxy pool, identity rotation, fingerprint spoofing, cookie import, or credential reuse.
- No full-body, raw HTML, screenshot corpus, browser state, signed redirect URL, or session persistence.
- No automatic deletion, quality-based purge, memory write, AGENTS promotion, or ADK modification.
- Use stable short URLs, official mirrors, or title-query locators for durable navigation; label locator evidence separately from direct-read evidence.
- Keep rate limits and candidate caps visible in `plan.json`; stop rather than escalating retries.

## Reference

Read [references/evidence-contract.md](references/evidence-contract.md) when changing the query matrix, status model, evidence schema, or archive/absorption boundary.

## Completion gate

Do not claim completion unless:

- plan, evidence, catalog, coverage, run summary, and check output agree;
- direct-read records have canonical account, in-window date, 64-character SHA-256, and `body_persisted=false`;
- negative states and unresolved candidates are retained;
- no temporary signed URL, body field, credential, cookie, or browser state appears in persisted outputs;
- the final report states coverage limits and does not claim exhaustive account history.
