---
name: adk-structured-requirements-questioning
description: "用于头脑风暴、brainstorming、Grill Me、方案拷问、苏格拉底式追问；以 Explore/Challenge 多轮探索意图、方案和决策依赖。不用于已有明确方案的直接实现、普通验收整理或文档润色。"
version: 1.2.3
last_updated: 2026-11-20
triggers:
  - "头脑风暴"
  - "脑暴"
  - "brainstorm"
  - "brainstorming"
  - "grill me"
  - "gill me"
  - "方案拷问"
  - "挑战方案"
  - "苏格拉底式追问"
  - "深度追问"
  - "先发散再提问"
non_triggers:
  - "已有完整方案按计划直接执行"
  - "只执行已有任务包"
  - "纯文档润色"
  - "只运行测试"
inputs:
  - "用户意图、既有决策和代码、约束、证据"
outputs:
  - "确认的设计取舍、未决依赖、反例与验收交接"
constraints:
  - "read-only；不授予实现、设备、发布或额外外部操作权限"
  - "不得冒充用户已确认，不重复已知问题或无限追问"
---

# 交互式设计探索

## Goal
发现真实需求、比较方案并证伪关键风险；使用本原生 Skill，不加载外部 Skill。

## Look before asking
先核已知约束、源码/测试、历史决定；标事实/用户确认/AI 建议/未知。仅问改变决策的问题；批准直接执行即退出。

## Explore protocol
Why 未明时每轮仅问一个关键开放问题；可查事实不再提问。明确意图后比较 2–3 个真正不同方案的收益/成本/失败条件，**反证优先**：给可证伪负例和最小验证；仅一路可行说明理由。

## Challenge protocol — decision tree
“Grill Me / 拷问 / 挑战方案”时，为重要决策记录 id、依赖、备选、证据与状态 confirmed / proposed / unresolved / invalidated。**Frontier** 仅含依赖已解决的未决节点；每轮问独立 frontier（通常 2–4 题），列建议、依据和反例，回答后重算。关注性能、成本、安全、兼容、资源和恢复风险，不凑题、不先问下游。“都按建议”仅确认本轮明示选择。

**部分回答与修订**：沿用问题 ID/原义，不回收或重编号；保留 `depends_on / status / answer_source`。未答保持 unresolved，不默认为同意；查证未返回只挂起依赖分支，独立项可继续。答案对应含糊只澄清该项。上游修订保留旧答案/来源，受影响下游置 invalidated 后重判。用户委托判断的结果标 AI 建议，不能冒充用户确认或新增写权限。

## 可抛弃原型（条件性）
状态机或交互可用性难以口头判断时，提出可证伪问题和最小原型，按需读 `references/prototype-as-experiment.md`。本 Skill 只读；写文件/外部工具仍走已有授权实施流程。

## Cross-mode convergence
无新证据/决策连续两轮即退出，给推荐/最小实验。交付设计、User-confirmed decisions、AI 建议、反例与验证；仅确认项交 triage，实施遵守原授权。

## Quality Gate
Explore 先 Why 后选项；Challenge 遵守依赖，不重复历史。真实多轮效果按源码评测协议 `docs/evals/interactive-discovery-evaluation.md` 独立盲测，静态路由通过不等于效果认证。
