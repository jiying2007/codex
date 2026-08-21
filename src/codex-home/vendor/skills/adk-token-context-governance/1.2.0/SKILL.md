---
name: adk-token-context-governance
description: 保真省 Token 的上下文读取治理，分层摘要、原文回退与高风险原文门禁
version: 1.2.0
last_updated: 2026-07-07
triggers:
  - "省 token"
  - "上下文太大"
  - "压缩输出"
  - "工具输出太长"
  - "日志太长"
  - "回退原文"
  - "token budget"
  - "上下文预算"
  - "审计模式"
  - "低 token"
  - "Low Token"
  - "Low Token Profile"
  - "知识编译"
  - "Knowledge Compile"
  - "渐进记忆检索"
  - "Progressive Memory Search"
non_triggers:
  - "单文件小改且上下文已充足"
  - "高风险审计要求直接看原文"
  - "只做短文本问答"
inputs:
  - 任务类型、风险等级、上下文预算模式、工具输出摘要、原始证据路径、置信度和回退条件
outputs:
  - 上下文预算配置、读取计划、工具输出摘要、原文证据索引、回退决策、风险门禁结论
constraints:
  - 摘要不能替代原文证据
  - 高风险任务必须读取原文或保留原文入口
  - 原始日志/diff/测试输出必须可追溯
  - 置信度不足时必须回退局部或原文
  - tool/skill 目录读取必须先使用 namespace summary，完整正文、references 和 schema 只在意图命中后加载
---

# 保真省 Token 上下文治理

## Goal
- 降低工具输出、日志、diff 和项目结构扫描的上下文噪音，同时保留可回退的原文证据。
- 防止 Agent 因压缩摘要过度自信，导致根因误判、审计漏判或交付证据缺失。

## Prerequisites
- 明确当前任务目标、风险等级、可用原始证据来源和验证方式。
- 确认压缩对象是只读信息输出，而不是会改变环境的操作。

## Workflow
1. 判定任务风险：普通开发为 low，跨模块 debug/接口变更为 medium，安全、权限、支付、数据库迁移、生产故障、协议兼容和签名逻辑为 high。
2. 选择上下文预算模式：极速用于探索，均衡用于日常编码，精确用于 debug/review，审计用于高风险原文判断。
3. 选择读取层级：L0 只读索引，L1 读摘要，L2 读局部原文，L3 读完整原文。
4. 只压缩只读输出：`git diff/status/log`、`rg`、测试日志、`docker logs --tail`、目录清单；写操作、删除、部署、数据库写入不得压缩代替审查。
5. 生成摘要时必须记录 `raw_evidence`、`confidence`、`fallback_condition`、`budget_profile` 和下一步读取层级。
6. 摘要缺少错误栈、调用方、迁移信息、权限条件、金额单位、签名字段或生产时间线时，立即回退 L2/L3。
7. 高风险任务必须读取原文或在交付证据中给出原文路径；不能只凭摘要下结论。
8. 出现 `HOT`、`CTX_PRESSURE`、长会话阶段切换或目标切换时，输出交接摘要并把下一阶段限制为预算配置中的必要证据。
9. 长期项目维护 `PROJECT_MAP.md`，只保存入口、测试、禁读目录、高风险区域和已验证时间，不保存一次性日志。
10. 完成前运行 token budget 与资产严格校验，并在报告中说明是否发生回退原文。
11. 可选代码智能提供方只能缩小阅读范围。记录 `code_intelligence_provider_contract`：provider、query、provider_answered、fallback_used、confidence、returned_files、raw_evidence、omitted_reasons、source_reread_required；高风险变更必须回读源码。
12. 大型 tool/skill 目录按 `tool_search_context_contract` 读取：记录 `namespace_summary`、`initial_surface`、`deferred_surface`、`loaded_tools`、`trusted_inventory`、`schema_review` 和相邻候选省略原因；不得把 deferred loading 视为权限审批。

