---
name: adk-chinese-code-review
description: 中文代码审查规范——适配国内团队沟通风格
version: 1.1.0
last_updated: 2026-05-06
triggers:
  - "代码审查"
  - "review 代码"
  - "检查代码质量"
  - "运行测试"
non_triggers:
  - "写代码"
inputs:
  - 代码变更（diff）
outputs:
  - 审查报告（中文）
constraints:
  - 使用中文输出
  - 先扬后抑的沟通风格
---

# 中文代码审查规范

## Goal

提供适配国内团队沟通风格的代码审查规范，确保审查意见既有技术深度又兼顾沟通效率。


## Prerequisites
- 确认代码变更（diff）完整且可读。
- 获取最小上下文：变更目的、影响范围。


## Workflow
1. **获取完整 diff**：确认变更范围和目的。
   ```bash
   git diff <base>...HEAD --stat
   git diff <base>...HEAD
   ```
2. **快速扫描**：先整体看一遍，了解变更意图和范围。
3. **逐项审查**：按五维度清单逐项检查。
4. **记录发现**：使用先扬后抑风格，标注严重性。
5. **生成审查报告**：按严重性排序，输出结构化报告。


## Quality Gate
- 五维度审查全覆盖。
- 审查意见使用中文且符合沟通风格。
- 发现已按严重性排序。
- Critical 发现必须有明确修复建议。
- 审查报告格式完整。


## Failure Handling
- diff 不完整时，要求补充后再审查。
- 审查遗漏时，补充检查并更新报告。
- 发现无法判断时，标记为"待确认"并给出建议。


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
