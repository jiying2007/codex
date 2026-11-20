---
name: adk-unit-test-embedded
description: "用于 MCU/RTOS 及其 host 模型的单元测试断言、性质/状态序列测试与外设替身；非跨模块策略，不用于证明真实 HIL 性能。"
version: 1.1.9
last_updated: 2026-11-20
triggers:
  - "单元测试/单测"
  - "写测试/测试用例"
  - "MCU 性质测试/嵌入式性质测试"
  - "RTOS 状态序列测试/嵌入式状态序列测试"
implicit_context: ["MCU/RTOS/嵌入式/embedded/firmware/固件/单片机/Cortex-M/Zephyr/bare-metal"]
non_triggers:
  - "纯硬件连线问题/非嵌入式/不涉及嵌入式/non-embedded"
inputs:
  - 模块接口、边界条件
outputs:
  - 设计交用例/断言；授权实施交测试/fixture 路径、命令/结果
  - 硬件/实时缺口及验证条件
constraints:
  - 优先覆盖边界与错误路径
---

# adk-unit-test-embedded

## Goal
按 MCU/RTOS 及其 host 模型的公开契约测试，复用入口与 mock/stub。

## Target / Test Seam Gate
- 选 host-unit、cross-build compile-only、SIL/emulator、HIL/board-runner 并记录；compile-only 不证明断言运行。先核工具/runner/compiler flags/libc 支持，不默认 MCU 能跑 host 工具。
- 测公开接口可观察状态，不以 mock 内部调用次数自证。W1C、DMA ownership、ISR/任务竞态、队列溢出加适用负例；电气/实时边界无法模拟则 `needs-hil`。

## Workflow
1. 读接口/验收/缺陷，核外设/时钟/全局替身；按契约给输入/期望，含边界/错误路径。
2. 解析器/编解码/队列/lifecycle 组合较多时读 `references/property-stateful-tests.md`，用独立性质和有界状态序列，核有效输入非空、状态复位和反例回放。
3. 设计交清单；授权实现须交测试/fixture。缺陷先复现，再核修复/同根因变体/原通过路径。
4. 跑已核定向命令，交版本/层次/路径/断言/退出码/缺口；未执行 `not-run`。不稳查时间依赖/共享状态，覆盖噪声回到关键路径。

跨板级、boot、OTA/现场层次读 `references/embedded-tdd-matrix.md`。内存/UB/线程竞争需要动态取证时按需交 `adk-systematic-debugging` 的 sanitizer 方法；未安装或 runtime 不支持则保留缺口，不能把普通单测当插桩通过。

## Commands
仅选项目已有工具，不全跑示例或为未知 runner 造 `--module` 参数。
```bash
ceedling test:<module_name>
ceedling gcov:<module_name>
# 启用 module_generator 后生成源/头/测试骨架；CMock mock 由依赖头和配置生成
ceedling "module:create[Sensor]"
gcovr --root . --filter src/ --xml -o coverage.xml
lcov --capture --directory build --output-file coverage.info
genhtml coverage.info --output-directory coverage_html
```

## 覆盖与交付
行/分支/函数覆盖按风险/基线设目标并留报告，不用统一百分比认证。条件/决策覆盖（含 BullseyeCoverage）不等于 MC/DC；安全关键场景核规范/工具能力/独立 MC/DC 报告，缺证据 `not-evaluated`。覆盖不代替板级时序/HIL；缺陷修复附可追溯回归。
