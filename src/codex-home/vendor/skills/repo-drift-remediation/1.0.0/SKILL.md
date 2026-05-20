---
name: repo-drift-remediation
description: "Use when the user asks for full repository inspection or cleanup for drift, deviation, redundancy, stale compatibility, leftovers, unclear boundaries, inconsistent docs/code, pre-submit readiness, or broad quality remediation."
version: 1.0.0
last_updated: 2026-05-20
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Repo Drift Remediation

Use this skill for broad repository health work where the user asks for more than a local bug fix.

## Scope

Typical trigger phrases include:

- 全面检查 / 全面优化
- 飘移 / 偏离 / 冗余 / 残留 / 边界不清
- 文档代码不一致
- 提交前检查
- 设计是否偏离目标

## Workflow

1. Establish the declared target from `AGENTS.md`, README, docs, manifests, and recent user instructions.
2. Build an issue map before editing:
   - goal drift;
   - architecture or ownership boundary drift;
   - stale compatibility code or docs;
   - duplicated docs, scripts, or generated artifacts;
   - source/live or manifest drift;
   - missing tests, docs, or verification gates;
   - unsafe commands or secret handling gaps.
3. Rank findings by risk and blast radius.
4. Remediate only issues that are clearly in scope. Avoid broad formatting churn.
5. For shared contracts, root configs, lockfiles, release scripts, or CI gates, make changes serially and validate harder.
6. Run targeted checks first, then full checks required by the repo.
7. For commit/push requests, hand off to `adk-commit-pr-quality-gate`.

## Rules

- Do not assume every historical file is wrong; identify the current source of truth first.
- Do not delete or rewrite user changes without explicit approval.
- Do not collapse project-specific knowledge into global policy.
- Prefer scriptable checks over narrative-only judgments.

## Output

Give:

- target and source-of-truth summary;
- fixed issues;
- issues intentionally left unchanged;
- validation commands and results;
- residual risk.
