# SoC＋多 MCU OTA 部分成功恢复矩阵（按需）

设计和证据参考，不执行 publish、flash、erase、OTA apply。

## 固定组件身份
逐项列 SoC boot/rootfs、主板 MCU、电机 MCU、充电桩 MCU（按真实项目增删）：board revision、当前/候选固件版本、artifact SHA-256、签名、协议 ABI、活动分区/region、存储与最后健康制品、恢复方法。不可假设所有 MCU 有 A/B slot 或支持 OTA。

## 阶段与失败状态
1. preflight：逐组件核对目标身份、依赖、协议版本兼容窗口、写权限、备份与恢复。
2. stage：制品校验与待激活状态；不能安全 stage 的单 bank MCU 必须具备已验证救援路径，否则 BLOCKED。
3. activate：按真实协议依赖确定顺序，每一步原子记录 operation id、component 状态与后置状态，未知结果先对账不盲重试。
4. health/commit：SoC boot、MCU handshake、运动安全、回充/充电通信和设备诊断达标后才整体确认；进入 shell 或单件 hash 成功不是整机成功。
5. 逐案覆盖：SoC 已新但 MCU 旧、MCU 已新但 SoC 回滚、任意组件 flash 失败、升级中断/断电、重复升级、部分组件取消/回滚失败及工厂恢复。
6. 单设备真实回执≠批量授权；publish 与 device write 各自独立审批。

输出：matrix(old/new) 、compatibility、component receipts、rollback anchor、partial-success recovery、data preservation、postcondition、stop、operator authorization、known gaps。

参考：https://www.rfc-editor.org/rfc/rfc9124.html ; https://rauc.readthedocs.io/en/latest/using.html ; https://docs.u-boot-project.org/en/latest/api/bootcount.html
