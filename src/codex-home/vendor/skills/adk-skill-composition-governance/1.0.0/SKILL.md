---
name: adk-skill-composition-governance
description: 治理技能组合、触发优先级、fallback 与弃用关系
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "技能组合"
  - "触发冲突"
  - "技能治理"
non_triggers:
  - 单个 skill 文案微调且不影响触发规则
  - 仅安装已有 profile 且不改变组合关系
inputs:
  - skill 清单、触发词、non_trigger、profile、候选任务场景
outputs:
  - 主技能、辅助技能、fallback、互斥关系和弃用决策
constraints:
  - 一个场景只能有一个主技能
  - 辅助技能不得抢占主技能触发
---

# adk-skill-composition-governance

## Goal
- 用小技能组合提高覆盖面，同时避免 `~/.codex` 中触发噪音和职责重叠。
- 建立技能组合规则、冲突检测机制和治理矩阵。

## Prerequisites
- 已列出涉及的 skill、optional skill 和目标 profile。
- 已有至少一条代表性任务输入。

## Workflow
1. 确定主技能：每个场景选择一个 primary skill。
2. 标注辅助技能：supporting skills 只作为建议，不直接抢占入口。
3. 定义 fallback：主技能不适用时，给出明确后备 skill。
4. 定义互斥关系：职责冲突或触发重叠时，明确优先级。
5. 冲突检测：检查触发词重叠与职责边界模糊。
6. 弃用治理：旧技能需给 `deprecated_by` 或 `replaced_by`。
7. 回归样例：为每个组合场景补触发测试。
8. 更新治理矩阵：记录所有组合规则与优先级决策。

## 技能组合规则
```md
[composition-rules]
rule-1: 一个场景只能有一个 primary skill，禁止多主竞争。
rule-2: supporting skills 只在 primary 明确请求时激活。
rule-3: fallback skill 必须在 profile 中可安装。
rule-4: 互斥 skill 必须有明确优先级，禁止同时激活。
rule-5: deprecated skill 必须有替代方案，禁止无替代弃用。
```

## 冲突检测
```bash
# 检查触发词重叠
comm -12 <(sort skill-a-triggers.txt) <(sort skill-b-triggers.txt)

# 检查 non_trigger 边界
rg -n "non_triggers:" skills/*/SKILL.md

# 列出所有触发词
rg -n "triggers:" skills/*/SKILL.md | sed 's/.*triggers: //' | tr ',' '\n' | sort | uniq -d
```

## 依赖图模板
```md
[dependency-graph]
场景: <场景名称>
primary: <主技能>
supporting:
  - <辅助技能-1>: <激活条件>
  - <辅助技能-2>: <激活条件>
fallback: <后备技能>
mutually_exclusive:
  - <互斥技能>: <优先级>
deprecated:
  - <旧技能> → <新技能>: <迁移说明>
```

## 治理矩阵
```md
[governance-matrix]
| 场景 | 主技能 | 辅助技能 | Fallback | 互斥 | 优先级 |
|------|--------|----------|----------|------|--------|
| <场景1> | <skill-a> | <skill-b> | <skill-c> | <skill-d> | 1 |
| <场景2> | <skill-e> | <skill-f> | <skill-g> | <skill-h> | 2 |

决策依据:
- <场景1>: <skill-a> 优先因为 <原因>
- <场景2>: <skill-e> 优先因为 <原因>
```

## Commands
```bash
# 重建技能目录
bash scripts/devkit.sh catalog build

# 测试技能匹配
bash scripts/devkit.sh match --skill <skill> --text "<task text>"

# 检查运行时路由
bash ../scripts/check-runtime-routing.sh ..

# 列出所有触发词
rg -n "triggers:" skills/*/SKILL.md optional-skills/*/SKILL.md

# 检查触发词冲突
rg -n "triggers:" skills/*/SKILL.md | awk -F: '{print $3}' | sort | uniq -d

# 验证 profile 一致性
bash scripts/check_profile_coherence.sh
```

## Evidence Template
```md
- Scenario:
- Primary Skill:
- Supporting Skills:
- Fallback Skill:
- Mutually Exclusive Skills:
- Deprecated/Replaced Decision:
- Trigger Regression:
- Composition Rules:
- Governance Matrix:
- Conflict Detection Results:
```

## Failure Handling
- 若一个场景出现多个主技能，结论固定为 `needs-fix`。
- 若 fallback 不可安装或不在 profile 中，退回 profile 设计。
- 若冲突检测发现触发词重叠但无优先级定义，必须补充治理矩阵。
- 若弃用技能无替代方案，必须冻结而非删除。

## Quality Gate
- 组合规则必须能被脚本检查。
- 触发样例必须覆盖正例、反例和 fallback。
- 治理矩阵必须覆盖所有已知场景。
- 冲突检测必须在每次 profile 变更后重新执行。
- 依赖图必须可视化展示技能间关系，禁止隐式依赖。
