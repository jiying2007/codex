---
name: adk-engineering-growth-review
description: "用于基于已授权的工程历史和交付证据做长期开发习惯复盘、学习建议与趋势分析；不用于推断私人属性或无证据评判个人表现。"
version: 1.1.3
last_updated: 2026-11-20
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
  - 默认 index-first，只读已授权范围；跨项目/全历史仅按明确请求扩展
  - 默认本地 report-only，不自动外发 Slack、邮件或外部服务
  - 不静默写入 ~/.codex/memories；长期记忆只输出候选和人工确认项
  - 仅长期 prompt/Skill/Workflow/AGENTS/记忆晋级须形成 trace-feedback-eval-handoff 候选
  - 联网查学习资源或外部发送必须由用户显式授权
---

# adk-engineering-growth-review

## Goal
基于**已授权且相关**的工程证据复盘；不作无证据个人评价，不全盘扫描、填充模板或额外付费调用。

## Scope / permissions
- 默认 **index-first**：当前项目及已提供的近期交付摘要先读目录/标题/结果与证据索引；只对影响结论的少量样本回读原文。
- 用户明确请求跨项目或全量历史时才扩大范围，预先排除原始聊天、密钥、客户资料及重复记录；没有真实来源就标 `insufficient-evidence`。
- 本地资料只读；报告保存仅在用户明确要求时写入受控工作区。不默认读取 `~/.codex/memories`、所有会话和其他项目，更不授权修改 `AGENTS` 或长期记忆。
- 不自动外发 Slack/邮件/IM、不默认联网寻找课程。外部访问/发送需要显式授权，权限边界不能由本 Skill 扩大。

## Workflow
1. 区分真正的长期成长评估与“只总结当前会话/commit/日报”；后者退出本 Skill。
2. 选最小相关时间窗与项目范围，先检索索引、再按需读取高信号证据；事实与推断分开，不能凭一次故障推断长期能力或私人属性。
3. 找到有重复证据的模式：可复用优势、常见返工、环境摩擦或测试/审查盲区；没有趋势就明确说样本不足，不凑满 3–5 个建议。
4. 为每个有效建议给出“事实证据 → 可执行动作 → 可检查信号”，不用强制生成一周、两周、四周全套训练计划。
5. 仅正式晋级 prompt/Skill/Workflow/AGENTS/记忆时输出 `trace-feedback-eval-handoff` 的 `eval candidate`、验证与 `human approval` 状态；普通建议不需晋级，修改仍按原任务授权。
6. 限定输出长度并保留 raw evidence pointer；保密/权限、跨项目评估等深入细节按需读 `references/growth-evidence-boundaries.md`。

## Output
`Scope / Sources / Observations / Evidence / Recommendations / Validation Signals / Gaps`。确实没有可行动建议时写明原因；额外记忆、课程计划、跨平台发送只在显式请求且获授权时生成。

## Quality Gate
- 趋势必须有足够的跨时点证据，否则归类为单次观察；建议不得基于私人属性或未经证实的行为推断。
- 默认报告只读与脱敏；不存在外部发送、付费调用、全历史扫描的隐式许可。
- 保留来源、置信度与不确定性；源级字节降低不等于真实 Token/阅读质量改善。
