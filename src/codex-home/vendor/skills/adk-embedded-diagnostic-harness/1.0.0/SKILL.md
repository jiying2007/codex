---
name: adk-embedded-diagnostic-harness
description: 嵌入式诊断 harness 治理，覆盖 prog_tool、diag 命令、strict/env 套件、返回码语义、HIL/SIL 证据和产测 CLI 验证
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "诊断 harness"
  - "diag 命令"
  - "prog_tool"
  - "strict suite"
  - "env suite"
  - "invoke_ret"
  - "产测诊断"
  - "诊断验证"
non_triggers:
  - "普通单元测试"
  - "纯 CLI 文案修改"
inputs:
  - 诊断命令清单、套件分类、预置条件、期望返回码、设备依赖、HIL/SIL 证据
outputs:
  - 诊断矩阵、期望结果语义、失败分类、验证证据、剩余硬件/环境依赖
constraints:
  - 不得把所有非零设备返回码直接判为失败
  - 不得为掩盖真实初始化错误而放宽 strict 套件
  - 环境依赖检查必须从 strict 套件中隔离出来
---

# adk-embedded-diagnostic-harness

## Goal
- 建立可复现、可审计的嵌入式诊断 CLI / harness 验证流程。
- 区分产品缺陷、harness 误判、环境依赖和预期失败，减少 false failure。

## Prerequisites
- 已识别诊断入口：`prog_tool`、`diag`、API/HDI/component 诊断、产测 CLI 或等价工具。
- 已明确运行环境：SIL、HIL、真实板卡、产测机、CI 模拟环境。
- 已拿到至少一组命令输出、预期语义或失败样例。

## Workflow
1. 识别诊断面：命令、suite、domain、硬件服务依赖和运行模式。
2. 分类套件：strict 只保留确定性检查；env/HIL 套件承接设备、服务、网络、存储和媒体依赖。
3. 建立期望矩阵：命令、mode、precondition、expected code、expected `invoke_ret`、pass/fail rule、依赖。
4. 先判定 harness 语义：返回码、stderr、超时、缺设备、缺服务是否被正确解释。
5. 再判定产品缺陷：初始化失败、协议错误、资源泄露、权限缺失和真实功能失败。
6. 先跑 focused suite，再跑 `all` 或全量产测套件。
7. 输出 HIL/SIL/manual 证据和剩余硬件依赖；缺真实硬件只能标为 residual risk。

## Commands
```bash
rtk rg -n "prog_tool|diag|invoke_ret|strict|env|suite|expected" <repo>
rtk rg -n "return code|exit code|timeout|device|serial|HDI|API" <diagnostic-path>
<diag-command> --help
<diag-command> run --suite strict
<diag-command> run --suite env
```

## Evidence Template
```md
- Diagnostic Surface:
- Suite Taxonomy:
- Expected Result Matrix:
  | Command | Suite | Preconditions | Expected Code | Expected invoke_ret | Rule | Dependency |
  |---|---|---|---|---|---|---|
- Reclassified Failures:
- Product Defects:
- Validation Commands:
- HIL/SIL Evidence:
- Residual Dependencies:
- Gate Result: pass / needs-fix / blocked
```

## Quality Gate
- 每个失败必须归类为 expected、harness-bug、product-bug、environment-blocked 或 unknown。
- strict suite 必须可确定复跑；环境依赖不得混入 strict pass/fail。
- 产测 CLI 的 usage、返回码和日志摘要必须稳定可读。
- 完成声明必须引用验证命令和证据路径。
