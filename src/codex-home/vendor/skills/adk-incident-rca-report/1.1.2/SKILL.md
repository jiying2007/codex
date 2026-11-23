---
name: adk-incident-rca-report
description: "用于生产事故稳定后整理时间线、根因、恢复和防复发证据；不用于事故正在处置时替代现场响应或虚构不存在的取证材料。"
version: 1.1.2
last_updated: 2026-11-20
triggers:
  - "线上事故"
  - "故障复盘"
  - "RCA分析"
  - "根因分析"
non_triggers:
  - 本地开发阶段的临时报错
inputs:
  - 事故时间线、监控数据、变更记录
outputs:
  - RCA 报告、修复项、预防项
constraints:
  - 区分确认事实、已证实因果、候选假设与未决问题
  - 不编造事故时间、影响、组织责任或概率；实际恢复操作需另行授权
---

# adk-incident-rca-report

## Goal
事故止损后凭证据解释因果与防复发；不以 5-Why 层数评判质量。

## Workflow
1. 固定事件范围、版本、影响与证据；保留原时区，区分事件发生与采集时间，仅可比时统一时基。未知时间/时钟偏差记 `unknown`，不凭采集顺序断因果。
2. 单一原因已复现时使用“触发 → 失效机制 → 影响 → 修复/验证”短链。
3. 多因素场景才按需用 5-Why、故障树或事件序列分析；**5-Why 为可选分析工具**，不强制凑三层/五层，不能因为模板把责任推给组织。
4. 根因没有确认时标 `unresolved`；分别记录事实、假设、被证伪方向、下一步取证，不编造概率或确定性判断。
5. 按实际缺口选择检测/缓解/预防行动，给改进、复验信号及实际 owner（未知则待确认），不强制三类齐全。生产、安全、数据写入或回滚仍维持原权限与恢复边界。
6. 默认短报告；需正式档案/多方协调时才补 RACI、影响核算与长期复查。

## Report
```md
- Incident / status / time range (event_time / observed_time / timezone / clock_uncertainty):
- Verified impact / unknown:
- Facts and evidence pointers:
- Causal chain: confirmed | hypothesis | unresolved
- Action (detect | mitigate | prevent) / owner / verification:
- Open questions / residual risks:
```

## Quality Gate
- 根因未验证不能宣称已闭环；不能虚构日志、时间点、损失、概率和复验结果。
- 正式事故的审批、权限、生产恢复及验证要求不得因 lite 输出被降低。
- 文档保真：保留原始证据、技术细节与不确定状态，不为了 5-Why 完整而创造因果。
