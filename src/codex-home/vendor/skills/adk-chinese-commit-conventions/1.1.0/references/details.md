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

## 格式

```
<type>(<scope>): <中文描述>

<body>

<footer>
```

## Type 类型详解

| Type | 中文 | 用途 | 触发条件 |
|------|------|------|---------|
| feat | 新功能 | 新增功能 | 有新用户可见行为 |
| fix | 修复 | 修复 bug | 修复已有功能缺陷 |
| docs | 文档 | 文档变更 | 仅修改文档/注释 |
| style | 格式 | 代码格式 | 空格/缩进/换行，不影响逻辑 |
| refactor | 重构 | 代码重构 | 既不修 bug 也不加功能 |
| perf | 性能 | 性能优化 | 提升性能且不改变行为 |
| test | 测试 | 测试相关 | 添加/修改测试 |
| chore | 杂项 | 构建/工具/配置 | 构建脚本、依赖更新 |
| ci | CI | CI/CD 相关 | CI 配置、流程变更 |
| revert | 回退 | 回退提交 | 回退之前的提交 |

## Scope 规则

- 使用模块名: `feat(driver): 新增 I2C 驱动初始化`
- 使用功能名: `fix(auth): 修复 token 过期未刷新`
- 使用文件名: `docs(readme): 更新安装说明`
- 多个 scope 用逗号: `feat(driver,hal): 统一接口抽象`
- 纯内部可省略: `refactor: 简化日志模块`

## 示例

### 标准提交
```
feat(driver): 新增 I2C 驱动初始化流程

- 实现设备树解析
- 添加 DMA 传输支持
- 包含单元测试

Closes #123
```

### 修复提交
```
fix(rtos): 修复任务调度优先级反转问题

使用优先级继承协议修复互斥锁导致的优先级反转。
高优先级任务等待低优先级任务释放锁时，临时提升低优先级。

Fixes #456
```

### 破坏性变更
```
feat(api)!: 重构用户认证接口

BREAKING CHANGE: 移除旧版 /auth/login 接口，
统一使用 /api/v2/auth/login。
迁移指南见 docs/migration/v2-auth.md

Closes #789
```

### 简短提交
```
docs: 更新 README 安装说明
style: 统一缩进为 4 空格
chore: 升级依赖到最新版本
```

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

## Commands
```bash
# 查看待提交变更
git diff --cached --stat
git diff --cached

# 标准提交
git commit -m "<type>(<scope>): <描述>"

# 多行提交
git commit -m "<type>(<scope>): <描述>" -m "<body>"

# 校验最近 commit message 格式
git log --oneline -10 | grep -E "^[a-f0-9]+ (feat|fix|docs|style|refactor|perf|test|chore|ci|revert)"

# 使用 commitlint 校验（如已安装）
echo "<type>(<scope>): <描述>" | npx commitlint 2>/dev/null || echo "commitlint not installed"

# 检查是否有破坏性标记
git log --oneline -20 | grep "!"
```

## 校验规则

| 规则 | 说明 | 正则 |
|------|------|------|
| type 合法 | 必须为预定义 type | `^(feat\|fix\|docs\|style\|refactor\|perf\|test\|chore\|ci\|revert)` |
| scope 格式 | 小写字母/数字/逗号 | `^\([a-z0-9,]+\)` |
| 描述非空 | 冒号后必须有内容 | `: .+` |
| 描述长度 | 不超过 72 字符 | `^.{1,72}$` |
| 中文优先 | 描述使用中文 | 人工校验 |

## Evidence Template
```md
- commit message: <完整 message>
- type: <feat/fix/docs/...>
- scope: <模块名>
- 描述: <中文描述>
- 格式检查: pass / needs-fix
- 破坏性变更: yes / no
- 关联 issue: #NNN / 无
- commit hash: <hash>
```

## Failure Handling
- commit message 格式不合规时，用 `git commit --amend` 修正。
- 不确定 type 时，查看变更内容后选择最匹配的。
- 描述过长时，精简为一行摘要 + body 详细说明。
- scope 不确定时，查看变更涉及的主要模块。

## Quality Gate
- commit message 符合格式规范。
- type 和 scope 准确反映变更内容。
- 描述使用中文且简洁准确（<50 字）。
- 破坏性变更必须标记 `!` 和 `BREAKING CHANGE` footer。
- 修复类提交必须关联 issue 编号。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "改动很小不用规范" | 小改动也需要可追溯 | 按格式写 commit message |
| "用英文更专业" | 中文团队用中文更高效 | 使用中文描述 |
| "来不及写详细了" | 10 秒写一行规范 message 不算慢 | 至少写 type(scope): 描述 |
| "git log 能看 diff 就行" | diff 不告诉你 why | commit message 记录意图 |

## 健壮性规范

- **输入验证**: 检查 type 和 scope 合法
- **重试策略**: commit 被拒绝时修正 message 重试
- **超时控制**: 写 commit message 不超过 2 分钟
- **异常隔离**: message 格式错误不影响代码
- **日志记录**: 记录最终 commit hash 和 message
