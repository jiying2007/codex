---
name: adk-cross-team-handoff
description: "用于产品、研发、测试等多团队交接时明确责任、接口和验收证据；不用于替代需求变更批准或直接操作外部系统。"
version: 1.1.2
last_updated: 2026-11-20
triggers:
  - "团队交接"
  - "模块移交"
  - "跨团队"
non_triggers:
  - 同团队内小范围任务流转
inputs:
  - 当前方案、风险列表、待办事项
outputs:
  - 交接清单、责任矩阵、验收计划
constraints:
  - 交接至少有范围、真实 owner、接收方、验收方式及未决风险
  - 正式权限或生产资产交接需真实批准、签收与恢复条件；未签收不得标完成
---

# adk-cross-team-handoff

## Goal
确保接收方知道接收什么、当前状态、由谁负责和如何验收。文档记录不等于真正完成签收或权限切换。

## Modes
- **lite**：普通模块、脚本、文档协作交接。范围、版本、owner/receiver、链接、验收条件与风险足够；不强制完整 RACI、三方签字或回滚演练。
- **formal**：生产、设备、量产、权限、重要接口和跨组织所有权转移。明确 RACI/授权、窗口、实际签收、验收证据、恢复与必要演练。
- 无接收方批准时状态为 `pending`；真实签收后才能记录 `accepted`。

## Workflow
1. 读取实际交付清单与现有责任边界，不编造不存在的接收人或资产路径。
2. 识别实质风险而不是文档篇幅；权限/设备等绝不可降为 lite 绕过安全合同。
3. 提供交付项及证据、验收方式、未决事项（owner 与下一动作）及支持渠道。
4. formal 按团队真实制度记录 RACI、签收、权限/回退计划，未提供的证据标待补。
5. 逾期或签收失败时提示重新协调，**不得自动修改权限或回滚设备**。

## Receiver cold-read（仅 formal 或材料有歧义时）
- 让接收方在**只看交接文档与声明可访问的证据链接**时回答：交付物及版本在哪里、如何独立验证、哪些风险/依赖仍 `pending`、失败后联系谁及如何停止/恢复。无法回答则改进交接材料或明确待补，不能靠移交方口头背景补造结论。
- lite 不强制新报告、额外模型或签收轮次；formal 的真实接收方验证与批准仍须由受权主体执行，作者自查仅记 `receiver_check: self-review`，未执行的独立核验记 `not-run`。
- 可定位文档不等于资产已交付、命令已运行、权限已转移或接收方已 `accepted`；事实仍按原证据门禁判定。

## Minimal Handoff
```md
- Scope / exclusions / version:
- Owner / receiver:
- Delivered items + evidence:
- Acceptance:
- Risks + next action:
- Receipt: pending | accepted (actual evidence)
```

## Quality Gate
- lite 不因没有 RACI、三方签字和 dry-run 而失败；正式交接的审批与回退不得跳过。
- 不凭文档完成推定对方已签收，也不执行自动权限变更或自动回滚。
- 文档保真：不编造签名、日期、owner、成本与未发生的状态转换。
