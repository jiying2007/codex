# Session Wrap - Core 排障与 BusyBox 工具增强

## 会话范围
- 时间: 2026-05-15
- 仓库: xcrz_sigmastar_demo
- 目标: 连续排查多份 core，完善离线 gdb 与 BusyBox 现场排障工具链

## 已完成
1. core 分析能力与流程
- 使用 `prog_pcr02.debug.full` 对多个 core 做 `verify + fastpass + deeppass`。
- 明确 `core-AgoraRTC-913-7759` 为 `SIGBUS`，PC 落在无效代码区特征（符号不足时）。
- 明确 `core-sensor_in0-914-416` 为 `SIGBUS`，落在 `vl53l8x/platform.c::_CopyBytes`，调用链来自 TOF init 固件写入。
- 明确 `core-prog_pcr02-913-2235` 为 `SIGBUS`，落在 `comm::Subscribe::onSensorAudioInfo(...)` 入口。

2. tools/debug 脚本修复与增强
- `match-build-artifact.sh`
  - 改为优先读取 core 内 `execfn` 匹配，修复 `core-AgoraRTC-*` 误匹配问题。
- `verify-core-match.sh`
  - 改为低噪音摘要输出，完整 gdb 输出落盘。
  - 新增 core execfn 与 bin_name 一致性提示。
- `gdb-core-fastpass.sh` / `gdb-core-deeppass.sh`
  - 新增 `--sysroot` 与 `--solib-search-path` 参数，提升离线符号化能力。

3. BusyBox 在线排障工具落地
- 新增 `tools/debug/busybox-kernel-io-watch.sh`:
  - BusyBox 兼容（不依赖 `dmesg -w`）
  - 周期轮询 `dmesg -c` + 线程级 `/proc/<pid>/task/*/io` 增量 TopN
  - 命中关键字自动快照（proc/thread/core 配置/dmesg tail）
  - 自动打包快照 `tar.gz` 到 `/tmp`（默认开启）
  - 支持快照冷却与数量上限，避免刷盘
- 更新 `tools/debug/README.md` 用法

## 关键结论
- 当前随机重启与多线程随机 SIGBUS 模式，更偏向底层存储/UBIFS 不稳定触发的系统级异常，而非单个业务模块稳定缺陷。
- 代码侧崩点已捕获，但多处存在 `corrupt stack` 与随机线程崩溃特征，应继续用“内核日志 + I/O 并发 + core 时间线”联合取证。

## 验证证据
- 脚本语法检查: `sh -n tools/debug/*.sh`（新增脚本通过）
- 新脚本帮助输出正常
- `busybox-kernel-io-watch.sh` 短时 smoke run 正常退出

## 风险与未决
- 目标机共享库与主机路径不全时，某些 core 仍有符号缺失，建议补齐 `/customer/lib`、`/lib`、`/usr/lib` 到本地 sysroot。
- UBIFS 异常尚未完成硬件层证据闭环（坏块/ECC 连续统计）。

## 下一步（Top 3）
1. 在设备运行 `busybox-kernel-io-watch.sh` 增强版，采集命中快照包（/tmp）。
2. 对照 core 时间点检查 `UBIFS/ubi/mtd` 日志是否先于进程崩溃。
3. 若需要，给 `onSensorAudioInfo` 与 TOF init 加仅诊断不改行为的入口防御日志，进一步区分“数据问题”与“存储页问题”。

## 关键产物路径
- fastpass/deeppass/verify 输出: `out/arm/app/gdb-*`
- BusyBox 工具: `tools/debug/busybox-kernel-io-watch.sh`
- 文档: `tools/debug/README.md`
