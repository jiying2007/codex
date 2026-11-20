---
name: adk-interface-contract-design
description: "用于模块 API、协议消息及生命周期状态转换的接口契约设计与迁移评审；不用于需求未收敛时直接写实现或放行设备动作。"
version: 1.3.9
last_updated: 2026-11-20
triggers:
  - "设计接口"
  - "API设计"
  - "接口契约"
non_triggers:
  - 纯内部重命名
inputs:
  - 调用方与被调方约束
  - 生命周期约束（有状态/异步操作时）
outputs:
  - 接口或生命周期操作契约草案
constraints:
  - 必须明确输入、输出、错误码
  - 机器消费接口声明 strict schema、消费者方言/能力与 refusal handling，拒绝未知字段
  - 受控生命周期须明确唯一 owner、状态/事件/终止语义
  - 工具/handoff 外部副作用须执行前授权并定义恢复重放语义
---

# adk-interface-contract-design

## Goal
模块/嵌入式 HAL/驱动/协议栈契约须可验证，含版本与调用方。

## Prerequisites
- 明确调用链 owner、输入输出源、错误边界及目标内存对齐/字节序。
- 共享操作启动/取消/恢复前确认下述生命周期契约。

## Workflow
1. **接口清单**：请求/响应/错误码/幂等/异常的最小契约。
2. **版本与能力协商**：声明消费者最低需求及提供方兼容方向/窗口；同 major 不保证新能力，版本非 wire/ABI 兼容证据。增量 C 例见 `references/details.md`。
3. **错误码设计规范**：统一空间，检查冲突。
   ```bash
   rg -n "IFACE_ERR_|ERR_" include/ src/ | sort
   rg --no-filename -o "= -[0-9]+" include/ | sort | uniq -d
   ```
   仅检负十进制写法；宏/表达式/别名/其他进制另核，限同命名空间判冲突；零候选不证明无冲突。
4. **异常预算**：超时/限流/重试/降级按目标协议、链路/设备预算及可证伪实验确定，禁通用固定值。
5. **受控生命周期契约**：跨状态/独占资源操作明确下述矩阵、状态可见性/取消/超时/恢复/迟到完成及 generation/op-id 隔离；按需读 `references/lifecycle-operation-contract.md`。
6. **副作用**：按参数/目标在写前授权；拒绝/未知结果/重放对账见 `references/tool-effect-contract.md`。
7. **结构化输出**：固定消费者 dialect/validator/子集及 required fields/enum/refusal handling/parse-failure；拒绝未知字段，同层用 `additionalProperties=false`，组合闭合见 `references/details.md`。
8. **契约用例**：含正常/边界/异常、最低版本及跨 major 的真实验证；跨端还查损坏帧、超时、重复/乱序；缺设备记 `not-tested`。
9. **设计挑战**：高风险公共接口比两种边界的演进成本/验证 seam；单路径写理由。变化才更新既有 glossary/ADR；详见 `references/design-quality-methods.md`。
10. **Spec-to-Code 双向核对**：跨仓共用 `protocol/spec@digest`；按 `references/spec-code-bidirectional.md` 核规格→实现及行为→规格，未知记 `not-checked`。

## Quality Gate
- 上述契约/用例须完整，含兼容迁移及可恢复/不可恢复错误。
- 嵌入式验证结构体大小/对齐（`pahole` 或 `sizeof` 断言）。
- 受控操作须有 owner × state × event × resource × termination × invariant 矩阵及幂等/重试预算/callback/cleanup 并发；缺项禁实现/通过。副作用须绑定目标及对账路径，审批不等于生效。

## Failure Handling
- 兼容策略未经调用方确认：`needs-fix`。
- 错误语义不一致：冻结接口变更，重返设计。
- ABI/线协议对齐冲突：区分内存表示/显式序列化，验证 `sizeof`/`offsetof`、目标非对齐访问/字节序；`packed` 非默认修复。
- 降级须有双方明确支持且满足必需语义/能力/安全约束的交集及依据；无交集/证据不明则拒绝，禁自动回退“最低公共版本”。

## Evidence Template

```md
status: pass | needs-fix | BLOCKED
structured_schema: strict | not_applicable
lifecycle_operation: not_applicable | contract-path
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

状态/owner/终止不明则冻结；不得以最终回调代替超时/取消/迟到完成验证。
