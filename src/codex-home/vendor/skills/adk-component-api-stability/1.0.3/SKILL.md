---
name: adk-component-api-stability
description: "用于组件 API 演进时检查调用方、兼容边界、迁移与回滚证据；不用于未经设计直接大范围改签名或纯格式修改。"
version: 1.0.3
last_updated: 2026-11-20
triggers:
  - "API稳定性"
  - "组件API"
  - "接口兼容"
non_triggers:
  - 私有一次性脚本
inputs:
  - 当前 API、调用方清单
outputs:
  - 兼容性评估与演进策略
constraints:
  - 破坏性变更必须附迁移路径
---

# adk-component-api-stability

## Goal
- 建立 API 稳定性基线，控制嵌入式 HAL/BSP/协议栈的破坏性变更风险。
- 分别验证源码 API、二进制 ABI 与运行行为，结论限定于真实消费者和目标。

## Prerequisites
- 收集 API 使用方清单与版本分布，以及新旧源码/制品、公开头文件和历史兼容问题。
- 锁定目标架构、toolchain/ABI flags、shared/static library、header-only 或 firmware 接口类型。
- 确认是否承诺旧二进制兼容，以及类型分析工具和 host/emulator/board runner；无执行后端时只做可完成的静态分析。

## Workflow
1. **盘点契约与消费者**：按 stable/experimental/deprecated 分类公开函数、类型、宏、回调和数据格式，找实际调用方；符号/正则扫描只是入口，不能覆盖宏、内联与动态调用。
2. **源码 API**：用旧消费者源码对新头文件和新实现构建，核签名、宏、类型、错误码及编译条件；按项目真实 toolchain/target 执行，不默认宿主 gcc。
3. **二进制 ABI**：仅对有二进制兼容承诺的接口检查。核架构、调用约定、布局、导出符号/版本和 ABI flags；ELF 类型比较先确认匹配的 DWARF/CTF/BTF 等信息。`nm` 或缺类型信息的报告只能说明符号层差异。
4. **旧二进制验证**：保留旧消费者 executable/object 的原始字节；动态库场景在隔离环境替换新库，静态库场景用旧 object 链接新 archive。只在匹配的 host/emulator/board runner 上运行，不把重编消费者成功当作旧二进制兼容。缺后端记 compile-only/not-run。
5. **行为兼容**：复用旧契约的正常、边界、错误和生命周期用例；分别记录 API 构建、ABI 比较与运行结果。失败保留原始退出码，工具错误不能记为兼容通过。
6. **演进与交付**：按消费者版本及项目承诺确定 SemVer、弃用窗口、迁移和回滚路径；输出验证范围、破坏性变更和缺口。本 Skill 给发布建议，不自行发布或通知外部人员。

## Commands
仅在已授权、真实目标使用对应工具时采用；从项目构建/测试配置和已核验的帮助中选择完整定向命令，确认真实 runner，不拼接假定的通用筛选参数：
```bash
rg -n "public|export|deprecated|DEPRECATED|VERSION" <component_path>
# ELF shared library 示例；需匹配的类型调试信息
abidiff libcomponent_old.so libcomponent_new.so
# 符号检查只提供局部证据，不证明布局/调用约定兼容
nm -D --defined-only libcomponent.so
<reviewed-compatibility-command>
```

以下仅为已确认 native GCC 工程的**源码兼容**示例；库放在消费者之后，运行时库查找按项目隔离配置：
```bash
set -euo pipefail
gcc -I include/ tests/compat_v1.c -L . -lcomponent -o compat_test_v1
if ./compat_test_v1; then
  echo "source compatibility case passed"
else
  compat_status=$?
  echo "compatibility case failed: $compat_status" >&2
  exit "$compat_status"
fi
```
`abidiff` 的非零状态含工具错误、ABI 变化等位标志，按实际版本解释；不得把所有非零笼统归为 breaking，也不能用 `|| echo` 吞掉失败。参考：https://sourceware.org/libabigail/manual/abidiff.html 。

## Evidence Template
```md
- Target / Toolchain / Old-New Artifacts:
- API Inventory: stable / experimental / deprecated + consumers
- Source API / Binary ABI / Behavior Result: pass | fail | partial | not-run | not-applicable
- ABI Differences and Type Information Coverage:
- Breaking Changes and Migration:
- Deprecation Window:
- Consumer Impact:
- Compatibility Tests: consumer/artifact/runner + exit code + log link
- Rollback / Known Gaps:
```

## Failure Handling
- 调用方影响无法评估时记 `needs-fix`，补使用证据，不猜测无消费者。
- 未声明的 breaking change 阻断发布建议，先补迁移方案。
- ABI 工具或类型信息不可用时可比较符号表，但 ABI 结论保持 `partial`；补旧 object/executable 与目标验证。
- 废弃 API 仍有活跃调用方时调整迁移/弃用安排；通知内容和收件人交给已有授权流程。

## Quality Gate
- 区分行为变更与签名/布局变更，给出真实调用方影响和迁移路径。
- 源码重编通过、符号名不变和 host 测试通过均不能替代所承诺的目标 ABI 验证。
- 兼容回归可追溯到命令、输入制品和报告；ABI 检查零未声明 breaking change，缺口不能算通过。
- 版本遵循 SemVer；发布与设备操作仍由各自授权流程执行。

## 健壮性规范
- 执行前核输入、工具、目标与权限；不把本 Skill 当作构建、设备或发布的新授权源。
- 超时按构建规模、工具与 runner 预算；仅重试已判定的瞬时工具故障，不重跑兼容失败刷绿。
- 独立检查可继续，失败不隐藏；记录命令、原始退出码、耗时和日志。
