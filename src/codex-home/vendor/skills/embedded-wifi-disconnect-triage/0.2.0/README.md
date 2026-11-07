# 嵌入式 Wi-Fi 分析与恢复定位

本地 Chronicle 派生 skill。主流程不绑定业务程序、仓库路径、驱动或构建系统；依据实际平台选择适配。

- 通用入口：SKILL.md。
- 多启动、轮转和连续采集证据：references/evidence-checks.md。
- Linux / wpa_supplicant：references/linux-wpa.md。
- PCR02/SigmaStar：references/pcr02.md。

当前具体后端参考覆盖 Linux / wpa_supplicant；其他平台可用通用分诊方法，命令和实现细节需按其实际后端核实，不表示已有完整平台验证。

源资产与启用版本由受管 manifest 管理；不直接修改运行副本。
