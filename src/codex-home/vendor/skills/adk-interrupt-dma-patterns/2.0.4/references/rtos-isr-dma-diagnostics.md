# FreeRTOS ISR／DMA／缓存一致性取证（按需）

## 身份与优先级
记录 CPU/MCU、实际 NVIC 实现的优先级位数、RTOS port、FreeRTOSConfig.h、configPRIO_BITS、configMAX_SYSCALL_INTERRUPT_PRIORITY（及移植层约定）、中断号和 ISR API。CMSIS 使用的逻辑优先级编码与数值越小越紧急的方向须分清，不能将另一芯片或 port 的阈值照搬。

遇 FromISR 断言，先找到断言行、具体 IRQ priority/分组、ISR 是否可调用 RTOS API，再决定是否应修改优先级或交接机制；不允许直接删除 configASSERT。电机 PWM/FOC 这类实时 ISR 按真实 WCET 和 jitter 预算决定是否下沉任务，不机械禁止 ISR 运算。

## DMA 所有权
对所有 DMA buffer/descriptor 明确 CPU owned→device owned→complete→CPU owned，标注 transfer direction、cacheable/non-cacheable、cache-line sharing、alignment、mapping/sync API。volatile 不能保证跨设备一致性、cache flush 或发布顺序。依目标平台使用 cache clean/invalidate、DMA barriers、memory ownership；不能把 Linux dma_map_* API 用在裸机。

异常路径必须覆盖：DMA 读旧数据、overrun/underrun、partial transfer、timeout、cancel/reset、late completion、double-free；证据包括实际源码/编译配置、受控 trace、总线/缓存状态与单变量实验。没有 HIL 只能 needs-runtime-evidence。

来源：https://github.com/FreeRTOS/FreeRTOS-Kernel-Book ; https://arm-software.github.io/CMSIS_6/latest/Core/group__NVIC__gr.html ; https://gcc.gnu.org/onlinedocs/gcc/Volatiles.html ; https://docs.kernel.org/core-api/dma-api-howto.html
