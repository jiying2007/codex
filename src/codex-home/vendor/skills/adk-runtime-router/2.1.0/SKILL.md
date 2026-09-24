---
name: adk-runtime-router
description: ADK 原生运行时技能路由入口，统一判定 primary、supporting、内部降级与跳过条件
version: 2.1.0
last_updated: 2026-09-14
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
- 外部资料只用于 intake/design 证据，不进入 runtime fallback。

## Prerequisites
- 已读取当前仓库 `AGENTS.md`、项目规则和用户最新指令。
- 已确认 scope、任务模式、风险等级，以及是否修改公共契约、CI 或发布链。
- 可访问 ADK inventory / workflow；不确定时先 triage，不先执行 mutation。

## Workflow
1. **Intent Triage**：识别 readonly / implementation / debugging / review / release / parallel / closeout；边界不清先 `adk-requirements-triage`。
2. **Risk Gate**：shared contract、schema、根配置、CI、依赖、运行态目录或发布链按中高风险处理。
3. **Progressive Disclosure**：执行 `skill-catalog-lazy-loading-v1`。先比较 `namespace_summary`、trigger、boundary；只为候选加载 `deferred_surface`，并记录 `loaded_tools` 与 `schema_review`。
4. **Route**：只选一个 primary skill；supporting skills 只能补充检查项。recall / reasoning / ranking / feedback 分层，执行裁决来自确定性规则、结构化校验或 owner approval。
5. **Evidence Plan**：中高风险必须生成 `Tool / Skill Evidence Plan`，包含 `primary`、`supporting`、`fallback`、`verification`，以及 required/recommended skills、artifacts 与 evidence paths。
6. **Tool Evidence**：涉及 Code Intelligence 时遵守 `code_intelligence_provider_contract`；记录 provider/tool/query/repo_ref/hit_summary/decision impact。Tool Search 记录 namespace/query/loaded_tools/schema_review。
7. **Degrade Fail-Closed**：出现 `no match`、`ambiguous`、`retrieval failed` 或工具不可用时，记录原因和 fallback evidence；不得把降级写成成功验证。
8. **Evidence Depth**：低风险可 L1 摘要；需要定位时升 L2；高风险、低置信度、安全例外或缺 raw evidence 时升 L3/raw，不用压缩替代原始证据。
9. **Execute + Verify**：加载 primary skill 推进；产生改动时最终经过 `adk-verification-before-completion`。

详细 Task Routing、Tool Routing、fallback/rationalization 规则仅在路由冲突、证据降级或需要解释边界时读取 `references/runtime-routing-details.md`，不要默认加载。

## Route Decision Template
```md
- Task Mode / Risk Level:
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
```bash
# Codex runtime：按需检索受信 inventory；不绑定专用低 token profile
rtk bash ~/codex/scripts/skill-search.sh --query "<用户请求>" --limit 5 --summary-json

# Codex runtime：验证声明式 routing
rtk bash -lc 'cd ~/codex && python3 -m unittest tests.test_agent_routing_eval'

# ADK 源仓维护
rtk bash scripts/check-profile-coherence.sh
rtk bash scripts/devkit.sh validate --strict
```

## Failure Handling
- 多个 primary 同时命中：按 triage/debug > task-breakdown > implementation > verification > release 裁决；必要时读 reference。
- 用户点名外部 Skill：保留任务意图并映射 ADK 原生能力；无安全等价能力时输出 no-skill/needs-input。
- supporting skill 缺失：低风险降为内联检查项；中高风险记录 evidence gap。
- 自然语言漏匹配：补 trigger/routing intent 与回归语料，不静默跳过。

## Quality Gate
- 必须给出 primary、supporting、fallback、verification；不得有两个 primary。
- 中高风险必须有 Tool / Skill Evidence Plan；降级、skipped skill、tool failure 必须有可追溯 evidence。
- 大型目录先 `namespace_summary`，再按需 `deferred_surface`；记录 `loaded_tools` / `schema_review`。
- 高风险或低置信度必须保留 L3/raw evidence；summary 不能替代原始证据。
- active Skill/workflow/profile/handoff 不得声明外部参考仓为 runtime fallback。
- 修改 skill、manifest、workflow、routing、阈值或分类器后必须运行匹配、负向边界和严格校验。
