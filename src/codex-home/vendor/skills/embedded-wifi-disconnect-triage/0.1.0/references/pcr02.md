# PCR02 专项入口与诊断边界

适用 PCR02 SSC305 / xcrz_sigmastar_demo。以下是定位入口，不是固定实现承诺。每次使用先确认源码根、独立子仓和实际链接库，再读取项目 AGENTS、模块规则与当前实现。

## 调用链与源码入口

```text
Task/IoT 请求与最终回执
  → SensorWifiService 编排和连接代次
  → api_wifi 状态/回调/扫描/Reset
  → wifimg action worker
  → WPA 控制 socket / supplicant
  → 驱动 / SDIO / 固件
```

| 责任层 | 相对已确认源码根的入口 |
| --- | --- |
| Sensor 编排、扫描、凭据和恢复 | `modules/sensor/wifi/sensor_wifi_service.{cpp,h}` |
| 共享消息线程 | `modules/sensor/main/sensor_entry.cpp` |
| API 状态、回调、扫描和 Reset | `modules/api/src/api_network/api_wifi.c` |
| action 生命周期 | `modules/wifi/wifimanager/api_action/api_action.c` |
| STATUS 解析、目标 SSID 校验和连接 | `modules/wifi/wifimanager/core/src/os/linux/linux_sta.c` |
| 扫描预算与事件等待 | `modules/wifi/wifimanager/core/include/os/linux/scan.h`、`modules/wifi/wifimanager/core/src/os/linux/event.c` |
| 实际产品依赖 | `pcr02/dep.mk` 与本次实际 link command |
| Host 恢复测试 | `tests/wifi_recovery_lifecycle/README.md`、`Makefile` |
| action 生命周期测试 | `tests/wifi_action_lifecycle/action_lifecycle_test.c` |
| 安全类型契约 | `tests/contracts/test_wifi_security_contracts.py` |

先分别核对 modules/wifi、modules/api、modules/sensor 的 Git root/status。父仓的 untracked modules 不能等同于该模块未纳管，父仓检查也不能替代子仓审查。测试入口缺失时重新定位，不从旧目录复制产物。

## 按现象审计的关键边界

- **DHCP 后空 SSID**：先检查当前 `wpa_check_connected_ssid()` 是否已有限重试及 parser 是否改变，再绑定现场库身份。重试不能替代解析器缺陷修复，旧日志不能证明新代码仍有同一缺陷。
- **扫描长等待**：读取实际扫描重试和事件等待常量；只把它们当作节律假设，配合锁/队列/命令/事件阶段证据验证。Connect 参数不必覆盖之前的查询/扫描时间。
- **Reset 预算**：核实每个阶段实际可中断性。若只在阶段间检查预算，应明确无法中断同步 backend，不将名义 30 秒当作绝对结束保证。
- **action 所有权**：追踪消息、参数数组和数组中指向的数据各自由谁拥有、何时转移；参数数组转移不意味着其指向的调用方栈地址也能异步存活。退出失败时保留资源并向上传播。
- **callback teardown**：注销返回 BUSY 时，旧 user data/owner 必须保留直至确认排空。`ring_buff_stop` 等唤醒操作不等于线程退出。
- **公开网络与安全类型**：区分显式 NONE、UNKNOWN、EAP、OWE 及 backend 支持范围；校验在断开当前链路、上电或持久化之前完成。空密码不等于凭据缺失。
- **共享 poller**：配网 callback 如同步等待安全类型扫描，会阻塞串行消息线程并影响音频/其它业务。先测 callback 耗时与排队时间，再决定是否改调度。
- **用户 SOC Sleep**：Wi-Fi/TCPKA 内部异常恢复与用户唤醒、业务 Standby 互斥分别验证。定位失败是在凭据、Wi-Fi、TCPKA re-arm、MCU arm 还是 suspend；不能因出现 re-arm 失败就直接归因 ioctl。

## 身份、现场与验证

检查 `pcr02/dep.mk` 是否仍链接预编译 Wi-Fi 库。重编 modules/wifi 不代表产品依赖已更新；比较库 hash/BuildID、实际 link command、最终 app 和设备 installed。app、image、OTA 分别留证，后编译 app 不自动进入既有包。

supplicant 日志可能跨多次初始化并混有相对秒数和绝对时间。先分启动段，再与 Sensor/API/IoT 对齐。现场包可能附带密码配置，默认只定位必要日志，不复制整个目录进入 skill 或知识正文。

按改动选测试；以下命令仅在已核实源码根、对应文件存在时使用：

```text
rtk git -C modules/wifi status --short
rtk git -C modules/api status --short
rtk git -C modules/sensor status --short
rtk make -C tests/wifi_recovery_lifecycle test
rtk python3 -m unittest tests.contracts.test_wifi_security_contracts -v
```

执行前读取 Makefile 的输出位置与副作用；既有恢复测试采用 Host/mock 和 sanitizer，它不能证明驱动或板级恢复通过。ARM 对象目标按当前 Makefile 选择，不沿用历史测试数量作为通过标准。

项目事实和历史案例通过项目规则指定的 Knowledge Provider 检索，可使用关键词：`WiFi DHCP SSID`、`wifi action lifecycle`、`TCPKA 公开网络 扫描取消`、`配网 扫描 音频阻塞`。返回 reviewing 的方案仅为候选，不能作为当前产品策略或部署事实；不固化 Hub 内部路径、现场文件名、故障时刻或设备端点。

ADB/HIL 的连接分层、设备写授权和恢复基线以项目当前 AGENTS/runbook 为准。无设备时仍可输出源码/日志分析，并明确缺少现场制品绑定与 HIL。
