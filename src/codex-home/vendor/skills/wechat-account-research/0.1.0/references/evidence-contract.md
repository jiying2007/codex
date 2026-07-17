# Evidence Contract

## Contents

1. Query-plan contract
2. Collection and access states
3. Persisted artifact contract
4. Safety and copyright boundary
5. Review and absorption boundary

## 1. Query-plan contract

The default technical matrix is:

`LLM`, `大模型`, `Agent`, `智能体`, `Skill`, `Skills`, `Workflow`, `工作流`, `Profile`, `MCP`, `Hook`, `Harness`, `上下文工程`, `Agent 记忆`, `Token 优化`, `多 Agent`, `AI Coding`, `Agent 评测`, `Agent 安全`, `工具调用`, `RAG`.

The plan must store:

- canonical account plus aliases;
- inclusive date window;
- ordered, de-duplicated topics;
- account × topic queries;
- stable seed URLs;
- query/result/candidate caps;
- `body_policy=persist-never`;
- `access_policy=public-read-only-stop-on-gate`.

Hard defaults:

- at most 50 queries per plan;
- at most 10 search results per query;
- at most 100 verification candidates;
- no more than one network attempt after an access gate;
- at least one second between browser actions unless a stricter limit is supplied.

## 2. Collection and access states

| State | Meaning | Eligible for catalog |
|---|---|---|
| `direct-read` | WeChat page supplied body, canonical account, and in-window date | yes |
| `official-mirror-verified` | Human-reviewed official mirror supplied provenance/date | yes, distinct evidence class |
| `account-mismatch` | WeChat body belongs to another account | no |
| `out-of-window` | Canonical account matches but date is outside the plan | no |
| `date-unknown` | Body was read but publication date is unavailable | no |
| `search-unresolved` | Fresh title search did not find a close candidate | no |
| `redirect-unresolved` | Public redirect did not resolve to WeChat | no |
| `fetch-inaccessible` | Resolved page did not expose usable article content | no |
| `access-gated` | CAPTCHA, login, anti-spider, paywall, or verification page appeared | no; stop or request manual help |

Search snippets, third-party mirrors, and title-query URLs are locators. They do not prove account ownership.

## 3. Persisted artifact contract

### `plan.json`

Reproducible input and bounded execution policy.

### `evidence.jsonl`

One record per attempted candidate. Allowed evidence includes:

- candidate and verified title;
- requested and verified account;
- publication date;
- query and topic hits;
- access state;
- character/paragraph/code-block counts;
- content SHA-256;
- stable locator when available;
- timestamp, similarity, and negative reason;
- `body_persisted=false` and `temporary_url_persisted=false`.

Forbidden keys include `content`, `body`, `html`, `raw_html`, `cookie`, `cookies`, `authorization`, `session`, and signed redirect URLs.

### `catalog.jsonl`

Metadata-only subset eligible for editorial review. Every generated record has `review_status=review-required`; tier, quality judgment, and absorption decision require human or Agent review against local assets.

### `coverage.json`

Counts by account, query, and access state plus explicit limitations.

### `run-summary.json`

Start/end state, processed count, retry budget, access-gate state, partial-run status, and output paths.

### `README.md`

Human-readable scope, method, status counts, candidate table, negative evidence, coverage limits, and copyright boundary.

## 4. Safety and copyright boundary

- Keep article bodies in memory only long enough to verify metadata, compute the digest, and derive topic signals.
- Do not reconstruct, quote, summarize at length, or mirror the body automatically.
- Do not retain transient Sogou or WeChat URLs containing timestamp/signature parameters.
- Do not import cookies or browser profiles. Close the browser session after the run.
- An access gate is a terminal state for automated collection, not a retry signal.
- Existing Hermes indexes are read-only discovery inputs; the Codex pack does not mutate Hermes data.

## 5. Review and absorption boundary

For each reviewed article or cross-article pattern, record:

- `problem` and reusable `mechanism`;
- evidence strength and whether the body was directly read;
- existing local equivalent;
- target asset and smallest coherent change;
- dependency, permission, maintenance, and drift risks;
- decision: `ADOPT`, `MERGE`, `ENHANCE`, `REJECT`, or `REFERENCE_ONLY`;
- validation and rollback evidence.

Default to `MERGE` when an existing skill, workflow, manifest, gate, or runbook already expresses the mechanism. Default to `REFERENCE_ONLY` for model news, product announcements, trend assertions, generic tutorials, and ideas already enforced more strongly by local deterministic gates.
