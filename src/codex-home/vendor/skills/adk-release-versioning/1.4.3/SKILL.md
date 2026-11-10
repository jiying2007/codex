---
name: adk-release-versioning
description: "用于规划版本号、Changelog 和发布基线并检查历史版本一致性；不执行真实发布，也不用于替代固件包验证或设备更新。"
version: 1.4.3
last_updated: 2026-11-09
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
- 核对版本与回退证据。


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
   - 读取目标项目真实的 release policy、版本 SSOT、CI 与回滚机制，通用 Skill 不假设 ADK 发布链适用于任意仓。
   - 合并前校验 exact base 与版本合法性；受保护主线 fresh CI 后才进行签名和制品发布，不覆盖不可变 tag。
   - **仅对 agent-dev-kit 源仓** 使用 source SemVer 门禁、successful-main CI → release-tag-promotion → exact annotated tag → canonical release，并核验 digest/attestation。
   - 非 ADK 项目没有上述工作流时标记 `not_applicable`，改用该项目实际审查过的发布门禁，不得伪造结果。
8. **发布签署**：输出 go/no-go 结论与残留风险，并记录 tag、commit、GitHub Release 与 artifact digest。


## Quality Gate
- 必须给出版本号决策依据。
- 阶段式迁移必须给出阶段结论与回退锚点。
- 必须附完整迁移与回退步骤。
- 必须明确发布门禁结论与签署条件。
- 版本、tag 与受保护 CI 必须符合目标项目发布政策；仅 ADK 自身要求 source SemVer、annotated tag 及 successful-main promotion。
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
