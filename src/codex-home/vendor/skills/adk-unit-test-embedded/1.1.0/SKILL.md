---
name: adk-unit-test-embedded
description: 嵌入式单元测试策略与样例
version: 1.1.0
last_updated: 2026-08-30
triggers:
  - "单元测试"
  - "写测试"
  - "测试用例"
non_triggers:
  - 纯硬件连线问题
inputs:
  - 模块接口、边界条件
outputs:
  - 单测清单与断言策略
constraints:
  - 优先覆盖边界与错误路径
---

# adk-unit-test-embedded

## Goal
- 为嵌入式模块建立高价值、低维护成本的单元测试。

## Prerequisites
- 明确模块输入输出、依赖替身（mock/stub）策略。
- 定义最小覆盖目标（关键路径与错误路径）。
- 需要跨板级、SIL/HIL、boot、OTA 或现场层次时使用 `references/embedded-tdd-matrix.md`。

## Workflow
1. 提炼可测单元：隔离外设依赖与全局状态。
2. 设计用例：正常、边界、异常、时序四类。
3. 编写断言：重点验证状态变化和错误处理。
4. 构建回归集：把历史缺陷固化为回归测试。
5. 执行与评估：统计通过率与失败根因。

## Commands
```bash
<unit-test-cmd> --module <module_name>
<coverage-cmd> --module <module_name>
# Unity 框架
ceedling test:<module_name>
ceedling gcov:<module_name>
# CMock 自动生成 Mock
ceedling module:create<module_name>
# 覆盖率报告
gcovr --root . --filter src/ --xml -o coverage.xml
lcov --capture --directory build --output-file coverage.info
genhtml coverage.info --output-directory coverage_html
```

## Unity/CMock 框架速查
```c
// Unity 常用断言
TEST_ASSERT_EQUAL_INT(expected, actual);
TEST_ASSERT_EQUAL_STRING(expected, actual);
TEST_ASSERT_TRUE(condition);
TEST_ASSERT_NULL(pointer);
TEST_ASSERT_EQUAL_MEMORY(expected, actual, len);
```

## 测试覆盖率策略
| 覆盖类型 | 目标 | 工具 |
|----------|------|------|
| 行覆盖率 | ≥80% | gcov / lcov |
| 分支覆盖率 | ≥70% | gcov -b |
| 函数覆盖率 | 100%（公开 API）| lcov |
| MC/DC | 安全关键模块 | BullseyeCoverage |

## Evidence Template
```md
- Test Scope:
- Case Matrix:
- Assertion Strategy:
- Coverage Snapshot:
- Regression Cases Added:
```

## Failure Handling
- 测试不稳定时先排查时间依赖和全局共享状态。
- 覆盖率提升导致噪声时，优先保留关键路径测试。

## Quality Gate
- 必须覆盖至少 1 条边界与 1 条错误路径。
- 新增缺陷修复必须附对应回归用例。
- 测试结果需可复现且可追溯到模块版本。

---

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "硬件相关代码没法单元测试" | HAL mock 和 SIL 桩可以覆盖绝大多数逻辑 | 按 SKILL.md 分层策略，业务逻辑与硬件解耦后分别测试 |
| "跑过集成测试就够了" | 集成测试无法精确定位模块内部缺陷 | 必须覆盖边界和错误路径的单元级验证 |
| "改动很小不需要补测试" | 小改动也可能破坏隐含的不变量 | 新增/修改代码必须附对应回归用例 |
