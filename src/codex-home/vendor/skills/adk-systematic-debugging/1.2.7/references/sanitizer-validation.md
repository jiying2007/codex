# Sanitizer 有效性与诊断判读

仅授权隔离测试：核 compiler/version、target ABI、libc/OS、runtime、runner、符号及预算；host 可运行不代表 MCU/ISR/DMA 可插桩。

| 缺陷候选 | 条件性选择 |
|---|---|
| 越界、UAF | ASan；核平台与实际插桩范围 |
| 溢出、非法移位、未对齐等 UB | UBSan；核启用的具体 checks |
| 线程数据竞争 | TSan；核线程模型和平台，单独构建，不与 ASan 混用 |

固定优化/构建身份；插桩不作性能基准。先同配置跑已知缺陷/修复对照确认报告，再跑真实用例。分别留编译/链接、启动、退出码、stderr/报告与输入，不能只看编译成功。缺工具 `not-run`，不支持 `not-applicable`，启动/符号化/超时故障 `inconclusive`；均非无缺陷，不自动安装或关资源上限。

## 可重放 UBSan 对照（host GCC）

隔离目录保存 `overflow.c`；需 GCC/UBSan runtime、Bash、`env -u`。`FIXED` 保留 INT_MAX 输入并避开加法。

```c
#include <limits.h>
volatile int source_value = INT_MAX;
volatile int observed_value;
int main(void) {
#ifdef FIXED
    if (source_value == INT_MAX) return 0;
#endif
    observed_value = source_value + 1;
    return 0;
}
```

```bash
set -euo pipefail
sanitize_flags=(-std=c11 -O1 -g -fsanitize=undefined)
gcc "${sanitize_flags[@]}" overflow.c -o recover
gcc "${sanitize_flags[@]}" -fno-sanitize-recover=undefined overflow.c -o fatal
gcc "${sanitize_flags[@]}" -fno-sanitize-recover=undefined -DFIXED overflow.c -o fixed
for variant in recover fatal fixed; do
    rc=0
    env -u UBSAN_OPTIONS "./$variant" >"$variant.out" 2>"$variant.err" || rc=$?
    printf '%s exit=%s\n' "$variant" "$rc"
done
```

子进程清除 `UBSAN_OPTIONS` 核默认行为：recover 报 signed integer overflow 但 exit 0；fatal 同类报警且非零；fixed 为 0 无诊断。前两者均成功报告程序缺陷，被测程序未通过；缺预期报告查插桩/路径/runtime，不当修复。记录 suppressed/未插桩模块；干净运行只覆盖实际输入，不证明目标无内存/并发/UB。未执行 ASan/TSan 记 `not-run`。

依据：[GCC 14.2](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Instrumentation-Options.html)。方法对照：[Trail of Bits](https://github.com/trailofbits/skills/blob/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/testing-handbook-skills/skills/address-sanitizer/SKILL.md)；独立概括，未导入代码。