## Budget Modes

| Mode | 场景 | 默认层级 | 压缩策略 |
|---|---|---|---|
| 极速 | 扫仓、定位入口、候选文件发现 | L0/L1 | 激进摘要，保留原文入口 |
| 均衡 | 普通实现、低中风险 bug | L1/L2 | 类型化摘要，关键窗口回读 |
| 精确 | 根因未明、代码 review、接口变更 | L2 | 少压缩，多读调用方和局部原文 |
| 审计 | 安全、权限、支付、迁移、生产事故 | L3 | 不压缩结论证据，只去重和排序 |

## Read Tiers

| Tier | 用途 | 最小证据 |
|---|---|---|
| L0 | 项目入口、模块地图、测试入口 | `PROJECT_MAP.md` 或目录摘要 |
| L1 | 普通定位、低风险变更 | 摘要 + `raw_evidence` |
| L2 | 根因未明、接口/测试失败 | 相关文件窗口、局部日志、关键 diff |
| L3 | 高风险或交付争议 | 完整日志、完整 diff、完整原文 |

## Compiled Knowledge Boundary

LLM Wiki / Knowledge Compile 的读取顺序是 `schema` / index -> `maintained_wiki` -> `raw_sources`。`maintained_wiki` 综合页只用于快速定位、去重和关系梳理；综合页不是原始证据，不能作为高风险结论、记忆晋升、规则提升或交付争议的唯一依据。

读取 compiled knowledge 时必须保留 `raw_fallback`：

- wiki 条目缺少 `raw_source_path`、`source_url_or_local_path`、`schema_path`、`retrieved_at`、`review_status`、`expires_at` 或 `duplicate_concept_check` 时，只能作为候选线索。
- 遇到 stale claims、弱链接、孤立页面、重复概念页、schema 冲突、低置信度、过期来源或用户要求精确依据时，回退 `raw_sources`。
- 从综合页得到的新 synthesis 需要写回时，先进入待审查 `change_log`，不得覆盖原始材料。
- context pack 必须记录 included sections 与 `omitted_reasons`；省略原因只能是低相关、已有更近证据、已读摘要可回退或预算限制，不得省略高风险原文入口。
- `code_intelligence_provider_contract` 的结果不是 source of truth。`source_reread_required: true` 时，完成前必须回读对应源码或标记为未闭环。
- `tool_search_context_contract` 只用于降噪和延迟加载。若 namespace summary 缺少 owner、auth/write class、trigger/boundary 或 trusted inventory，必须回退原始 manifest / SKILL.md / tool schema。

## Quality Gate
- 摘要必须包含 `raw_evidence`、`confidence`、`fallback_condition`。
- 预算配置必须包含 `task_type`、`risk_level`、`read_tier`、`budget_profile`、`compress_allowed`、`raw_required`。
- high 风险项不得以压缩摘要作为唯一依据。
- 原始证据可追溯，复盘时能重新读取。
- token budget 检查与 strict 资产校验通过。
- tool/skill 目录压缩必须记录 `trusted_inventory`、`deferred_surface` 和 `loaded_tools`，且 schema review 通过后才能执行工具。

## Evidence Template
```md
- read_tier: L0 / L1 / L2 / L3
- budget_profile: fast / balanced / precision / audit
- summary: <compressed facts>
- raw_evidence: <path or command output source>
- confidence: low / medium / high
- fallback_condition: <when to read local/raw/full context>
- high_risk_raw_read: yes / no / not-applicable
- code_intelligence_provider_contract:
  - provider:
  - provider_answered:
  - fallback_used:
  - confidence:
  - returned_files:
  - omitted_reasons:
  - source_reread_required:
- tool_search_context_contract:
  - namespace_summary:
  - initial_surface:
  - deferred_surface:
  - loaded_tools:
  - trusted_inventory:
  - schema_review:
  - omitted_reasons:
```
