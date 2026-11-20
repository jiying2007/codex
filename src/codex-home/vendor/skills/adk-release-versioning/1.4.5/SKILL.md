---
name: adk-release-versioning
description: "用于规划版本号、Changelog 和发布基线并检查历史版本一致性；不执行真实发布，也不用于替代固件包验证或设备更新。"
version: 1.4.5
last_updated: 2026-11-20
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
核对版本、完整变更范围和回退证据；不执行真实发布。

## Prerequisites
确认目标 commit、受影响用户及项目版本、正式发布、CI 和回滚政策；首发需明确确认。

## Workflow
1. **冻结范围**：正式发布记录确定 baseline，核其为目标祖先；不自动选择最近 tag。shallow/缺历史先按授权补齐，不改用首发。
2. **完整取证**：使用 `references/details.md` 的只读示例保留全部 hash、subject、body；首发列所有可达历史，Git 失败立即停止。
3. **版本与 Changelog**：逐条核实际影响并分类，breaking/revert/build/ci/未知类型均保留审阅去向；按兼容性决定 major/minor/patch 和迁移说明。
4. **清单**：制品、依赖、配置、迁移、可回滚版本、触发条件和验证命令；阶段式迁移各列退出条件、证据及回退锚点。
5. **Promotion 交接**：核 exact base/版本，受保护主线 fresh CI 后才签名/发布，核 tag/digest/attestation。ADK 专用链见 reference；其他项目遵循自身政策。
6. **签署**：报告 go/no-go、残余风险和缺失证据，绑定 tag/commit/Release/digest；未执行不得声称已发布。

## Quality Gate
- 历史与分类覆盖全部待发布变更；撤销及非用户可见项也保留依据，不冒充仍生效的功能。
- 版本、迁移/回退、阶段结论和签署条件可追溯，tag/CI 符合目标政策。

## Failure Handling
- 空清单先核 baseline/HEAD；Git 错误、历史不完整、版本不匹配或缺回退 → `needs-fix`。
- 同名 tag 指向不同 commit 必须提升 SemVer，禁止覆盖；已有 Release 仅在 assets 与 validated bundle byte-identical 时可幂等通过。
- ADK tag 已存在但 Release 缺失，不重建 tag；self-heal audit 绑定 exact tag/commit 后补发。

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
需要完整历史命令、SemVer 对照或 ADK 发布边界时读 `references/details.md`。
