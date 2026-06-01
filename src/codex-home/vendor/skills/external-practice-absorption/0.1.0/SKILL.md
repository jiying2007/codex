---
name: external-practice-absorption
description: Use when the user asks to absorb, mine, or apply lessons from external articles, WeChat public account posts, GitHub projects, reference folders, or copied research notes into llm_agent, agent-dev-kit, ~/codex, AGENTS.md, skills, workflows, manifests, or archive governance without creating drift.
version: 0.1.0
last_updated: 2026-05-31
origin: local-chronicle-derived
lifecycle: iterative-local
---

# External Practice Absorption

Use this skill to turn external material into controlled local improvements.

## Good Fits

- "参考这些公众号文章优化 llm_agent / agent-dev-kit / ~/codex"
- "吸收 wechat-articles 目录"
- "这个 GitHub 项目有什么可借鉴并落地"
- "结合网页内容优化 skill / AGENTS / workflow"

## Supporting Skills

- Use `browser-reader` for a single page that needs browser/manual verification.
- Use `multi-search-engine` for current claims, competing projects, standards, or cross-source verification.
- Use `adk-knowledge-archive` when durable research notes should be archived.
- Use `adk-repo-drift-remediation` when changes risk adding duplicate concepts, stale docs, or boundary drift.

## Workflow

1. Inventory sources:
   - source path or URL;
   - title, publisher, date if available;
   - read status: direct read, browser/manual verification, user-provided excerpt, or inaccessible.
2. Extract reusable claims:
   - problem solved;
   - mechanism;
   - local applicability;
   - cost, dependency, maintenance risk;
   - evidence strength.
3. Map to target assets:
   - existing skill update;
   - new skill;
   - AGENTS/routing rule;
   - manifest/eval/automation record;
   - archive-only.
4. Decide with an explicit table: `adopt`, `adapt`, `reject`, or `archive-only`.
5. Implement only the smallest coherent improvement set.
6. Validate source-to-live when Codex assets are changed.

## Guardrails

- Do not copy external prose wholesale into skills or docs.
- Do not promote one article's opinion into global rules without repeated evidence or user confirmation.
- Keep external source metadata in archives; keep skills focused on durable procedure.
- Sanitize private URLs, credentials, cookies, and internal endpoints.
- Avoid creating parallel rules that duplicate an existing adk skill or AGENTS section.

## Output

Report:

- source summary and read status;
- decisions and rejected ideas;
- changed files;
- validation evidence;
- remaining archive-only material.
