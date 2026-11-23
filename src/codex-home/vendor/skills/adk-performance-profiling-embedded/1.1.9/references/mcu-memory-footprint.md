# 资源与运行对象实测

## 运行对象（装载/分派相关诊断）
核实际binary/共享库/dispatch；源码/产物hash和测试数不证明跑到目标kernel。只读观察已授权Linux PID：

```sh
# profile-object-snapshot
readlink -- "/proc/${profile_pid:?}/exe" &&
  rg -F -- "${profile_object:?}" "/proc/$profile_pid/maps"
```

核完整路径、PID/starttime及前后变化；[maps](https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html)只是映射。退出/exec、(deleted)、匿名/JIT、转义/容器路径有歧义，不以同名文件hash/build-id代表加载内容；无匹配是未观察到，无权限记unavailable，不提权。再用已有符号采样/计数核实际ISA、精度、线程/模型分支；插桩、注入、换库/设备配置仍需授权。MCU核固件/上板记录和trace，host不替代板端。
温漂难分时加不受候选影响的配置作对照；同向漂移仅支持环境假设，不排除混杂，不强制加开关/框架。

## 资源与栈
冻结芯片/链接布局、toolchain/flags、源/配置/ELF hash、map及上板限制；构建失败blocked。同工具链以size -A、nm --print-size --size-sort、objdump/map、-fstack-usage核段/alignment/Flash初始化副本/DMA/uncached/retention；stack/heap reserve与RTOS high-water分开。

`.su`单位bytes：`static`为固定frame，`dynamic,bounded`为该函数上界，`dynamic`只给有界部分；不自动包含调用链。按真实调用图/反汇编核同时存活frame，不能用最大frame或全函数之和作任务峰值。递归、间接调用、VLA/alloca、库/汇编、优化/LTO、ABI未定保留unknown；按port区分任务/IRQ栈，计嵌套、异常、RTOS context/FPU。
high-water仅覆盖观测负载，核API/port、单位/扰动。FreeRTOS `uxTaskGetStackHighWaterMark`是启动以来最小剩余words，按`StackType_t`换算；vendor另核。Zephyr thread analyzer不证明未经历路径；余量非最坏上界，未上板`not-measured`。

`stack.c`仅作host GCC x86-64反例：

```c
#include <stddef.h>
__attribute__((noinline)) int leaf(int x) {
    volatile unsigned char bytes[256];
    bytes[0] = x; return bytes[0];
}
__attribute__((noinline)) int caller(int x) {
    volatile unsigned char bytes[384];
    bytes[0] = x;
    int result = leaf(x);
    return bytes[0] + result;
}
__attribute__((noinline)) int dynamic_frame(size_t n) {
    if (n == 0 || n > 4096) return 0;
    volatile unsigned char bytes[n];
    bytes[0] = 1; return bytes[0];
}
```

```bash
gcc -std=c11 -O0 -fstack-usage -fno-omit-frame-pointer -mno-red-zone -c stack.c -o stack.o
```

核新stack.su：caller调leaf时数组仍存活，dynamic_frame不含完整VLA。缺产物先核支持；-mno-red-zone仅x86-64。未测dynamic,bounded、IRQ/真实high-water。

## 优化与资产复用
授权内量化const/rodata、buffer、成员布局、section GC、libc/优化级别；不以共享static破坏可重入性，不擅移DMA/cache line、保留区/向量表；核packed非对齐、错误恢复。交付build identity、scope、段大小/峰值和重复测量；复验功能、latency/jitter、热/功耗及回滚，缺板端记needs-runtime-evidence。
KWS/音频复用先核可信清单/摘要、来源/许可、采样/声道、特征/量化及target profile；匹配才复用录音/特征/模型/ELF/回执，只重做stale/unverified部分。复用不证明新准确率/资源/时延。

## KWS／音频比较
冻结标签、说话人/场景划分、噪声、采样/分帧/特征、量化校准来源、模型与阈值；同录音及派生片段不能跨训练/验证/测试。验证集选阈值，测试集只作冻结后的最终比较。
剪辑分类给目标与unknown/silence混淆；流式监听使用各候选在验证集冻结的阈值/后处理，按同误唤醒预算或工作点比较误唤醒次数/负音频时长、漏检/延迟。不同分数尺度不强用同数值阈值，剪辑准确率不替代流式效果。共享输入核host/target前端、量化、后处理输出及容差，再测板端Flash/RAM、时延/功耗。仅合成/host数据须标覆盖，不启动未授权训练/服务。

参考：[size](https://sourceware.org/binutils/docs/binutils/size.html)、[GCC .su](https://gcc.gnu.org/onlinedocs/gcc/Developer-Options.html)、[FreeRTOS](https://github.com/FreeRTOS/FreeRTOS-Kernel/blob/ca759444e9ca59cfa3a9faa6cb8b49e0772ca520/include/task.h)、[Zephyr](https://docs.zephyrproject.org/latest/services/debugging/thread-analyzer.html)、[Speech Commands](https://www.tensorflow.org/datasets/catalog/speech_commands)。
