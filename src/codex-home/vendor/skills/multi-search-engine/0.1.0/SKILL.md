---
name: multi-search-engine
description: Use when the user asks for multi-source search, cross-source verification, evidence-backed research, current information checks, market/standard/library comparisons, or says "多源搜索", "交叉验证", "资料核验", "查多个来源", or "multi-search". Search across multiple credible sources, prefer primary sources, compare dates and claims, and return concise findings with citations. Do not use for routine coding tasks that can be answered from the local repository.
version: 0.1.0
last_updated: 2026-05-10
---

# Multi Search Engine

Use this skill for evidence-backed research that benefits from more than one source.

## Scope

Good fits:

- Current facts that may have changed
- Library, standard, policy, model, product, or tool comparisons
- Conflicting claims that need cross-checking
- Research before spending time or money
- Technical decisions that need primary-source evidence

Poor fits:

- Local codebase questions
- Simple facts answerable from known stable context
- Private browsing or authenticated pages
- Tasks where the user explicitly said not to browse

## Source Policy

- Prefer primary sources: official docs, standards, papers, release notes, vendor pages.
- Use reputable secondary sources only to discover leads or compare interpretations.
- For technical topics, rely on official documentation or source repositories.
- For news/current facts, compare publication dates and event dates.
- For OpenAI product/API questions, restrict fallback browsing to official OpenAI domains unless the user asks otherwise.

## Workflow

1. Restate the research question in one sentence.
2. Choose 2 to 5 source classes:
   - Official docs or release notes
   - Source repository or changelog
   - Standards/specification/paper
   - Vendor/product page
   - Reputable independent analysis
3. Search and open enough sources to resolve the question.
4. Compare claims:
   - What agrees
   - What conflicts
   - Which source is newest or most authoritative
5. Return:
   - Short conclusion
   - Evidence table or bullets
   - Source links
   - Confidence and remaining uncertainty

## Safety

- Do not access authenticated/private pages.
- Do not enter credentials or submit forms.
- Do not over-quote copyrighted sources.
- If sources conflict, say so instead of forcing a single answer.
- If browsing is unavailable, state that the result is unverified.
