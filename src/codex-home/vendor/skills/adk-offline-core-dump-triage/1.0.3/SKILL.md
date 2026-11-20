---
name: adk-offline-core-dump-triage
description: "用于离线分析嵌入式 Linux core dump，并对 binary、BuildID、符号与 GDB 匹配留证；不用于无符号时编造可信 backtrace 或操作在线设备。"
version: 1.0.3
last_updated: 2026-11-20
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
离线定位崩溃，先核制品与符号匹配，再区分 crash site、可能根因和缺失证据。

## Prerequisites
定位 core、候选 executable、目标架构和 GDB；收集符号、rootfs/libs、日志及版本线索。

## Workflow
1. 校验匹配：时间、路径、banner、源 commit 只定位候选；用制品摘要/BuildID、部署清单、core 映射及同次采集的 binary/libs 证明关联。core 未必包含各映像 BuildID；缺关联或不匹配记 `partial`，同源 commit 不能替代二进制匹配。
2. 校验工具：运行指定 GDB 的 `--version` 或最小加载；缺宿主依赖时停止源码级归因。
3. 先配置目标 `sysroot`、必要的 `solib-search-path` 和源码映射，再加载 executable/core；逐库核版本与符号，不能误用宿主库或自动信任旁置脚本。线程辅助库/pretty-printer 仅加载已核验的匹配文件。
4. 用 batch 命令采集文件、库、线程栈、崩溃线程寄存器和有限对象状态，保留 stderr/退出码；缺栈、优化值、不可展开帧单列，exit 0 不证明匹配或根因。
5. 只对匹配帧分析源码与生命周期，区分 crash site、trigger、likely root cause、blocked evidence；给出补库/符号、最小日志或复现等下一步取证。

## Commands
变量设为真实路径，日志留在受控位置。GDB 不可用记 unavailable；安装或在线设备操作另需相应授权：
```bash
file "$core_file" "$matched_binary"
readelf -n "$matched_binary"
readelf -n "$core_file"
"$target_gdb" --version
"$target_gdb" -nx --batch -iex 'set auto-load off' \
  -iex "set sysroot $target_rootfs" "$matched_binary" "$core_file" \
  -ex 'info files' -ex 'info sharedlibrary' -ex 'info threads' \
  -ex 'thread apply all bt' -ex 'info registers'
```
`set auto-load off` 也禁用线程辅助库自动加载；若影响解析，记录缺口，仅恢复已核验的匹配库。依据：[batch](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Mode-Options.html)、[auto-loading](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Auto_002dloading.html)。

## Evidence Template
```md
- Artifacts:
- Match Check:
  - binary_build_id:
  - core_exe:
  - symbols:
  - sysroot/libs:
- Match Evidence vs Candidate-only Clues:
- GDB Status:
- Trusted Frames:
- Crash Site:
- Likely Root Cause:
- Blocked Evidence:
- Next Probes:
- Confidence: high / medium / low
```

## Quality Gate
匹配、工具或库证据不全时最多 `partial`；事实、推断、缺口分开，下一步须可执行。
