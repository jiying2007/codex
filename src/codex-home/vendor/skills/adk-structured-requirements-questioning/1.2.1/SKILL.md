---
name: adk-structured-requirements-questioning
description: "用于头脑风暴、brainstorming、Grill Me、方案拷问、苏格拉底式追问；以 Explore/Challenge 多轮探索意图、方案和决策依赖。不用于已有明确方案的直接实现、普通验收整理或文档润色。"
version: 1.2.1
last_updated: 2026-11-09
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
讨论阶段追求发现真实需求、优质方案与可证伪的风险，而非快速填 PRD；只保留这一个原生 Skill，不加载外部 Skill。

## Look before asking
先读用户原话、已批准事项、仓库现状和测试。能自行核实的事实自己查；明确区分事实、用户决定、AI 建议、未知项。仅问答案能改变设计的问题；用户说“直接做”且范围明确则退出，不重新访谈。

## Explore protocol
用户要求“头脑风暴 / brainstorm”或尚未弄清 Why 时使用。**每轮一个关键问题**，先开放询问目标/受益者，不先给诱导选项；依据上一回答调整下一问。意图明确后比较 2–3 个真实可行方向的收益、成本、失败条件与推荐；仅一路合理则直说。阶段性复述设计和未决项，接受纠正。

## Challenge protocol — decision tree
用户要求“Grill Me / 拷问 / 挑战方案”时使用。为重要决策记录 id、前置依赖、备选、证据与状态：confirmed / proposed / unresolved / invalidated。**Frontier** 是依赖已解决的未决节点；每轮只问当前独立 frontier（通常 2–4 题），每题列建议、依据及反例；待回答后重算，不提前问下游。挑战真实的性能、成本、安全、兼容、资源和恢复风险，不能为了凑题追问。“都按建议”仅确认本轮明示选择。

## 可抛弃原型（条件性）
若争议在于状态机是否易理解或交互是否可用，先提出一个可证伪的问题与最小原型方案；按需读 `references/prototype-as-experiment.md`。本 Skill 只做只读设计，真实写文件或调用外部工具需独立进入已有授权实施流程。

## Cross-mode convergence
用户可切换模式或停止；连续两轮没有新证据/决策时给出推荐或最小实验，拒绝空转。讨论结束形成简短设计及 User-confirmed decisions、AI 建议、开放问题、反例和验证路径；仅将确认内容交 `adk-requirements-triage`，按原有审批与工程门禁实现，讨论不等于授权写代码。

## Quality Gate
Explore 先 Why 后选项；Challenge 不能跳过依赖；问题必须改变选择且不重复历史。真实多轮效果依据 `docs/evals/interactive-discovery-evaluation.md` 的独立盲测，静态路由通过不等于效果认证。
