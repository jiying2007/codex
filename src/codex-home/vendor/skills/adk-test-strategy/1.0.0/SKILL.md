---
name: adk-test-strategy
description: 嵌入式全栈测试策略与 TDD 分级，覆盖板级、启动链、BSP、OS/runtime、驱动、组件、设备应用、上位机工具、量产和现场维护的验证证据
version: 1.0.0
last_updated: 2026-05-18
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
- 为嵌入式全栈项目提供优先级明确的测试策略，覆盖芯片/板级、启动链、BSP、OS/runtime、驱动、组件、设备应用、Linux 用户态、上位机、量产、现场维护和交付工具链。
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

## Embedded Full-stack Guidance
- 优先确认是否能在 host unit、SIL、仿真或交叉编译阶段提前暴露问题。
- 涉及寄存器、DMA、中断、时序、boot/rootfs、烧录、OTA、产测或硬件 errata 时，自动化测试不足必须记录 HIL、boot log、波形、寄存器读回、产测报告或手工验证证据。
- 嵌入式 TDD 矩阵模板：`references/embedded-tdd-matrix.md`。
- Linux 用户态、设备侧应用、上位机、产测诊断工具、烧录工具和现场维护脚本的语言测试属于嵌入式交付链路的一部分；通用 Web/互联网后端测试不纳入默认目标。

## Workflow
1. **识别行为面**：确认改动是否影响功能、接口、性能、安全、配置或发布产物。
2. **选择测试级别**：按风险和影响面选择 Level 0/1/2，并说明理由。
3. **发现现有入口**：读取仓库文档、脚本和测试目录，优先使用已有命令。
4. **设计测试矩阵**：覆盖 happy path、边界、错误路径、回归样例、真实世界边界、集成环境缺口、安全边界和无法模拟的运行条件。
5. **TDD 红灯检查**：Level 2 必须先写失败测试并记录失败原因。
6. **最小实现验证**：只实现让测试通过的必要代码，避免顺手扩张范围。
7. **回归扩展**：对共享逻辑或公共接口追加相关测试。
8. **证据记录**：记录命令、退出码、结果摘要和关联工件。
9. **完成前衔接**：把测试证据交给 `adk-verification-before-completion`。

## Evidence Template
```md
- Test Level: 0 | 1 | 2
- TDD Decision: required | not-required + reason
- Behavior Surface:
- Test Matrix:
  | Case | Type | Command | Expected |
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
- 不得只用覆盖率数字替代测试结论；必须说明现实环境、集成、安全或硬件条件中仍未验证的部分。
- 所有完成结论必须交给 `adk-verification-before-completion` 复核。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "只是小改不用测" | 小改也可能影响共享路径 | 至少 Level 0 定向验证 |
| "先写完再补测试" | 这会让测试从实现派生 | Level 2 场景必须先红灯 |
| "没有测试框架" | 没框架不等于没验证 | 记录 smoke、脚本或手工验证步骤 |
