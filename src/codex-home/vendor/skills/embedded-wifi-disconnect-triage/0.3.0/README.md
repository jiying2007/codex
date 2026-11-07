# 嵌入式 Wi-Fi 分析与恢复定位

本地 Chronicle 派生的团队内部复用 skill。主流程不绑定业务程序、仓库路径、驱动或构建系统；依据实际平台选择适配。

Origin: local-chronicle-derived
Lifecycle: iterative-local
Version: 0.3.0

- 通用入口：SKILL.md。
- 多启动、轮转和连续采集证据：references/evidence-checks.md。
- Linux / wpa_supplicant：references/linux-wpa.md。
- PCR02/SigmaStar：references/pcr02.md。
- 维护与语义验收：references/scenario-acceptance.md。

当前具体后端参考覆盖 Linux / wpa_supplicant；其他平台可用通用分诊方法，命令和实现细节需按其实际后端核实，不表示已有完整平台验证。

源资产与启用版本由受管 manifest 管理；不直接修改运行副本。

LICENSE允许授权用户的团队内部使用、复制、修改及向团队受管Codex环境分发，不授予对外分发或开源许可。维护身份local表示来源，不代表团队采用或硬件覆盖。发布还需资产验证和独立审查通过；成员安装/采用、硬件平台覆盖和产品问题修复另取证，不由本机技能检查推导。只读有界日志仍按目标环境离线日志入口路由，必要时加载本技能参考；纯服务端/DNS故障不强制进入Wi-Fi专项。
