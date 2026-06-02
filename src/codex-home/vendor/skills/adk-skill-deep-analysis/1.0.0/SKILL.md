---
name: adk-skill-deep-analysis
description: 从产品视角深度拆解 AI Skill 的设计意图、独特解法和可借鉴模式
version: 1.0.0
last_updated: 2026-05-16
triggers:
  - 深度拆解 skill
  - 分析 skill 设计
  - 提取设计模式
  - skill 产品视角分析
non_triggers:
  - 编写新 skill
  - 修改现有 skill
inputs:
  - repo_path: 目标仓库路径
  - skill_name: 可选，指定分析某个 skill
outputs:
  - deep_analysis: Skill 深度分析报告 (Markdown)
constraints:
  - 禁止直接引用 description 字段，必须从实现细节反推
  - 每个解法必须提供"通用做法 vs Skill 做法"对比
  - 5 维评分必须给出具体证据
---

# 分析仓库的 prompt 结构

## Goal
从产品视角深度拆解目标仓库中的 Skill 设计，提炼可复用的设计模式、确定性边界和不适合吸收的风险。

## Prerequisites

- 理解相关领域的基本概念
- 熟悉项目结构和工作流程
- 具备基本的文档编写能力

## Workflow

1. 扫描资源构成：`SKILL.md`、scripts、references、assets、tests、manifest。
2. 反推真实痛点：禁止只摘 description，必须从流程、脚本和失败处理推导。
3. 标注模式类型：Tool Wrapper、Generator、Reviewer、Inversion、Pipeline 或混合型。
4. 拆解确定性边界：哪些步骤由脚本/模板/schema 固化，哪些留给 LLM 判断。
5. 检查渐进式披露：frontmatter、入口正文、references/assets 是否层次清晰。
6. 评估输出契约：产物、schema、pass/needs-fix、deny-path 和复验方式是否明确。
7. 提炼可借鉴点：每项必须包含通用做法、Skill 做法、设计巧思、适用边界。
8. 给出吸收建议：ADOPT、MERGE、REJECT、ENHANCE，并说明与现有 adk 资产关系。

## Pattern Checklist
- Tool Wrapper：看命令 allowlist、输入校验、错误码、回滚。
- Generator：看模板/schema、覆盖策略、格式化和测试。
- Reviewer：看证据路径、严重级别、误报处置。
- Inversion：看 stop/ask 条件、状态恢复、owner。
- Pipeline：看代码级状态机、checkpoint、resume/abort 和最终验证。


## Quality Gate
- 分析报告必须包含具体文件/行号证据
- 禁止直接引用 description 字段，必须从实现反推
- 5 维评分每项必须给出≥1个具体证据
- 输出报告必须包含"可借鉴点清单"章节
- 不得把临时参考素材直接写入长期 knowledge 或 adoption matrix


## Evidence Template

```md
status: pass | needs-fix | BLOCKED
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

## References
- 详细背景、命令、模板、示例和扩展检查项保存在 `references/details.md`。
- 入口文件只保留触发和执行所需的最小上下文，避免默认加载过多 token。
