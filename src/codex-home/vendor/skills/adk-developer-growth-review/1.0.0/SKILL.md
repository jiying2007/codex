---
name: adk-developer-growth-review
description: 本地开发者成长复盘与学习建议，宽读本地 Codex 历史、归档、日报和项目证据，识别长期趋势、重复问题和训练计划
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "开发者成长复盘"
  - "成长分析"
  - "学习建议"
  - "分析我的编码习惯"
  - "分析最近工作"
  - "developer growth"
  - "growth review"
  - "个人成长报告"
non_triggers:
  - "只总结当前会话"
  - "只生成项目日报"
  - "只总结 commit"
  - "线上事故根因复盘"
inputs:
  - 本地 Codex 历史、session wrap、项目日报、commit 摘要、归档笔记、memory candidate、用户指定范围
outputs:
  - 本地成长复盘报告、证据索引、长期趋势、短期观察、学习建议、训练计划、可选 memory/archive 候选
constraints:
  - 允许本地宽读；默认不固定 24-48 小时时间窗，不限制单一项目
  - 默认本地 report-only，不自动外发 Slack、邮件或外部服务
  - 不静默写入 ~/.codex/memories；长期记忆只输出候选和人工确认项
  - 联网查学习资源或外部发送必须由用户显式授权
---

# adk-developer-growth-review

## Goal
- 基于本地开发证据生成开发者成长复盘和学习建议。
- 识别跨项目、跨会话的重复问题、能力短板、稳定优势、风险模式和下一步训练计划。
- 替代外部 `developer-growth-analysis` 的核心价值，同时把外部发送和联网资源检索降级为显式可选动作。

## Prerequisites
- 已确认用户需要成长复盘、编码习惯分析或学习建议，而不是普通会话总结、项目日报或 commit 摘要。
- 已明确本次范围是当前项目、最近活跃项目、全量本地历史，还是用户指定路径。
- 已确认本轮是否只输出报告，或需要额外产出本地文件、memory candidate、archive candidate。
- 若用户要求联网资源、Slack、邮件或其他外部发送，必须先完成显式授权和权限边界确认。

## Permission Model

默认采用“本地宽读、外部窄写”：

| 能力面 | 默认策略 |
|---|---|
| 读取 `$CODEX_HOME/history.jsonl` 或 `~/.codex/history.jsonl` | 允许，只读，可全量或按用户指定范围 |
| 读取 `~/.codex/memories` | 允许，只读；输出必须区分既有记忆和新候选 |
| 读取 `~/codex/docs/archive/`、`~/codex/reports/` | 允许，只读 |
| 读取当前项目 `reports/`、`docs/archive/`、session wrap、research note | 允许，只读 |
| 读取本地多个 repo 的 `git log`、commit summary、dirty 状态 | 允许，只读 |
| 读取原始聊天、粘贴内容或历史片段 | 允许用于分析，但报告中必须摘要化和脱敏 |
| 写本地报告或 archive note | 仅在用户要求产出文件时允许 |
| 写 `~/.codex/memories`、AGENTS、长期规则 | 默认禁止；只生成候选 |
| 联网搜索 HackerNews、文档或课程 | 可选增强，必须用户显式授权 |
| Slack、邮件、IM、外部发送 | 默认禁止，必须用户显式授权 |

## Scope Strategy
- 默认范围：当前项目、最近活跃项目、可用 session wrap、项目日报和本地历史摘要。
- 用户要求“长期趋势”“全局复盘”时，允许跨全部本地 Codex 历史和归档扫描。
- 不强制短时间窗；输出时按时间衰减加权，近期问题优先，长期重复问题标为趋势。
- 跨项目结论必须按项目或工作流聚类，避免把不同技术栈的问题混成单一判断。

## Workflow
1. 确定范围：记录用户指定范围；若未指定，选择当前项目 + 最近活跃项目 + 可用历史。
2. 读取索引：先读取文件清单、报告标题、日期、项目名和 commit 摘要，建立 evidence index。
3. 分层读取：对高信号材料回读局部原文；对低信号材料只保留摘要和路径。
4. 脱敏处理：移除或摘要化 token、密钥、个人隐私、客户数据和完整聊天原文。
5. 聚类分析：按项目、技术栈、任务类型、失败模式、验证门禁、协作模式归类。
6. 趋势判断：区分一次性噪音、短期反复、长期趋势和高影响改进项。
7. 成长建议：给出 3-5 个优先级排序的改进领域，每项绑定证据和具体训练动作。
8. 学习计划：输出 1 周、2-4 周或用户指定周期的训练计划；不依赖外部资源也必须可执行。
9. 候选沉淀：若发现稳定偏好或重复风险，只输出 memory/archive 候选，不静默写入。
10. 可选增强：用户显式要求时，再进入联网资源检索或外部发送流程。

## Report Template
```md
# Developer Growth Review

- Period:
- Sources:
- Scope:
- Privacy Handling:

## Work Pattern Summary
<2-4 段，按项目/任务类型概括。>

## Recurring Trends
| Trend | Evidence | Impact | Confidence |
|---|---|---|---|

## Improvement Areas
### 1. <Area>
- Why it matters:
- Evidence:
- Recommendation:
- Practice plan:
- Review signal:

## Strengths To Keep
- <evidence-backed strength>

## Training Plan
| Horizon | Action | Evidence To Collect |
|---|---|---|

## Optional Follow-ups
- Memory candidates:
- Archive candidates:
- External resource search: disabled unless explicitly authorized
- External delivery: disabled unless explicitly authorized
```

## Quality Gate
- 报告必须列出证据来源，不得只凭印象评价。
- 每个改进建议必须绑定至少一个本地证据来源或明确标记为低置信度。
- 必须区分“长期趋势”和“短期噪音”。
- 必须说明隐私处理：是否读取原始历史、是否脱敏、是否包含敏感内容。
- 默认不得调用外部网络、Slack、邮件、发布、提交或写长期记忆。
- 若用户要求全量历史扫描，必须说明性能成本和摘要策略，不得把完整聊天原文复制进报告。

## Evidence Template
```md
- Source Scope: current-project / recent-projects / all-local-history / user-specified
- Read Mode: index-first / targeted-raw-read / full-local-scan
- Local Sources:
- Redaction Decision:
- External Actions: none / user-authorized-search / user-authorized-delivery
- Growth Findings:
- Memory Candidates:
- Archive Candidates:
- Gate Result: pass / needs-fix
```
