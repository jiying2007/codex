---
name: adk-bsp-analysis
description: 用于梳理嵌入式 BSP 源码、启动/探测与资源依赖，对照硬件依据、patch/workaround 历史及 SoC/board 差异，交付证据化架构和迁移风险；不用于直接实现驱动或 live 板级故障隔离。
version: 2.0.3
last_updated: 2026-11-20
triggers:
  - BSP 分析/BSP 梳理/分析 BSP/梳理 BSP/梳理这个 BSP/梳理现有 BSP
  - BSP 代码梳理
  - BSP 架构分析
  - BSP patch 历史
  - SoC board 迁移分析
implicit_context: ["BSP/SoC"]
non_triggers:
  - 直接驱动开发
  - live 硬件调试
  - 发布放行
inputs:
  - BSP 代码目录
  - SoC/board/kernel 或 RTOS identity
  - datasheet/reference manual/errata
  - patch/commit/log 证据
outputs:
  - BSP 架构与调用链摘要
  - confirmed/inferred/unknown findings
  - patch/兼容/迁移风险
  - evidence refs 与下一步验证
constraints:
  - 硬件结论必须引用权威资料章节或可重放运行证据
  - 推断与事实必须分离
  - 不在本 Skill 执行驱动实现或高风险硬件写操作
---

# adk-bsp-analysis

## Goal
追踪 BSP 源码、资源与硬件依据，区分事实/推断/未知和迁移风险。

## Prerequisites
- 明确 BSP root、SoC、board、kernel/RTOS 版本与目标问题。
- 至少能访问源码；涉及寄存器/时序结论时还需要权威 hardware reference。

## Target Family Gate
按真实目标分支读取：`linux-embedded` 关注 bootloader/kernel/DTS/probe，`mcu-rtos` 关注内核配置、任务/驱动/板级初始化（Kconfig/Devicetree 仅在真实支持的平台适用），`mcu-baremetal` 关注启动向量、链接脚本、时钟复位和寄存器初始化。未确认 SoC/board/toolchain 时标 `unknown`；不得以 Zephyr 或 Linux 的机制强套普通裸机 MCU。

## Workflow
1. **Scope identity**：锁定 BSP root、版本/commit、SoC、board、bootloader/kernel/RTOS identity 和分析问题。
2. **Structure map**：定位 arch/platform、board/DTS、drivers、include、boot/init 与 vendor abstraction 入口。
3. **Boot/probe path**：追踪初始化注册、match/probe、资源获取与关键状态转换；只展开与目标问题相关的链路。
4. **Resource graph**：按需追踪 clock、reset、power/domain、pinctrl/GPIO、IRQ、DMA、memory/map、bus dependency；不得机械地为每个 BSP 全扫一遍。
5. **Hardware correlation**：把关键寄存器、位域、时序或 errata 映射到 authoritative section；没有资料时标为 unknown。
6. **History**：读取相关 patch/commit/workaround，区分原始设计、兼容层、临时 workaround 和已废弃路径。
7. **Synthesis**：输出 confirmed / inferred / unknown、关键 call/dependency graph、迁移/兼容风险和最小下一步验证。

详细搜索模式与证据组织见 `references/bsp-analysis-details.md`，仅在需要展开代码/历史追踪时加载。

## Failure / Escalation
- 任务转为代码实现 → `driver-engineer` / implementation Skill。
- 需要 shared architecture 决策 → `architecture-planner`。
- live board fault isolation → `hardware-debugger`。
- 硬件资料冲突或缺失 → `needs-evidence`，不得将经验判断写为 confirmed。

## Quality Gate
- 每个高影响 finding 都能回到 code location、commit/log 或 hardware section。
- `confirmed`、`inferred`、`unknown` 明确分离。
- 输出不包含未请求的完整 BSP 百科；只加载当前问题需要的资源链路。
- migration risk 绑定受影响 owner/consumer 和验证动作。

## Evidence Template
```md
- Scope identity:
- Question:
- Entry points:
- Dependency / call graph:
- Findings:
  - status: confirmed | inferred | unknown
    evidence_refs:
    impact:
    verification:
- Patch/history observations:
- Migration/compatibility risks:
- Result: complete | needs-evidence | blocked
```
