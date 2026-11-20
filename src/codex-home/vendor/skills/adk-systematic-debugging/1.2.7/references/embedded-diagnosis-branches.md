# 嵌入式真实故障跨层分流（按需）

本参考只帮助选择下一证据，不是项目默认配置，也不授权设备读写。始终固定 SoC/MCU、board、固件、内核/RTOS、toolchain、负载及第一条异常。

## UBI／UBIFS／SquashFS
SquashFS 为只读压缩文件系统；只读或 df 100% 本身不足以推断坏块、空间不足或“需要迁移”。先核 /proc/mounts、/proc/mtd、bootargs、实际 MTD/UBI/volume，记录 dmesg 首次 UBIFS/I/O/ECC/ENOSPC 错误与供电、并发写时间线。意外 UBIFS 只读要区分 I/O、错误恢复、空间、掉电、配置；缺完整证据不归因“并发写本身”。不用 ext4 fsck、盲格式化或全 UBI 擦除试错；只有明确更改 layout 才进入 storage-layout-migration。

## Buildroot／Autotools／CMake／Yocto
先读取真实 package infra/Makefile/configure.ac/CMakeLists/toolchain/sysroot。Buildroot 可构建 Autotools、CMake 或 generic package；不能把“交叉编译”直接等同 CMake。aclocal/automake/Autoconf 缺失先检查 host tool、版本与环境；重现同一 source+config+compiler。区分 compile-only、host-unit、emulator、board-runner 结果。

## Wi-Fi／DNS／MQTT
按时间线逐层排：association/signal → DHCP/IP → route/gateway → DHCP 生成的 resolver → DNS query → TCP → TLS → MQTT CONNECT/KeepAlive。Wi-Fi 已连接不代表 DNS 正常；分清 NXDOMAIN、timeout、网络不通、TLS/keepalive。公网 IP/DNS 对照属于主动网络检查，先批准；不要直接把修改 resolv.conf 或写死公网 DNS 当最终方案，DHCP hook 可覆盖。

## SPI／QSPI 圆屏
分别核 power/reset/背光、strap 接口模式、pinmux/CS/CLK/D-C、single/quad lane、SPI mode、命令与GRAM窗口、实际 init 序列和波形。背光亮且初始化无返回错误不证明面板收包，SPI 没有底层 ACK；不要在读写效果未确认时盲改寄存器。单线/四线/飞线需冻结同一硬件条件比较。

## BLDC/FOC 低速与回充过流
冻结电流/速度环、保护阈值由来、采样与PWM时序、堵转/负载/温升、保护码与重复次数。区分真实过流、采样干扰、控制积分、回充机械接触。不能为获得“通过”直接抬高保护阈值；实际运动测试需独立安全工况/停止条件。

结论记录：symptom、first failure、competing hypotheses、excluded hypotheses、single-variable test、observed、confidence、next safe probe、raw path、required authority。没有现场数据写 needs-runtime-evidence。

参考：https://docs.kernel.org/filesystems/ubifs.html ; https://docs.kernel.org/filesystems/squashfs.html ; https://github.com/buildroot/buildroot/blob/master/package/busybox/udhcpc.script ; https://docs.kernel.org/spi/spidev.html
