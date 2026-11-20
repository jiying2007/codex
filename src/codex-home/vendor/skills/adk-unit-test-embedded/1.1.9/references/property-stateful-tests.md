# 性质与状态序列测试

从契约选边界/错误保持、黄金字节、幂等或状态不变量；roundtrip 成对实现可能同错，expected 不调用被测 helper。沿用 runner，区分边界枚举、性质框架、coverage-guided fuzz；缺工具 `not-run`，不自动安装。

生成合法/边界/截断/畸形输入，核预期拒绝；全过滤或只到 harness 是无效运行。留生成/丢弃/到达 SUT 数量与有效操作，必要时用匹配 binary 的覆盖核关键路径。限定时间/次数/长度/内存，保存 seed/原始输入/序列/build identity。跨轮复位全局/时钟/队列/资源、回收线程。

对 init/submit/cancel/reset/late-completion 用独立模型定义转移/拒绝/owner 不变量，不臆造语义。失败分实现、错误性质、契约歧义或 harness；留原例、删减并重放。仅实际缩减/枚举证明才称最小，否则称可重放反例；修复核反例/变体/合法行为。

## 有界 host 示例

容量 2 FIFO：0=pop，1=push(0)，2=push(1)，空/满拒绝保持内容。Python 枚举长度 0..4；`trace` 模拟 seam，错误版忽略 head，`deque` oracle 不共享环形算法。接项目时替换 seam。存 `stateful.py`，运行 `python3 -I stateful.py`，不受 `PYTHONOPTIMIZE` 影响：

```python
import json
from collections import deque
from itertools import product

def expected(ops):
    q, out = deque(), []
    for op in ops:
        if op == 0:
            out.append(q.popleft() if q else "empty")
        elif len(q) == 2:
            out.append("full")
        else:
            q.append(op - 1)
            out.append("ok")
    return out

def trace(ops, fixed):
    buf, head, count, out = [0, 0], 0, 0, []
    for op in ops:
        if op == 0:
            if count:
                out.append(buf[head])
                head, count = (head + 1) % 2, count - 1
            else:
                out.append("empty")
        elif count == 2:
            out.append("full")
        else:
            buf[(head + count) % 2 if fixed else count] = op - 1
            count += 1
            out.append("ok")
    return out

cases = [ops for n in range(5) for ops in product(range(3), repeat=n)]
assert cases and any(cases), "invalid: no nonempty input"
bad = next(ops for ops in cases if trace(ops, False) != expected(ops))
actual = trace(bad, False)
trace((2, 2, 2, 0), False)  # unrelated prior sequence must not leak state
assert trace(bad, False) == actual
assert all(trace(ops, True) == expected(ops) for ops in cases)
print(json.dumps(dict(cases=len(cases), steps=sum(map(len, cases)),
                     counterexample=bad, actual=actual, expected=expected(bad),
                     replay=trace(bad, False), fixed_pass=len(cases))))
```

预期 121 序列/426 步；`[1,0,2,0]` 最后 pop 应为 1、错误版为 0。按长度枚举证明其在此字母表内最短；正确版全过。未覆盖所有输入/并发调度，host 枚举不计为 fuzz/HIL/板端性能。

方法对照：[Trail of Bits](https://github.com/trailofbits/skills/blob/149d7b21f4067765b82e67029730b42d228ef4b4/plugins/property-based-testing/skills/property-based-testing/SKILL.md)。[Hypothesis](https://hypothesis.readthedocs.io/en/latest/settings.html) 过量过滤可报 health check/Unsatisfiable，不作通过。
