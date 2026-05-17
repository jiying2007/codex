---
name: adk-verification-before-completion
description: 完成前验证门禁，确保交付声明与证据一致
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "准备完成"
  - "准备提交"
  - "完成前检查"
non_triggers:
  - 仅做方案讨论且尚未产生实现改动
  - 纯背景知识问答
inputs:
  - 改动清单、测试结果、评审结论、风险与回退信息
outputs:
  - 完成前核对清单、门禁结论、未闭环项与处理建议
constraints:
  - 没有验证证据不得给出完成或通过结论
  - 评审 blocker 未关闭时不得给通过结论
  - breaking change 必须显式声明与迁移/回退方案
---

# adk-verification-before-completion

## Goal
- 在交付前统一核对验证证据、评审状态和风险闭环，避免“未验先结论”。

## Prerequisites
- 已整理改动文件清单与影响范围。
- 已收集 lint/test/build/smoke 与评审状态证据。

## Workflow
1. 收敛改动范围：确认本次改动边界、影响面与非目标。
2. 证据核验：核对 lint/test/build/smoke 等结果与执行环境。
3. 评审闭环：按 blocker/major/minor 分级，检查必须项是否关闭。
4. 运行目标检查：若目标是 `~/.codex`，必须补 `~/codex` build/apply 证据与运行目录健康验证证据。
5. 配置加载核验：若涉及 codex 配置变更，补 `声明配置 vs 运行态加载` 对比证据。
6. prompt 回归核验：若改动提示词或策略文本，补 before/after 行为对比与失败样例。
7. 证据索引化：关键命令必须记录命令、退出码、结果摘要、证据路径、层级（Agent/Skill/Workflow）与关联工件。
8. 兼容性检查：显式判断是否存在 breaking change，并给出迁移与回退方案。
9. 反向核验：逐条检查“结论是否被证据支持”，避免先给结论后补证据。
10. 结论输出：给出 pass/needs-fix，并列出下一步动作与责任人。

## Commands
```bash
git diff --name-only <base>...HEAD
<project-lint-cmd> && <project-test-cmd> && <project-build-cmd>
bash scripts/check-global-codex-health.sh ~/.codex minimal
codex mcp list
```

## Evidence Template
```md
- Scope Summary:
- Verification Command Results:
- Runtime Config Audit:
- Prompt Regression Evidence:
- Evidence Index:
- Review Status (B/M/m):
- Breaking Change Decision:
- Risk + Rollback:
- Final Gate Result:
```

```md
Evidence Index（命令级）:
| Command | Exit Code | Result Summary | Evidence Path | Layer | Related Artifact |
|---|---|---|---|---|---|
| <cmd> | 0 | <summary> | <path> | Workflow | verify-report |
```

## Failure Handling
- 关键命令无法执行时，必须说明原因并降级完成度表述。
- 若 blocker 未闭环，结论固定为 `needs-fix`，不得放行。

## 与 adk-commit-pr-quality-gate 的区别
- adk-verification-before-completion: 完成前自检（验证命令、证据、边界）
- adk-commit-pr-quality-gate: 提交/PR 质量门禁（格式、规范、评审）

## Quality Gate
- 输出必须包含验证命令、关键结果、风险项和处理状态。
- 若存在未闭环 blocker，结论必须为 `needs-fix`。
- 完成声明需与实际证据逐项可追溯。
- 若声明目标可在 `~/.codex` 放行，必须附 `~/codex` build/apply 证据和运行目录健康验证结果。
- 若涉及 codex 配置变更，必须附声明配置与运行态加载一致性结论。
- 若涉及 prompt/policy 文本变更，必须附 before/after 行为对比与失败样例。
- 关键验证命令必须存在 Evidence Index 记录，且字段完整（命令/退出码/结果摘要/证据路径/层级）。
- Evidence Index 至少包含一条负结果或被证伪路径记录。
- 禁止使用"应该可以/理论上通过"等无证据措辞。

---

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "我验证过了" | 口头验证不是证据，无法复现无法审计 | 按 SKILL.md 写入 Evidence Index，附命令/退出码/结果摘要 |
| "跑了一遍应该没问题" | "应该"是被禁止的措辞，一次性通过不等于可靠 | 关键验证命令必须可复跑，且记录负结果 |
| "这次改动很安全不需要全量验证" | 安全感不等于安全性，局部验证遗漏全局回归 | 按验收标准逐项验证，Evidence Index 至少含一条负结果 |
