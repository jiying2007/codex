---
name: adk-token-context-governance
description: 全链路保真省 Token 治理，统一预算、渐进加载、原文回退与高风险原文门禁
version: 1.3.0
last_updated: 2026-09-14
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
  - "token lean"
  - "知识编译"
  - "Knowledge Compile"
  - "渐进记忆检索"
  - "Progressive Memory Search"
non_triggers:
  - "单文件小改且上下文已充足"
  - "高风险审计要求直接看原文"
  - "只做短文本问答"
inputs:
  - 任务类型、风险等级、预算模式、工具输出、原始证据路径、置信度和回退条件
outputs:
  - 上下文预算、读取计划、摘要、原文证据索引、回退决策和风险门禁
constraints:
  - 摘要不能替代原文证据
  - 高风险必须读取原文或保留原文入口
  - 日志、diff、测试输出必须可追溯
  - 置信度不足必须回退局部或完整原文
  - tool/skill 先读 namespace summary，正文、references、schema 仅在意图命中后加载
---

# 保真省 Token 上下文治理

## Goal
- 全 profile/workflow 默认用最小充分上下文，减少输入、工具和证据噪音。
- 保留 `raw_fallback`，避免压缩导致根因误判、审计漏判或交付证据缺失。
- 机器策略以 `manifests/token_context_policy.json` 为准。

## Global Invariants
- 默认 `balanced`；显式 Low Token 仅切到 `fast` runtime overlay，不新增资产 profile/skill。
- progressive disclosure：L1 只放稳定最小规则；agent/skill/tool/reference 按意图命中加载。
- stable reusable context 放前，动态用户/检索/运行证据放后；支持时记录 `input_tokens/output_tokens/cached_tokens/total_tokens`。
- 工具输出先 bounded summary + raw pointer；完整日志保留在上下文外，可按需回读。
- mutation 审批不得由压缩摘要替代；high risk 强制 `audit/L3`。
- low confidence、缺 raw evidence、契约冲突或安全例外立即恢复更完整上下文；省 token 不得降低验证、review、回滚或证据强度。

## Prerequisites
- 确认任务风险、原始证据入口与可用预算信息。
- 高风险或缺 raw evidence 时先进入 `audit/L3`，不先压缩再猜测。

## Workflow
1. 定风险：普通开发 low；跨模块 debug/接口变更 medium；安全、权限、支付、迁移、生产事故、协议兼容、签名逻辑 high。
2. 定预算：`fast / balanced / precision / audit`；未指定时 `balanced`。
3. 定读取层级：L0 索引、L1 摘要、L2 局部原文、L3 完整原文。
4. 只压缩只读输出，如 `git diff/status/log`、`rg`、测试日志、`docker logs --tail`、目录清单。
5. 摘要记录 `raw_evidence/confidence/fallback_condition/budget_profile/read_tier`；关键条件缺失时回退 L2/L3。
6. `HOT`、`CTX_PRESSURE`、阶段/目标切换时输出 handoff，只携带下一阶段必要证据。
7. 长期项目用 `PROJECT_MAP.md` 保存入口、测试、禁读目录、高风险区域和验证时间，不保存一次性日志。
8. code intelligence 仅缩小阅读面；记录 `code_intelligence_provider_contract`：provider、query、provider_answered、fallback_used、confidence、returned_files、raw_evidence、omitted_reasons、source_reread_required；高风险完成前回读 source。
9. 大型 tool/skill 目录按 `tool_search_context_contract` 延迟加载：记录 namespace_summary、initial_surface、deferred_surface、loaded_tools、trusted_inventory、schema_review、omitted_reasons；不得把 deferred loading 当成权限审批。
10. 完成前跑 token budget 与 strict asset validation，并声明是否发生 `raw_fallback`。

## Budget Modes
| Mode | 场景 | 默认层级 | 策略 |
|---|---|---|---|
| fast | 探索、定位、显式 Low Token | L0/L1 | 激进摘要 + raw pointer |
| balanced | 日常实现、低中风险 bug | L1/L2 | 类型化摘要 + 关键窗口回读 |
| precision | 根因未明、review、接口变更 | L2 | 少压缩，多读局部原文 |
| audit | 高风险、交付争议 | L3 | 结论证据不压缩，仅去重排序 |

## Read Tiers
| Tier | 用途 | 最小证据 |
|---|---|---|
| L0 | 项目/模块/测试入口 | index / `PROJECT_MAP.md` |
| L1 | 普通定位、低风险变更 | summary + `raw_evidence` |
| L2 | 根因未明、接口/测试失败 | 文件窗口、局部日志、关键 diff |
| L3 | 高风险或交付争议 | 完整日志、diff、原文 |

## Compiled Knowledge Boundary
读取顺序：`schema/index -> maintained_wiki -> raw_sources`。**综合页不是原始证据**；仅用于定位、去重和关系梳理，不能作为高风险结论、记忆晋升或规则提升的唯一依据。编译/晋升前记录 `duplicate_concept_check`；缺 `raw_source_path/source_url_or_local_path/schema_path/review_status/expires_at`，或 stale/冲突/低置信度时必须回退 raw source。context pack 记录 included sections 与 `omitted_reasons`。`code_intelligence_provider_contract` 不是 source of truth；`source_reread_required: true` 时必须回读源码。`tool_search_context_contract` 只用于降噪和延迟加载，trusted inventory/schema 不足时回退原始 manifest、SKILL.md 或 tool schema。

## Quality Gate
- `raw_evidence/confidence/fallback_condition` 齐全；预算配置含 `task_type/risk_level/read_tier/budget_profile/compress_allowed/raw_required`。
- high risk 不以摘要为唯一依据；tool/skill 延迟加载记录 `trusted_inventory/deferred_surface/loaded_tools`，执行前完成 schema review。
- 支持 usage 时记录 token/cache 指标；token budget 和 strict validation 通过。

## Evidence Template
```md
- read_tier: L0 / L1 / L2 / L3
- budget_profile: fast / balanced / precision / audit
- summary:
- raw_evidence:
- confidence: low / medium / high
- fallback_condition:
- high_risk_raw_read: yes / no / not-applicable
- usage: input_tokens / output_tokens / cached_tokens / total_tokens / unavailable
- code_intelligence_provider_contract: provider / query / provider_answered / fallback_used / confidence / returned_files / raw_evidence / omitted_reasons / source_reread_required
- tool_search_context_contract: namespace_summary / initial_surface / deferred_surface / loaded_tools / trusted_inventory / schema_review / omitted_reasons
```
