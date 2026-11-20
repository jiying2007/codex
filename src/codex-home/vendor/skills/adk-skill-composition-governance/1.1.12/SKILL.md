---
name: adk-skill-composition-governance
description: "用于多个 Skill 的触发冲突、组合边界、fallback 和退役策略审查；不用于新增并行路由权威或直接提升工具写权限。"
version: 1.1.12
last_updated: 2026-11-20
triggers:
  - "技能组合"
  - "触发冲突"
  - "技能治理"
  - "创建 skill"
  - "skill 生命周期"
  - "内部降级治理"
  - "弃用治理"
non_triggers:
  - 单个 skill 文案微调且不影响触发规则
  - 仅安装已有 profile 且不改变组合关系
inputs:
  - skill 清单、触发词、non_trigger、profile、候选任务场景
outputs:
  - 主技能、辅助技能、fallback、互斥关系、模式分类和弃用决策
constraints:
  - 一个场景只能有一个主技能
  - 辅助技能不得抢占主技能触发
  - Pipeline/Inversion 类 skill 必须有可执行门禁或结构化状态检查
  - 组合治理必须先比较 skill namespace summary 和 initial_surface，再按命中候选加载 deferred_surface
---

# adk-skill-composition-governance

## Goal
- 用小技能组合提高覆盖面，同时避免运行时目录中触发噪音和职责重叠。
- 建立技能组合规则、冲突检测机制和治理矩阵。
- 建立 adk 原生 skill 创作、profile 归属、pilot 证据和弃用下线流程。

## Prerequisites
- 已列出涉及的 skill、optional skill 和目标 profile。
- 已有至少一条代表性任务输入。

## Skill 精简决策
- **KEEP**：独立触发/产物/门禁可复核；**DEFER**：低频但有用则归已有专业 Profile。
- **MERGE**：触发/产物/失败边界等价且迁移回归通过；**RETIRE**：无消费者且有受测替代。
- 未观测调用≠无用，专业≠多余；权限及原始证据不降级，Token/效果须真实 A/B。

## Admission Modes
- `collision-only`：一次触发冲突、无 Profile/依赖/权限变化时，仅冻结候选和 near-miss，运行现有 matcher/negative/collision case，提出最小修复；不强制 13 阶段和全量矩阵。
- `composition-change`：调整 primary/supporting/fallback、Profile、权限、Workflow 或生命周期时，才完整执行下述组合治理、契约/安全门禁及必要的真实行为评测。

## Workflow
1. 确定主技能：每个场景只能有一个 primary skill。
2. 标注辅助技能：supporting skill 只在 primary 明确需要时激活。
3. 定义 fallback：主技能不适用时给出后备 skill、触发条件和退出条件。
4. 定义互斥关系：职责冲突或触发重叠时写明优先级。
5. 模式分类：标注 Tool Wrapper、Generator、Reviewer、Inversion 或 Pipeline。
6. 输出契约审查：Generator/Reviewer 必须有 schema、失败条件和复验方式。
7. 硬门禁审查：Pipeline/Inversion 必须有状态文件、callback、脚本 gate 或外部编排，不得只靠自然语言约束。
8. 渐进披露审查：按 `skill-catalog-lazy-loading-v1` 记录 `namespace_summary`、`initial_surface`、`deferred_surface`、`loaded_tools`、`schema_review` 和相邻 skill 拒绝理由；不得全量加载所有 skill 正文后再裁决。
9. 冲突检测：检查 triggers、non_triggers、profile 和实际 match 样例。
10. 弃用治理：旧 skill 必须给 `deprecated_by` 或 `replaced_by`。
11. 回归样例：为 primary/supporting/fallback 各补代表输入。
12. 更新治理矩阵：记录场景、主技能、辅助技能、fallback、互斥和优先级。
13. **行为 TDD**：同模型/工具/上下文比较现行 baseline 与 candidate；首次价值或负收益调查才另设 no-skill。区分开发、选型与冻结留出案例，按影响执行正反/near-miss、独立盲评和成本对照；禁止用 holdout 调参。无真实 trace 保持 `not-measured`，路由 CI 不代表行为改善。七字段方法记录与详细控制见 `references/skill-behavior-evaluation.md`，复用既有证据，不增加台账。

