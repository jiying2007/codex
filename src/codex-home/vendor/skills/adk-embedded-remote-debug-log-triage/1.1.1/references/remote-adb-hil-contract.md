# Remote ADB/HIL Detailed Contract

## Health Layers

| Layer | Evidence | Success | Failure boundary |
|---|---|---|---|
| host route | route/neighbor | 有合理 route | 只说明 host/network 可疑 |
| network hint | 单次 ping | 可作旁证 | 失败不跳过 transport |
| transport | ADB/SSH/serial/GDB 状态 | 通道协议确认 ready | 不推断 remote shell/app |
| remote shell | heartbeat、boot_id、uptime | 系统命令按独立 timeout 返回 | 区分 adbd/系统负载 |
| app/diag | PID、health、diag reply | 按业务 timeout 返回 | 不覆盖 transport/shell 结果 |

ADB 失败语义必须包括 `offline`、`unauthorized`、`missing`、`No route to host`、connection refused、timeout。禁止 `ping && adb connect`；禁止只读取退出码。

## Timeout and Retry

- network probe：短 timeout，只作提示；
- transport：独立 connect/status timeout；
- remote shell：比 transport 更长；
- app/diag：按业务耗时单独预算；
- retry budget：默认 1，扩大不得超过 3；
- stop condition：budget 用尽或出现明确不可恢复状态；
- circuit breaker：停止所有设备写操作和 HIL 扩大。

## Recovery/Deploy Preflight

设备恢复后按顺序读取：

1. boot_id/uptime/reset 线索；
2. 目标 PID/状态；
3. core/fatal dmesg；
4. installed size/hash/BuildID；
5. backup/rollback anchor；
6. watchdog、auto-standby、supervisor、其他 mutator；
7. transport/shell/app 时延。

设备恢复不等于授权部署。进入写阶段前必须另由 `adk-artifact-gating` 核对 source、candidate、staged、installed、image/OTA 等不同制品阶段。

## HIL Expansion

| Stage | Minimum evidence | Exit gate |
|---|---|---|
| single smoke | 每个目标模式/拓扑一次 | 状态、首输出、无 fatal |
| short cycle | 5～10 次 | 无 core/泄漏/身份漂移；长尾可接受 |
| long stress | 目标循环数和分位数 | 无累积错误或资源趋势 |
| soak | 长稳、资源、功耗、consumer | 达到产品时长和健康阈值 |
| restore | 正常 profile、关闭临时 diag | transport/shell/app/identity healthy |

任一失联、core、fatal log、状态泄漏、身份漂移、输出停滞或 restore 失败立即停止。watchdog/standby/其他控制面未隔离时标为 `confounded`。

## Evidence Template

```md
- Device Context:
  - model / board_rev / firmware / image / commit:
  - access_channel / endpoint_source:
  - readonly_boundary / mutation_authority:
- Reachability:
  | Layer | Probe | Timeout | Result | Elapsed | Evidence |
  |---|---|---|---|---|---|
- Artifact Identity:
  | Stage | Path/Class | Size | Hash | BuildID | Status |
  |---|---|---|---|---|---|
- Timeline:
  | Phase | Marker | Evidence | Anomaly | Confidence |
  |---|---|---|---|---|
- Mutators:
  | Watchdog/Standby/Supervisor | State | Isolated | Evidence |
  |---|---|---|---|
- Hypothesis Matrix:
  | # | Hypothesis | Evidence | Probe | Result |
  |---|---|---|---|---|
- HIL Stage: single | short | long | soak | restore
- Circuit Breaker:
- Evidence Bundle / SHA256:
- Gate Result: stable | degraded | blocked | needs-fix | unsafe-to-release
- Next Action / Residual Risk:
```

raw log/core/binary 不复制进长期正文；长期条目只保存脱敏摘要、原始证据引用和 SHA256。
