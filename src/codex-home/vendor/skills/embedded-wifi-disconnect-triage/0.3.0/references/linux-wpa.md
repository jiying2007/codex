# Linux / wpa_supplicant 适配

仅确认该后端时加载；接口、路径、命令和网络管理owner以实际部署为准。

- 对齐CTRL-EVENT-CONNECTED/DISCONNECTED、reason、locally_generated、SSID/BSSID和network-id；network-id不是跨启动稳定身份。
- STATUS可能遗漏或保留地址，核对内核接口/路由及地址族，IPv6关注scope、tentative/dadfailed和目标路由；关联、DHCP、DNS和业务成功分别陈述。
- `wpa_state=COMPLETED`只支持该次后端样本中的关联/认证状态完成，不证明地址、网关、DNS、公网或业务可用；附带的SSID也不等于新鲜的端到端连通性结果。
- DNS先区分本机解析接口返回、DNS服务器响应与业务自定义超时日志；只打印“DNS failed”而没有返回码/响应时，不能宣称NXDOMAIN、SERVFAIL或DNS服务器自身故障。记录getaddrinfo或等效接口返回码、resolver配置来源和耗时；接口/路由读取默认只读，主动探测另核网络/设备授权。
- SSID按原始字节和后端编码比较，不trim/截断/折叠大小写；检查响应长度、字段边界、转义、UTF-8字节和parser并发。
- 分开运行时网络列表、持久化配置和缓存。LIST_NETWORKS为空、条目disabled、凭据不可读不是同一状态。
- 核对SAVE_CONFIG结果和实际配置路径、软链接、挂载、权限、update_config条件；连接成功不证明已落盘，不输出完整配置和秘密。
- 部分读取、截断或超过实现容量时，不能按不完整列表删网络或更新整表。SELECT_NETWORK改变其它条目状态时核查保存和失败回滚。
- 存在action worker/控制socket锁才追相应等待；连接timeout不自动覆盖排队、控制往返、扫描和DHCP。
- 分开请求、参数数组和指针所指数据owner；调用方栈地址不因参数数组转移就安全异步存活。
- 按owner完成停止准入、排空调用/回调、worker退出、join或等效确认再销毁；ring-buffer停止不等于线程退出。
- 无网时DNS与组播错误先关联接口、地址、路由，不能仅凭errno或重启有效认定驱动故障。
- 使用预编译库时查实际链接和打包来源；ELF平台可比应用/关键库BuildID/hash，installed、image与OTA分别验证。
