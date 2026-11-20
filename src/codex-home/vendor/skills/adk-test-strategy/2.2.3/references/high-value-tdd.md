# 高价值 TDD 与测试 seam（按需）

实现须已有授权；本策略只设计/核对，不授予产品代码或测试文件写权限。

- **测试的是外部能力**：从公开接口或用户可见场景断言行为，而非 private 方法、内部函数调用次数或实现顺序。例：重试后状态正确、取消后不会生效，优于“调用了 mock 三次”。
- **Red**：先运行最小测试，确认失败因缺失的功能/不满足的行为而非编译报错、依赖未安装或断言拼写错误；记命令、退出码和关键观察。
- **Green**：只改最少产品代码，使该测试通过；同时跑关键原有通过用例，避免让历史行为变红。
- **Refactor**：在测试保护下清理重复，确保同样的断言仍然绿；不在重构阶段扩大需求或破坏 public seam。
- **Mock 边界**：可替代硬件访问、时钟、网络等不可控依赖，但不能把 mock 返回值或实现内部调用当作核心行为正确性。比较真实集成边界时用更高一级测试。
- **嵌入式注意**：有 ISR/异步、寄存器/时序、功耗或设备响应时，host unit 只能证明模拟环境，不得替代 SIL/HIL/真机证据；证据层级分别标明。

失败转换：红灯意外通过 → 测试未覆盖缺失行为；绿灯偶发 → 回到最短反馈回路；测试必须依赖实现细节 → 改在更稳定的公开 seam。

## 独立 expected 与错误变体

expected 来自需求、手算常量或独立夹具，不调用被测实现/同一 helper 自证。新增/可疑测试须指出具体错误（分支、遗漏副作用、边界偏移），运行隔离错误变体并保留正确/合法边界通过；不改真实数据，无需全仓 mutation 扫描。

契约要求查询参数的 `&` 编码。临时保存为 `oracle.py`；`python3 oracle.py mirror broken` 会漏报，`independent broken` 应退出 1，`independent good` 应全部通过：

<!-- adk-example: independent-oracle -->
```python
import json
import sys
from urllib.parse import quote

mode, implementation = sys.argv[1:]
def encode(value):
    return quote(value, safe="&" if implementation == "broken" else "")

def query(value):
    return "tag=" + encode(value)

cases = [("", "tag="), ("plain", "tag=plain"), ("a&b c", "tag=a%26b%20c")]
failed = False
for value, literal in cases:
    expected = "tag=" + encode(value) if mode == "mirror" else literal
    actual = query(value)
    passed = actual == expected
    print(json.dumps({"input": value, "expected": expected, "actual": actual, "pass": passed}))
    failed |= not passed
raise SystemExit(int(failed))
```

## 新建、修改或可疑 checker

仅这些情况校准；普通检查不重复增加步骤。用实际命令链、同 schema/阈值/范围核对：正常/阈值内通过，已知违规失败，工具错误/缺字段/未知级别/不完整或空扫描均无效或失败。exit 0 可能只表示报告生成，不能等同业务 PASS。

记录 checker 身份/配置、预期/实际结果、命令/原报告；同快照配置且适用的校准可复用，身份/schema/阈值/范围改变后重校准。一律拒绝不算可靠；报告夹具只验证判读，真实缺陷检出另需目标环境证据。
