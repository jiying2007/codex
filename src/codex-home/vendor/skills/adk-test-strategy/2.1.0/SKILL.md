---
name: adk-test-strategy
description: 平台中立的软件测试策略与 TDD 分级，按行为、风险和现有测试入口生成可复跑的验证矩阵与证据
version: 2.1.0
last_updated: 2026-09-10
triggers:
  - "测试策略"
  - "TDD"
  - "先写测试"
  - "补测试"
  - "回归测试"
  - "测试矩阵"
  - "验证策略"
non_triggers:
  - 纯文档修改且无行为变化
  - 已有完整测试计划且只需执行命令
inputs:
  - 需求类型、行为变化、技术栈、现有测试入口、风险等级
outputs:
  - 测试级别、TDD 决策、测试矩阵、验证命令与证据要求
constraints:
  - 行为变化必须给出测试或明确说明不可测试原因
  - 高风险变更不得只依赖手工检查
  - 没有红灯证据不得声称完成 TDD
---

# adk-test-strategy

## Goal
- 为通用软件项目提供优先级明确的测试策略，覆盖库、服务、应用、CLI、配置、数据、构建和交付链路。
- 根据风险选择 Level 0 到 Level 2 的测试纪律，避免所有任务机械套用重 TDD。
- 将验证结论落到可复跑命令和 Evidence Index，而不是口头确认。

## Prerequisites
- 已确认本次变更是否改变用户可见行为、公共接口、数据结构或配置加载。
- 已定位项目测试入口，例如 `ctest`、交叉编译 smoke、SIL/HIL 脚本、`pytest`、`go test ./...`。
- 已读取现有测试风格，避免引入与项目不一致的测试框架。

## 测试分级

| Level | 适用场景 | 要求 |
|---|---|---|
| Level 0 定向验证 | 文档、小配置、无行为代码整理 | 运行最小 smoke 或静态检查 |
| Level 1 回归测试 | bugfix、局部行为变化、脚本调整 | 先复现或补回归用例，再跑相关测试 |
| Level 2 TDD | 新功能、共享逻辑、公共接口、高风险修复 | 先红灯，再最小实现，再绿灯和重构 |

## Domain-specific Guidance
- 本 Skill 只定义平台中立的 Level 0/1/2、red/green、回归和 Evidence Index 合同。
- 嵌入式项目在 `embedded-fullstack` Profile 下组合 `adk-unit-test-embedded`、`adk-integration-hil-sil`
  和 `adk-production-field-readiness`；板级、SIL/HIL、boot、OTA、产测矩阵不得进入 core 默认上下文。
- Web、服务端、桌面、移动端或数据项目应复用目标仓已有测试入口，不从 ADK core 引入特定框架。

## Workflow
1. **识别行为面**：确认改动是否影响功能、接口、性能、安全、配置或发布产物。
2. **选择测试级别**：按风险和影响面选择 Level 0/1/2，并说明理由。
3. **发现现有入口**：读取仓库文档、脚本和测试目录，优先使用已有命令。
4. **设计测试矩阵**：覆盖 happy path、边界、错误路径、回归样例、真实世界边界、集成环境缺口、安全边界和无法模拟的运行条件。
5. **验证资源矩阵**：并行执行前列出每项验证的输出目录、二进制/缓存、端口/设备与写入资源；只有全部写入资源隔离才可并行，共享 build directory、测试二进制或中间产物必须串行。
6. **TDD 红灯检查**：Level 2 必须先写失败测试并记录失败原因。
7. **最小实现验证**：只实现让测试通过的必要代码，避免顺手扩张范围。
8. **回归扩展**：对共享逻辑或公共接口追加相关测试。
9. **证据记录**：记录命令、退出码、结果摘要和关联工件。
10. **完成前衔接**：把测试证据交给 `adk-verification-before-completion`。

## Evidence Template
```md
- Test Level: 0 | 1 | 2
- TDD Decision: required | not-required + reason
- Behavior Surface:
- Test Matrix:
  | Case | Type | Command | Expected |
  |---|---|---|---|
- Validation Resource Matrix:
  | Validation | Output directory | Binary/cache/device | Parallel decision |
  |---|---|---|---|
- Red Evidence:
- Green Evidence:
- Regression Commands:
- Gaps / Not Tested:
- Evidence Index:
```

## Commands
```bash
# Python
pytest -q

# Node.js
npm test -- --runInBand

# Go
go test ./...

# Rust
cargo test

# C/CMake
ctest --output-on-failure
```

## Failure Handling
- 测试入口不明确时，先做只读扫描，不得凭空发明框架。
- 红灯测试直接通过时，说明测试没有覆盖缺失行为，必须修正用例。
- 测试失败超过两轮仍无根因时，切换到 `adk-systematic-debugging`。
- 测试无法执行时，必须记录环境缺口和替代验证，不得声称通过。

## Quality Gate
- 输出必须包含测试级别、测试矩阵和至少一个可复跑验证命令。
- Level 2 必须包含红灯和绿灯证据。
- bugfix 必须包含复现或回归样例；无法自动化时必须说明原因。
- 共享逻辑改动必须说明回归范围。
- 声称并行的验证必须有 Validation Resource Matrix；共享输出目录、二进制、缓存、端口或设备时必须串行。
- 不得只用覆盖率数字替代测试结论；必须说明现实环境、集成、安全或硬件条件中仍未验证的部分。
- 所有完成结论必须交给 `adk-verification-before-completion` 复核。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "只是小改不用测" | 小改也可能影响共享路径 | 至少 Level 0 定向验证 |
| "先写完再补测试" | 这会让测试从实现派生 | Level 2 场景必须先红灯 |
| "没有测试框架" | 没框架不等于没验证 | 记录 smoke、脚本或手工验证步骤 |
