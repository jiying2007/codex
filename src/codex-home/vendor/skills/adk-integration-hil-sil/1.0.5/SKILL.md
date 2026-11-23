---
name: adk-integration-hil-sil
description: "用于软件在环与硬件在环的集成测试、场景配置与结果证据编排；不用于仅做单元测试或绕过真实设备操作授权。"
version: 1.0.5
last_updated: 2026-11-20
triggers:
  - "集成测试"
  - "HIL测试"
  - "SIL测试"
non_triggers:
  - 只改注释文档
inputs:
  - 系统拓扑、测试资源
outputs:
  - HIL/SIL 用例矩阵
constraints:
  - 必须标注硬件依赖与替代方案
---

# adk-integration-hil-sil

## Goal
验证 SIL/HIL 系统行为并保留可复跑证据。

## Prerequisites
- 核设备族、board revision、固件 hash、runner、rig 占用、受控 operator 与恢复路径。
- 查项目真实 build/test 入口和插件，不猜选项；编程、探测、重启、断电、故障注入分别核授权和效果。

## Workflow
1. **层次与后端**：分开 host-unit、compile-only、SIL/QEMU、HIL、人工板级及量产资格；没有目标 runner，CTest 绿不证明上板。
2. **隔离**：冻结构建目录、二进制、缓存、端口/串口、rig 和设备身份，共享资源禁止并行。
3. **SIL**：运行真实入口，记录架构、模拟精度和未覆盖的硬件行为。
4. **HIL preflight**：只读核设备/固件、工装、停止条件与恢复；刷写或状态改变另交授权 operator。
5. **逐级扩大**：smoke→功能/异常回归→适用长稳。失联、身份漂移、core/fatal log 或恢复失败停止，不重试刷绿。
6. **资格与交付**：分开 pass/fail/skip/not-run，核必跑用例、日志、退出码与健康 postcondition；至少一条系统级异常恢复验证。SIL 不代 HIL/量产资格。

## Commands
仅用于已核 CMake/CTest ≥3.21 的 runner。`ADK_BINARY_DIR` 为本次绝对构建目录，`ADK_CONFIG` 为一致配置，`ADK_EVIDENCE_DIR` 为已有任务证据目录；筛选时保留参数和必跑身份。
```bash
# hil-sil-ctest:
set -euo pipefail
report_dir=$(mktemp -d "$ADK_EVIDENCE_DIR/ctest.XXXXXXXX")
report="$report_dir/ctest.xml"
printf 'CTest report: %s\n' "$report"
ctest --test-dir "$ADK_BINARY_DIR" -C "$ADK_CONFIG" --output-on-failure --no-tests=error --output-junit "$report"
```
此段只采集报告并保留命令失败，**不自动判整项通过**。读取新 JUnit 的每个 testcase：`run` 且无 failure/error/skipped 才是 pass；`notrun`/`skipped` 和 `disabled` 分列。缺失、畸形、未知状态、任一失败、零实际 pass 均不合格；混合 pass/skip 为 partial，缺必跑项 blocked。`--no-tests=error` 不拒绝全部动态 skip，不能只信 exit 0。沿用项目报告工具，不消费旧 JUnit；pytest 等使用其已核插件/报告格式。

## Budget / Retry
- 按动作、恢复 SLA、负载和阶段定 timeout/退避/重试，不套统一秒数或次数。
- 外部效果未知先对账 artifact、boot_id、device status；无设备/授权记 not-run/blocked。

## Evidence Template
```md
- Layer / Backend / Cases: selected / pass / fail / skip / disabled / not-run
- Environment: toolchain / runner / rig / device / firmware hash
- Command / Configuration / Selector / Exit / Duration / Fresh Report:
- Required Cases / Missing Cases / Qualification:
- Failure Reproduction / Serial-or-bus Evidence / Final Health:
- Uncovered Hardware / Next Verification / Release-gate Owner:
```

## Failure Handling
- HIL 不可用可继续 SIL，保留硬件缺口；冲突先核环境与 mock 假设。
- 超时保留日志再核连接与板状态；刷写失败按既定恢复路径核通道、供电和固件身份。

## Quality Gate
明确覆盖分工、异常恢复、固件/设备身份、用例结果与最终健康；有串口则附原始日志。未执行/未解释失败不算 PASS；go/no-go 归项目发布门禁。

依据：[CTest JUnit](https://cmake.org/cmake/help/v3.21/manual/ctest.1.html)。