14. **失败反馈→回归候选**：仅针对已核实的重复失败，在现有测试/fixtures 补最小正例、反例和适用确定性检查；改动前保存失败证据，修复后核旧成功路径。真实模型未执行仍为 `not-measured`，不得靠 E0/E1 判定模型成功。按需见 `references/adk-skill-lifecycle.md`。

## 组合规则
- 一个场景一个 primary；supporting 不抢占触发。
- fallback 必须在目标 profile 或可选安装范围内可用。
- deprecated skill 必须有替代方案，禁止无替代删除。
- 运行能力退役必须有 ready pilot、路由回归和 required/forbidden footprint 证据。

adk 原生 skill 创作和弃用生命周期模板：`references/adk-skill-lifecycle.md`。

## Skill Pattern Rules
- Tool Wrapper：必须声明命令/API/MCP 边界、输入校验、失败回滚。
- Generator：必须声明产物路径、覆盖策略、格式化/测试命令。
- Reviewer：必须声明严重级别、证据路径和误报处理方式。
- Inversion：必须声明 stop/ask 条件、owner 和状态恢复入口。
- Pipeline：必须声明阶段状态、检查点、resume/abort 路径和最终整合验证。

## Commands
以下管理命令仅在已核 ADK 源码根且 helper 可读时运行。纯 Skill 消费使用目标项目已有清单/验证入口；缺失则输出候选与限制，源码检查记 `not-run`，不安装依赖、不伪报通过。目录盘点合并 core 与 optional；可见不等于已安装。
```bash
bash scripts/devkit.sh catalog find --keyword adk --type skill
bash scripts/devkit.sh catalog find --keyword adk --type optional-skill
bash scripts/devkit.sh match --skill <skill> --text "<task text>"
rg -n --glob SKILL.md "triggers:" skills optional-skills
bash scripts/devkit.sh validate --strict
bash tests/test_profile_coherence.sh
bash tests/test_skill_trigger_matrix.sh
bash scripts/pilot-readiness.sh --summary-json
```

## Evidence Template
```md
- Scenario:
- Primary Skill:
- Supporting Skills:
- Fallback Skill:
- Mutually Exclusive Skills:
- Pattern Classification:
- Output Contract:
- Hard Gate:
- Deprecated/Replaced Decision:
- Trigger Regression:
- Composition Rules:
- Governance Matrix:
- Conflict Detection Results:
- Progressive Disclosure:
  - contract: skill-catalog-lazy-loading-v1
  - namespace_summary:
  - initial_surface:
  - deferred_surface:
  - loaded_tools:
  - schema_review:
  - adjacent_rejection:
```

## Failure Handling
- 若一个场景出现多个主技能，结论固定为 `needs-fix`。
- 若 fallback 不可安装或不在 profile 中，退回 profile 设计。
- 若冲突检测发现触发词重叠但无优先级定义，必须补充治理矩阵。
- 若弃用技能无替代方案，必须冻结而非删除。

## Quality Gate
- 组合规则必须能被脚本检查；`collision-only` 至少覆盖目标候选及近邻负例，不能凭命中一条字符串宣称宿主实际行为改善。
- 触发样例必须覆盖正例、反例和 fallback。
- 治理矩阵必须覆盖所有已知场景。
- 冲突检测必须在每次 profile 变更后重新执行。
- 依赖图必须可视化展示技能间关系，禁止隐式依赖。
- Generator/Reviewer/Pipeline/Inversion 的输出契约和硬门禁必须可验证。
- 组合裁决必须保留 progressive disclosure 证据，证明未因全量上下文噪音导致 primary/supporting/fallback 误判。
- Skill 发布前区分 source-contract PASS 与真实 host behavior `not-measured`；缺真实 trace 不得宣称达到上游产品体验。
