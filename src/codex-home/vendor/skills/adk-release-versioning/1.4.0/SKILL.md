---
name: adk-release-versioning
description: 版本策略、变更说明与发布基线
version: 1.4.0
last_updated: 2026-09-19
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
7. **Promotion 发布**：
   - 先用版本管理器同步并验证 source identity。
   - PR 合并前必须先前移 source SemVer；required `contract-py3.11` 会把 head 与 exact base 比较，未前移直接拒绝。
   - 只把 source/PR 合并到受保护的 `main`；不要手工移动、覆盖或复用已有版本 tag。
   - `main` fresh CI 成功后，由 `release-tag-promotion` 对 exact main SHA 创建 annotated version tag，并调用 canonical release workflow。
   - canonical release 必须从 exact tag 构建、校验、attest，并发布 GitHub Release；已有同 tag Release 只能在资产 byte-identical 时视为幂等成功。
   - v7+ exact annotated tag 若因 package 阶段失败而缺少 Release，后续 successful-main promotion 会审计 immutable/asset/source identity 并通过 canonical release 自动补发；禁止移动旧 tag。
8. **发布签署**：输出 go/no-go 结论与残留风险，并记录 tag、commit、GitHub Release 与 artifact digest。


## Quality Gate
- 必须给出版本号决策依据。
- 阶段式迁移必须给出阶段结论与回退锚点。
- 必须附完整迁移与回退步骤。
- 必须明确发布门禁结论与签署条件。
- PR 合并前 source SemVer 必须严格高于 exact base；正式 Tag 必须为 annotated tag，并由 successful-main promotion 自动创建。
- Changelog 必须覆盖自上次发布以来的所有变更。


## Failure Handling
- 版本号与变更类型不匹配时，停止切版并重审。
- 缺失回退路径时，结论必须为 `needs-fix`。
- Changelog 为空时，检查 commit message 是否符合规范。
- Tag 创建失败时，检查同名 tag 是否已存在；若已指向不同 commit，必须提升 SemVer，禁止覆盖旧 tag。
- GitHub Release 已存在时，只有远端 assets 与本轮 validated bundle byte-identical 才允许幂等通过。
- Tag 已存在但 Release 缺失时，不删除或重建 tag；由 self-heal audit 绑定 exact tag/commit 后补发。


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
