---
name: multi-search-engine
description: Use when the user asks for multi-source search, cross-source verification, evidence-backed research, current information checks, high-quality open-source repository discovery, market/standard/library comparisons, or says "多源搜索", "交叉验证", "资料核验", "查多个来源", "高质量开源仓库", "开源项目推荐", or "multi-search". Search across multiple credible sources, prefer primary sources, record query/source choices, compare dates and claims, and return concise findings with citations, confidence, and remaining uncertainty. Do not use for routine coding tasks that can be answered from the local repository.
version: 0.1.1
last_updated: 2026-06-26
---

# Multi Search Engine

Use this skill for evidence-backed research that benefits from more than one source, especially when the answer may affect technical direction, tool selection, repository intake, time investment, or money.

## Scope

Good fits:

- Current facts that may have changed.
- Library, standard, policy, model, product, or tool comparisons.
- High-quality open-source repository discovery, screening, or intake recommendations.
- Conflicting claims that need cross-checking.
- Research before spending meaningful time or money.
- Technical decisions that need primary-source evidence.

Poor fits:

- Local codebase questions that can be answered by reading the repository.
- Simple stable facts that do not need live verification.
- Private browsing, authenticated pages, or CAPTCHA-gated sources.
- Tasks where the user explicitly said not to browse.

## Source Policy

- Prefer primary sources: official docs, standards, papers, release notes, vendor pages, source repositories, changelogs, issue trackers, security advisories, and license files.
- Use reputable secondary sources only to discover leads, compare interpretations, or validate ecosystem adoption.
- For technical topics, rely on official documentation, upstream repositories, specifications, or papers.
- For news or current facts, compare publication dates, event dates, and update timestamps.
- For OpenAI product/API questions, restrict fallback browsing to official OpenAI domains unless the user asks otherwise.
- Treat star counts, blog rankings, and social popularity as weak signals unless supported by maintenance, governance, release, license, and security evidence.

## Workflow

1. Restate the research question and decision context in one sentence.
2. Choose 2 to 5 source classes, such as:
   - Official docs, standards, papers, or release notes.
   - Source repository, changelog, license, security policy, or issue tracker.
   - Package registry, benchmark, adoption signal, or ecosystem index.
   - Vendor/product page.
   - Reputable independent analysis.
3. Build a small query plan before searching. For repository discovery, include search qualifiers when useful, such as `stars`, `forks`, `pushed`, `archived`, `license`, `language`, `topic`, and exact phrases from the user domain.
4. Search and open enough sources to resolve the question. Keep the source set small but defensible; broaden only when claims conflict or coverage is thin.
5. Triage sources:
   - Prefer primary and recently updated sources.
   - Reject or down-rank stale, archived, unlicensed, install-unsafe, opaque, or single-maintainer-risk projects when that risk matters.
   - Separate evidence from inference.
6. Compare claims:
   - What agrees.
   - What conflicts.
   - Which source is newest or most authoritative.
   - What remains unknown.
7. Return:
   - Short conclusion.
   - Evidence table or compact bullets with links.
   - Search/query notes when they affect reproducibility.
   - Confidence level and remaining uncertainty.

## Repository Candidate Mode

When the user asks for high-quality open-source repositories, candidates for absorption, or projects matching ADK/Codex positioning:

- Start with the target capability and exclusion rules, not only keyword search.
- Prefer repositories with clear licensing, recent maintenance, tests or CI, release discipline, issue/PR activity, security posture, and readable architecture.
- Check whether the repository is a reference source, candidate for intake, or only a pattern to learn from.
- Do not clone, execute install scripts, add subrepos, or register candidates unless the user explicitly asks for intake execution.
- Return a candidate table with:
  - `repo/url`
  - `category`
  - `why it fits`
  - `evidence`
  - `risks or reject reasons`
  - `next intake action`

## Output Contract

Default response shape:

- `结论`: one short answer or recommendation.
- `证据`: source-backed bullets or a small table with links.
- `冲突/不确定`: any disagreements, stale data, or missing verification.
- `置信度`: high, medium, or low, with one reason.

For repository discovery, add `搜索策略` when useful, including the most important query terms or filters.

## Safety

- Do not access authenticated/private pages.
- Do not enter credentials, submit forms, bypass CAPTCHA, or scrape at scale.
- Do not run external code, install packages, or execute repository scripts during research.
- Do not over-quote copyrighted sources.
- If sources conflict, say so instead of forcing a single answer.
- If browsing is unavailable, state that the result is unverified.
