---
name: adk-performance-profiling-embedded
description: "用于有指标的嵌入式性能分析、栈上界判读和真实负载 A/B；不用于无指标猜测或推断收益。"
version: 1.1.9
last_updated: 2026-11-20
triggers:
  - "性能分析"
  - "性能优化"
  - "性能调优"
  - "评估 MCU 栈上界"
  - "评估 RTOS 栈上界"
non_triggers:
  - 无性能指标诉求的小改
inputs:
  - 性能指标、采样数据
outputs:
  - 瓶颈定位与优化建议
constraints:
  - 优化收益须量化对比；仅定位瓶颈不要求候选改动
---

# adk-performance-profiling-embedded

## Goal
固定场景/KPI（时延、吞吐、CPU、内存、功耗），量化瓶颈/收益。

## Workflow
1. 核真实负载计数/正确输出；无活动 `run-validity=invalid`。固定源码/编译/输入 hash、设备、频率/温度/供电/预热、采样预算及扰动。
2. **定位瓶颈**：先低开销统计 CPU、等待/I/O、锁、内存，再按证据选可证伪候选/最小实验；无候选不强制 A/B。
3. **比较候选**：等价输入输出/有效负载下 A/B/A/B，核波动/漂移。时延 p50/p95/p99，吞吐 有效工作量/时间，Flash/RAM 段/峰值，能耗按同工作量；段大小不用分位数。
4. 核功能/内存/功耗/热稳定，超预算回滚；候选做真实长稳复验。无效 `invalid`，样本不足/噪声不可分 `inconclusive`，有效证据支持无收益才 `no-gain`；均留原因、不宣传收益。噪声先查环境；只读诊断不授权优化/设备配置变更。

## Target Execution Gate
- `linux-embedded`：核内核/用户态、架构、计数器权限/资源。CPU 用 perf/flame graph；堆峰值/时间线用 Massif，核采样/时间单位；错误/泄漏用 Memcheck；RSS 含非堆页，另测不互代。I/O 用 strace -T/perf trace，锁用 perf lock/lockstat；cache-misses 按 CPU/PMU/内核映射解释，不默认等同 LLC miss，LLC 须核专用事件；未知/不支持记 unavailable。核采样计数；热点不等于整体收益，用户态工具不通用于内核/MCU。
- `mcu-rtos` / `mcu-baremetal`：按支持用板端计数/trace、DWT/ETM、GPIO timing、stack/heap high-water、ELF/map；host 分析不能替代板端 `not-measured`。
- 核工具/系统/编译身份、权限和扰动；缺工具记 unavailable，不隐式注入/改配置。Valgrind 插桩耗时不当原生性能；不跨优化等级比较。

## Commands
按工具/窗口预算执行，留命令/退出码/耗时；失败不消费旧结果：
```bash
perf stat -p <pid> -- sleep <sample-window-seconds>
perf record -g -p <pid> -- sleep <sample-window-seconds> && perf report --stdio
valgrind --tool=callgrind --callgrind-out-file=callgrind.out <binary> && callgrind_annotate callgrind.out
```
benchmark 用项目命令，不猜参数。

## 按需实测
核运行对象/dispatch，或测 Flash/RAM/stack、DMA/retention、KWS/音频时读 `references/mcu-memory-footprint.md`。

交付原始证据、样本数/KPI/不确定性及复现入口；无有效采样只给假设与缺口。
