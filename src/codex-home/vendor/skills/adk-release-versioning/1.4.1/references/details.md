---
name: adk-release-versioning
description: 版本策略、变更说明与发布基线
version: 1.1.0
last_updated: 2026-05-06
triggers:
  - "版本发布"
  - "版本管理"
  - "发版"
non_triggers:
  - 开发中临时调试
inputs:
  - 版本号策略、发布目标
outputs:
  - 发布清单与版本说明模板
  - 阶段门禁决策（baseline-aligned/migrate-ready/cutover-ready）
constraints:
  - 必须记录可回滚版本
  - 阶段式迁移必须记录每阶段回退锚点
---

# adk-release-versioning

## Goal
- 统一版本语义与发布清单，降低升级和回退风险。

## Prerequisites
- 确认版本策略（SemVer 或项目定制规则）。
- 收集本次发布范围、变更类型与受影响用户。

## 语义版本规则 (SemVer)

格式：`MAJOR.MINOR.PATCH[-prerelease]`

| 变更类型 | 版本位 | 示例 | 说明 |
|---------|--------|------|------|
| Breaking change | MAJOR+1 | 1.0.0 → 2.0.0 | API 不兼容、删除功能 |
| 新功能 | MINOR+1 | 1.0.0 → 1.1.0 | 向后兼容的新功能 |
| Bug 修复 | PATCH+1 | 1.0.0 → 1.0.1 | 向后兼容的修复 |
| 预发布 | 后缀 | 1.1.0-beta.1 | 测试阶段版本 |

判断规则：
- 有删除/重命名公开 API → MAJOR
- 有新增公开 API → MINOR
- 仅修复内部实现 → PATCH
- 不确定时选择更保守的版本位

## Workflow
1. **版本决策**：根据变更类型确定 major/minor/patch。
   ```bash
   # 查看最近版本
   git tag --list --sort=-version:refname | head -10
   # 查看自上次发布的变更
   git log $(git describe --tags --abbrev=0)..HEAD --oneline
   ```
2. **变更归档**：按 feat/fix/refactor/docs 分类生成 changelog。
3. **Changelog 生成**：
   ```bash
   # 按 type 分类生成 changelog
   git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"- %s" | \
     grep -E "^- (feat|fix|refactor|perf|docs)" | sort
   ```
4. **发布清单**：制品、依赖、配置变更、迁移步骤。
5. **阶段矩阵**：给出里程碑阶段、退出条件、验证证据与回退锚点。
6. **回退预案**：可回滚版本、触发条件、验证命令。
7. **打 Tag 并发布**：
   ```bash
   git tag -a v1.2.0 -m "release: v1.2.0"
   git push origin v1.2.0
   ```
8. **发布签署**：输出 go/no-go 结论与残留风险。

## Commands
```bash
# 查看版本历史
git tag --list --sort=-version:refname | head -10

# 查看两版本间变更
git log v1.0.0..HEAD --oneline

# 生成 changelog
git log $(git describe --tags --abbrev=0)..HEAD --pretty=format:"- %s (%h)" | sort

# 创建 annotated tag
git tag -a v1.2.0 -m "release: v1.2.0 - <变更摘要>"

# 推送 tag
git push origin v1.2.0

# 验证发布
git tag -v v1.2.0 2>/dev/null || echo "tag 未签名"
git log v1.2.0 --oneline -1

# 版本号一致性检查
grep -r "version" package.json Cargo.toml pyproject.toml 2>/dev/null
```

## Evidence Template
```md
- Version Decision:
  - 旧版本: vX.Y.Z
  - 新版本: vA.B.C
  - 决策依据: <breaking/feature/fix>
  - 变更统计: feat N 个, fix M 个, refactor K 个
- Change Summary:
  - feat: <列表>
  - fix: <列表>
  - breaking: <列表>
- Artifact List:
  | 制品 | 路径 | 校验和 |
  |------|------|--------|
  | ... | ... | sha256:... |
- Stage Gate Matrix:
  | 阶段 | 退出条件 | 验证证据 | 回退锚点 |
  |------|---------|---------|---------|
  | baseline-aligned | ... | ... | ... |
- Migration/Rollback Plan:
  - 迁移步骤: 1. ... 2. ...
  - 回退命令: `git checkout vOLD && <build-cmd>`
  - 回退验证: <命令>
- Release Gate Result: go / no-go + 残留风险
```

## Failure Handling
- 版本号与变更类型不匹配时，停止切版并重审。
- 缺失回退路径时，结论必须为 `needs-fix`。
- Changelog 为空时，检查 commit message 是否符合规范。
- Tag 创建失败时，检查是否已存在同名 tag。

## Quality Gate
- 必须给出版本号决策依据。
- 阶段式迁移必须给出阶段结论与回退锚点。
- 必须附完整迁移与回退步骤。
- 必须明确发布门禁结论与签署条件。
- Tag 必须为 annotated tag（`-a` 参数）。
- Changelog 必须覆盖自上次发布以来的所有变更。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "这次改动很小直接 patch" | 小改动也可能包含 breaking change | 按语义版本规则逐项检查变更类型 |
| "changelog 以后再补" | 以后永远不会补，用户无法了解变更 | 发布前必须生成完整 changelog |
| "tag 用 lightweight 就行" | lightweight tag 无法记录发布元信息 | 使用 `git tag -a` 创建 annotated tag |

---

## 健壮性规范

- **输入验证**: 执行前校验所有必要输入是否存在且格式正确
- **重试策略**: 外部命令失败时最多重试 3 次，指数退避（1s, 2s, 4s）
- **超时控制**: 单步操作超时 30 秒，整体流程超时 300 秒
- **异常隔离**: 单个步骤失败不阻塞其他独立步骤
- **日志记录**: 关键操作记录命令、退出码、耗时
