---
name: adk-adr-writer
description: "已有架构权衡、需编写或更新 ADR 时记录真实决定、依据与后果；不用于概念介绍、需求未明或代码实现。"
version: 1.2.3
last_updated: 2026-11-20
triggers:
  - "写ADR/编写ADR/撰写ADR/更新ADR/修订ADR/写成ADR/记录为ADR/整理成ADR"
  - "架构决策"
  - "决策记录"
non_triggers:
  - 临时性小修补
inputs:
  - 候选方案、约束、风险
outputs:
  - ADR 文档草稿
constraints:
  - 必须保留真实决策、依据、trade-off 与后果，不虚构 rejected options 或评分
  - 高风险公共接口、安全和迁移决策必须保留实际验证与回退边界
---

# adk-adr-writer

## Goal
记录真实选择与理由；Context、Decision、Alternatives、Consequences 可追溯，建议不得冒充已批准决策。

## Risk-based authoring
- **lite（默认）**：局部可逆决策。简述背景、选择、理由、后果及验证；确无其他可行路径时写明约束，不编造第二方案。
- **standard**：真实存在多条可行路径，记录候选与利弊；可用定性权衡，不强制加权分数。
- **deep**：公共 API/ABI、权限、安全、数据迁移、生产或不可逆决定。补足来源、失败场景、演进成本、责任与回退；只有可核实权重时才引入量化矩阵。
- 高风险不能因为省 Token 降为 lite。

## Workflow
1. 检查已知目标、约束、用户实际选择、现有 ADR；不重问已确认事实。
2. 固定核心决定与取舍，只有一个可行方案时解释排除其他路径的原因，不虚构备选。
3. 记录后果与证据；缺失成本、性能或决策状态标待核。
4. 需要写入仓库时，按目标项目的 ADR 编号规则查找已有编号（例如 `ADR-NNN`），不覆盖旧决策；仅要求草稿则不写文件。
5. 自检事实、术语、数值、限制词和引用关系；删无必要的复述。定向修订只改授权段落/字段，逐字保留其余约束、状态、数字、单位与引用；发现冲突先标明，不扩大成整篇改写或升级决策状态。

## Reader-only acceptance（按风险，不默认增加模型轮次）
- **lite**：作者只依据成稿而非历史会话自检：读者能否区分 `proposed / accepted`、说出核心决定及其理由、定位验证办法？能则结束，不另建文档评测流水线。
- **standard/deep 或需长期跨团队引用**：冻结仅含最终草稿和明确引用的 `reader_view`，按目标读者回答：`What was decided? Why? What changes for me? What evidence is missing? Who owns rollback?`。回答依赖未提供的口头背景、含糊状态或不存在的证据时，修正文档或标 `unknown/pending`，不虚构批准、结果和责任人。
- 只做作者冷读时标 `reader_check: self-review`；独立读者或真实模型评测只有在被授权且实际执行后才标 `independent-verified`，否则 `not-run`。不能用作者自评冒充真实读者理解率。

## Output
```md
# ADR: <决策>
Status: proposed | accepted | deprecated | superseded
Context: <已知事实>
Decision: <真实决定或待确认建议>
Alternatives: <真实备选或无可行替代的原因>
Consequences: <权衡、影响与风险>
Validation: <证据/后续验证或待核>
```

## Quality Gate
- lite 不强制 2 个候选、3 个评价维度、加权总分或完整迁移矩阵；deep 不可省略安全/兼容与恢复要求。
- 不虚构 `rejected options`、真实批准、性能数据或验证通过状态。
- 文档保真：数字、单位、接口名、来源、因果和“可能/必须”等限定语不能在润色中被篡改。
