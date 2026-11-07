# 低功耗场景验收

每个场景记录输入覆盖、观测、候选、反证及最小下一步。表中是审查准则，不是已经执行的HIL结果。

| 输入 | 必须区分 | 不得推导 |
| --- | --- | --- |
| sleep请求收到SUCCESS，但无kernel entry | 请求ACK、实际suspend准入和失败回滚 | ACK即已睡眠 |
| TX quiet为零，SDIO计数仍变化 | 流量窗口、驱动事件、MCU/SoC交接 | TX quiet证明总线静默 |
| 第一轮恢复，第二轮只有Sensor发布/Task接收 | 每轮代次、准入、受理、恢复分支、服务终态 | 收到消息即业务已恢复 |
| boot_id变化或uptime归零 | 掉电式交接、冷启动、watchdog和真正resume | 最后wake marker即唯一原因 |
| suspend中途失败后网络/锁未恢复 | 失败阶段、已停止资源及恢复对称性 | 重试可替代清理责任 |
| 日志轮转缺少故障窗口 | covered/partial/missing、各来源时钟 | 其他窗口的完整链回填本次根因 |

源码/Host验证与单次设备smoke、多轮循环、soak分别记录。用户只授权日志分析时不改wake配置、不开关网络、不重启设备。
