---
name: adk-protocol-stack-integration
description: "用于通信协议栈适配、连接状态机和跨层错误处理的集成设计与回归；不用于纯寄存器布局设计或仅修复孤立格式问题。"
version: 1.0.7
last_updated: 2026-11-20
triggers:
  - "协议栈"
  - "协议集成"
non_triggers:
  - 只改 UI 文案
inputs:
  - 协议规范、链路约束
outputs:
  - 集成步骤与状态机草图
constraints:
  - 先定义错误恢复与超时策略
---

# adk-protocol-stack-integration

## Workflow
1. 核协议版本、时序、容量、保活、重传/异常；定义连接、鉴权、收发、恢复及版本协商/降级。
2. 实现/排查收发时读 `references/transport-boundaries.md`：分帧、部分 I/O、长度/校验、截断和缓冲上限。
3. 按下述预算设计 timeout/retry/backoff/熔断；按问题选物理测量、帧分析、传输或应用回归。

## Execution Target Boundary
区分 Linux 用户态/kernel、RTOS/裸机和离线/仿真；MCU 不默认有 `tcpdump/tshark`。主动采集/注入/配置/板测须核接口、权限、范围，否则用既有 trace、脱敏日志或仿真。DNS、TCP/UDP、TLS、握手、keepalive 分标 `measured|inferred|unknown`，抓包不独证应用根因。

## Commands
离线先核 `PCAP` 来源与 `DISPLAY_FILTER`：
```bash
tshark -n -r "$PCAP" -Y "$DISPLAY_FILTER"
```
获授权采集：核端口/脱敏，时间与包数为预算内正值，`PCAP` 为新路径；失败不消费旧文件：
```bash
tshark -n -i "$IFACE" -f "port $PORT" -a "duration:$CAPTURE_SECONDS" -c "$PACKET_LIMIT" -w "$PCAP" &&
  tshark -n -r "$PCAP" -Y "$DISPLAY_FILTER"
```
留退出码、帧号/时间、匹配包数；坏文件失败，空文件/零包/零匹配即使 exit 0 仍 `partial`。大文件限窗口；`-q` 须配 `-z` 统计。[TShark](https://www.wireshark.org/docs/man-pages/tshark.html)。Scapy 是需依赖的 Python API，不能粘入 Bash，发包仍需授权。

## Retry and timing boundary
- 各层独立 timeout/状态机，参数依据协议/链路/产品预算。有限操作以单调钟算剩余时长，含阶段、尝试、I/O 等待和退避；每阶段取本地 timeout 与剩余值之小，耗尽停止。跨主机传剩余时长或协议 deadline，不传本地单调绝对值；长连接寿命另定。
- 核 SDK/调用层重试，明确责任层、总 attempts（含首次）和嵌套调用量/时延，不关闭协议必要重传。分短暂/永久失败；非幂等 UNKNOWN 先对账。退避/jitter 遵守协议及 Retry-After；超剩余预算结束本轮，不延长 deadline 或缩短强制等待。
- 用实际实现/仿真验正常、短暂故障、永久失败、退避耗尽、嵌套重试、乱序丢包和重连；未执行记 `not-tested`。

交付：State/Compatibility/Timeout-Retry/Recovery、Transport/Framing/Buffer Limits/Partial-I/O、Command/Exit/Raw Evidence/Test Result/Gaps。

协议冲突留证、暂停扩展；重连不稳回最小报文/并发。交付须有已授权抓包/日志/仿真及参数来源；未测值和缺口不算通过。
