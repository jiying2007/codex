---
name: adk-chinese-commit-conventions
description: 中文 Git 提交规范——适配国内开发团队
version: 1.1.0
last_updated: 2026-05-06
triggers:
  - "中文提交"
  - "commit 规范"
  - "提交信息格式"
  - "写 commit message"
  - "git commit"
  - "提交格式"
  - "commit message 格式"
non_triggers:
  - "需求模糊"
  - "调试代码"
inputs:
  - 代码变更内容
outputs:
  - 格式化的 commit message
constraints:
  - 使用中文提交信息
  - 遵循 conventional commits 格式
---

# 中文 Git 提交规范

## Goal
- 提供适配国内开发团队的 Git 提交规范，确保 commit message 可读、可追溯。


## Prerequisites
- 确认代码变更已完成且可提交。
- 获取最小上下文：变更内容、影响范围。


## Workflow
1. **检查变更内容**：确认哪些文件被修改，变更类型是什么。
   ```bash
   git diff --cached --stat
   git diff --cached
   ```
2. **选择 type 和 scope**：根据变更内容选择最匹配的 type。
3. **编写中文描述**：简洁准确，动词开头，不超过 50 字。
4. **补充 body（可选）**：复杂变更需要说明原因和影响。
5. **补充 footer（可选）**：关联 issue、标记破坏性变更。
6. **组装并提交**：
   ```bash
   git commit -m "feat(driver): 新增 I2C 驱动初始化" -m "- 实现设备树解析
   - 添加 DMA 传输支持"
   ```


## Quality Gate
- commit message 符合格式规范。
- type 和 scope 准确反映变更内容。
- 描述使用中文且简洁准确（<50 字）。
- 破坏性变更必须标记 `!` 和 `BREAKING CHANGE` footer。
- 修复类提交必须关联 issue 编号。


## Failure Handling
- commit message 格式不合规时，用 `git commit --amend` 修正。
- 不确定 type 时，查看变更内容后选择最匹配的。
- 描述过长时，精简为一行摘要 + body 详细说明。
- scope 不确定时，查看变更涉及的主要模块。


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
