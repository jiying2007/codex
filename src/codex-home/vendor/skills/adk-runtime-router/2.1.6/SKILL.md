---
name: adk-runtime-router
description: "用于任务开始前在可信 Skills 清单中选定唯一 primary、supporting 和回退路径；不用于已有明确任务包时重复路由或隐式授予执行权限。"
version: 2.1.6
last_updated: 2026-11-20
triggers:
  - "技能路由"
  - "选择技能"
  - "任务分流"
  - "adk 路由"
  - "adk-first"
  - "判断使用哪个技能"
  - "运行时路由"
  - "开始任务前"
non_triggers:
  - 子代理已收到明确任务包
  - 已有完整计划且只需按计划执行
  - 纯背景知识问答且不需要工具或文件操作
inputs:
  - 用户请求、仓库规则、任务类型、风险等级、可用 skill 清单
outputs:
  - primary skill、supporting skills、内部降级条件、跳过理由与下一步动作
constraints:
  - 只能从受信 ADK inventory 或项目已声明 workflow 中选择运行能力
  - 外部参考仓不得作为 runtime fallback、安装源或隐式依赖
  - 任何内部降级必须说明触发原因和退出条件
  - 不得用“任务很简单”作为跳过路由的理由
  - 大型 skill/tool 目录必须先读 namespace summary，再按意图延迟加载完整正文或 schema
---

# adk-runtime-router

## Goal
- 任务开始前完成 adk-first 路由，只保留一个 primary skill。
- 默认使用 progressive disclosure：先读轻量入口和 namespace summary，仅对命中候选加载正文、reference 或 schema。


## Prerequisites
- 读取当前 `AGENTS.md`、仓库规则与用户指令。
- 确认 scope、任务模式、风险与是否影响接口/CI/发布。
- 核目标 Profile 已安装 inventory；Matcher 命中不等于可用，缺失则 `no-skill/abstain`。

## Workflow
1. **Intent Triage**：目标/权限/风险未变则复用已验证 route；变化或不明才 `adk-requirements-triage`。
2. **Risk Gate**：共享接口/CI/发布按中高风险；E0–E3 控投入，不豁免 R2。
3. **Progressive Disclosure**：按 `skill-catalog-lazy-loading-v1` 检索 `namespace_summary` / trigger，仅加载命中 `deferred_surface`，记录 `loaded_tools` / `schema_review`。
4. **Skill Fit Gate**：命中不代表适配；版本/平台/验收冲突须核目标仓当前源码，禁用过期 Skill 模板；不适配则 `no-skill/abstain`；细则见 `references/runtime-routing-details.md`。
5. **Route**：唯一 primary，supporting 不提升权限；按规则/schema/owner approval 决定执行。
6. **Evidence Plan**：中高风险交 `Tool / Skill Evidence Plan`：`primary` / `supporting` / `fallback` / `verification` 及必要证据。
7. **Tool Evidence**：保留 `code_intelligence_provider_contract` 与 Tool Search 选项/来源/权限证据。
8. **Degrade Fail-Closed**：出现 `no match`、`ambiguous`、`retrieval failed` 或工具不可用时，记录原因和 fallback evidence；不得把降级写成成功验证。
9. **Evidence Depth**：按风险 L1/L2/L3；高风险保留 raw evidence。
10. **Execute + Verify**：加载 primary skill 推进；产生改动时最终经过 `adk-verification-before-completion`。

冲突/降级时再读 `references/runtime-routing-details.md`。

## Route Decision Template
```md
- Task Mode / Risk Level / Execution Effort (E0–E3) / Escalation Basis:
- Primary Skill:
- Supporting Skills:
- Fallback: enabled / reason / exit_condition
- Skip Reasons:
- Tool / Skill Evidence Plan:
  - primary / supporting / fallback / verification:
  - namespace_summary / deferred_surface:
  - loaded_tools / schema_review:
  - required/recommended skills:
  - Required Artifacts / Skipped Skills:
  - Fallback Evidence / Evidence Paths:
- Verification Path:
- Next Action:
```

## Commands
- 只使用当前目标已验证的 inventory、manifest 与 health adapter，不假定固定 HOME 路径或 shell wrapper。
- Codex 特有命令见 `docs/runbooks/codex-team-runtime-distribution.md`，不进入通用 Skill。
- ADK 源仓内可执行：

```bash
bash tests/test_profile_coherence.sh
bash scripts/devkit.sh validate --strict
```

## Failure Handling
- 多个 primary 同时命中：按 triage/debug > task-breakdown > implementation > verification > release 裁决；必要时读 reference。
- 用户点名外部 Skill：保留任务意图并映射 ADK 原生能力；无安全等价能力时输出 no-skill/needs-input。
- supporting skill 缺失：低风险降为内联检查项；中高风险记录 evidence gap。
- 自然语言漏匹配：补 trigger/routing intent 与回归语料，不静默跳过。

## Quality Gate
- 低风险只记 `primary / installed-profile / verification / next action`；中高风险记录 primary、supporting、fallback、verification。不可多 primary 或冒充已安装。
- 中高风险必须有 Tool / Skill Evidence Plan；降级、skipped skill、tool failure 要留 evidence。
- Effort 不改变授权、R2、Review/Release；不适配则 `no-skill/abstain`。
- 高风险或低置信度必须保留 L3/raw evidence；summary 不能替代原始证据。
- active Skill/workflow/profile/handoff 不得声明外部参考仓为 runtime fallback。
- 修改 skill、manifest、workflow、routing、阈值或分类器后必须运行匹配、负向边界和严格校验。
