---
name: adk-offline-core-dump-triage
description: 嵌入式 Linux 离线 core dump 取证，先校验 core/binary/BuildID/符号/GDB 依赖，再给可信 backtrace、根因边界和下一步探针
version: 1.0.0
last_updated: 2026-06-28
triggers:
  - "core dump"
  - "core文件"
  - "离线core"
  - "BuildID"
  - "符号不匹配"
  - "gdb分析core"
  - "SIGSEGV core"
non_triggers:
  - "在线调试通道联调"
  - "只有普通运行日志没有core文件"
inputs:
  - core 文件、崩溃二进制、符号文件、运行日志、工具链/GDB 路径、目标 rootfs 或板端库目录
outputs:
  - 制品匹配结论、GDB 可用性、可信 backtrace、根因边界、缺失证据、下一步探针
constraints:
  - 不得在 BuildID 或符号不匹配时给源码级根因定论
  - 用户指定 GDB 路径时必须优先使用；工具起不来先报告依赖阻塞
  - 不能把 `??` backtrace 或缺库场景包装成已确认根因
---

# adk-offline-core-dump-triage

## Goal
- 对嵌入式 Linux core dump 做可复核的离线取证。
- 先证明 core、binary、symbol、rootfs 和 GDB 可用，再判断 crash site、likely root cause 和剩余风险。

## Prerequisites
- 已定位 core 文件和候选可执行文件。
- 已知道目标架构、工具链或用户指定 GDB 路径。
- 有运行日志、版本 banner、commit hash、BuildID 或产物目录中的至少一种匹配线索。

## Workflow
1. 盘点制品：core、executable、`.debug`/`.debug.full`、shared libraries、运行日志和源码 checkout。
2. 校验匹配：读取 BuildID、文件时间、版本 banner、commit hash 和路径；匹配失败只输出 partial diagnosis。
3. 校验工具：先运行目标 GDB 的 `--version` 或最小 core 加载；缺 `libncurses` 等宿主依赖时停止源码级归因。
4. 加载符号：设置 `sysroot`、`solib-search-path` 和源码路径，记录每个库是否找到符号。
5. 提取证据：`info threads`、`thread apply all bt`、crash thread、PC/LR/SP、fault address、关键对象状态。
6. 区分层级：把 crash site、trigger、likely root cause、blocked evidence 分开写。
7. 回到代码：只对已匹配的 frame 做源码路径和对象生命周期分析；对优化内联或缺符号帧保守标注。
8. 给下一步：补齐板端库、重编 debug 符号、加最小日志/断言、复现命令或现场采集清单。

## Commands
```bash
rtk file <core-file> <binary>
rtk readelf -n <binary>
rtk readelf -n <core-file>
rtk <target-gdb> --version
rtk <target-gdb> <binary> <core-file>
```

## Evidence Template
```md
- Artifacts:
- Match Check:
  - binary_build_id:
  - core_exe:
  - symbols:
  - sysroot/libs:
- GDB Status:
- Trusted Frames:
- Crash Site:
- Likely Root Cause:
- Blocked Evidence:
- Next Probes:
- Confidence: high / medium / low
```

## Quality Gate
- 必须说明 binary/core/symbol 是否匹配。
- 必须区分已验证事实、推断和缺失证据。
- 符号不匹配、GDB 不可用或缺共享库时，结论不得超过 `partial`。
- 最终建议必须包含可执行的下一步取证或修复验证。
