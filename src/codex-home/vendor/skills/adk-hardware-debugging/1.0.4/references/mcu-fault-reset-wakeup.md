# MCU HardFault、随机复位与低功耗唤醒（按需诊断）

## 确认硬件身份
先记录 MCU、内核、stepping、board revision、SDK/RTOS port、bootloader、固件 hash、编译 ELF/map 与电源/时钟条件。GD32L235 为 Cortex-M23，MM32SPIN023C 为 Cortex-M0，HC32F072 为 Cortex-M0+；实际寄存器与勘误以对应厂商手册/头文件为准，禁止套用其他型号的 MMIO 地址。

## 异常／随机复位
1. 捕捉最早复位源（watchdog、brownout、software、external/power）、电压波形和故障时间线；读取复位标记前核对 read-clear、清除顺序与持久性。
2. 记录 PC/LR/SP、栈帧、异常号、MSP/PSP 与有效符号的精确 ELF；检查栈越界、NVIC、ISR 负载、时钟与 DMA/cache/内存所有权。
3. Cortex-M0/M0+ 不具有 M3/M4 那套完整的 CFSR/HFSR/BFAR 可配置 fault status。M23 能力也按具体实现核实；缺寄存器不可补猜。
4. 调试器 attach/halt、watchdog 复位或写寄存器可能改变被测状态，必须先标效果类别、授权、恢复和验证。

## 低功耗唤醒
按真实 STOP/STANDBY/SLEEP 类型检查 wake source、RTC、EXTI、GPIO、PWR/clock/reset domain、保留内存、外设上电时序与电流曲线。单变量记录每次唤醒延迟、成功率和失败复位源；无板端复现不得声称修复。

## 证据与状态
状态只能为 confirmed（数据／符号／手册直接支持）、inferred（有反例及下一步取证）、needs-runtime-evidence（缺手册/板卡/trace）。默认只读，严禁把“读不出寄存器”直接当作硬件根因。

参考：
- https://arm-software.github.io/CMSIS_6/latest/Core/regMap_pg.html
- https://www.gigadevice.com/product/mcu/low-power-consumption-mcus/gd32l23x-series/gd32l235
- https://www.mindmotion.com.cn/products/mm32mcu/mm32spin/mm32spin_driver_mcu/mm32spin023c/
- https://www.xhsc.com.cn/product/1272.html
