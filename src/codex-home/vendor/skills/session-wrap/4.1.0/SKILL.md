---
name: session-wrap
description: Close the current Codex session with evidence-backed outcomes, decisions, validation, risks, next actions, and activity-session-receipt v2 captured through the public Knowledge Provider. Use only for the current session or resumable handoff; use activity-report for cross-session daily/weekly reports and their archive.
version: 4.1.0
last_updated: 2026-10-31
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Session Wrap

1. 固定本会话范围，读取最少量状态、差异、验证和产物，分开成果、决策、验证、风险、未闭环与下一步。
2. 通过 `rtk bash ~/codex/scripts/knowledge-provider.sh status --summary-json` 核验活动采集能力。仅 `operations.activity-capture.write_allowed=true` 且有明确 `configured_subject_id` 时，当前会话的可报告事项默认应采集；不直接读取 Hub 配置，不需要用户再次提醒。旧Provider缺此字段时保持待补录，不猜主体。
3. 不只采集代码提交：分析结论、只读审查、文档／计划交付、资源治理、阻塞和协作也可报告。没有实现不等于没有活动；分析完成不能写成故障修复。
4. 规范化每项的真实activity_date、稳定item_id、project_id、status和verification。相同任务多轮总结更新同一事项，不把分析／修复／审查／提交拆成重复“成果”；不同交付物可分别记录。
5. 临时输入经公开 Provider Adapter 校验及采集；不得手写 Hub receipt目录。失败记录原因和待补录事项，不能只说“未归档”而遗漏活动采集结果。
6. 输出状态与证据层级、活动采集回执、知识归档状态和未完成验收。活动采集不是长期知识归档。用户已要求归档时按Provider契约处理；未要求时不自动扩大为归档或发布。

## Receipt v2

```json
{
  "schema_version": 2,
  "kind": "activity-session-receipt",
  "session_date": "YYYY-MM-DD",
  "work_items": [{
    "schema_version": 2,
    "kind": "work-activity-item",
    "item_id": "stable-deliverable-id",
    "subject_id": "explicit-configured-subject",
    "project_id": "explicit-project-id-or-empty",
    "activity_date": "YYYY-MM-DD",
    "title": "脱敏的本会话交付或分析事项",
    "status": "planned|in_progress|done|blocked",
    "verification": "verified|reported|missing",
    "outcomes": [],
    "evidence_refs": [],
    "blockers": [],
    "next_actions": [],
    "raw_content_stored": false
  }],
  "raw_content_stored": false
}
```

主体来自Provider公开的配置主体或明确授权，不由Git、路径或姓名猜测Provider身份。verified done需有界证据；Host／ARM／设备／产品、提交／推送分别报告。验证证据不足用reported或missing，未完成验收的交付保持in_progress。

## Provider采集

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh activity-capture --input /tmp/sanitized-session-receipt.json --json
rtk bash ~/codex/scripts/knowledge-provider.sh activity-capture --input /tmp/sanitized-session-receipt.json --apply --json
```

仅 `status=pass` 且 `applied=true` 可声明活动已采集。配置关闭、主体缺失、schema错误、secret扫描或Provider失败时，不降级旧格式、不改内部目录、不提升授权；明确待补录原因。无可报告成果的问候／纯闲聊不创建空receipt。

日报周报跨会话补漏交给activity-report，不将历史成果补成当前会话新贡献。可为交付项保留受控计划ID／版本、承诺日期、上下游与待验收动作；没有计划或owner时明确待确认，不自行分派责任或承诺时间。

不写memory，不commit/push，不修改飞书，不发送消息、不提升active或代签owner。知识候选归档只通过Provider且需明确成功回执，raw session/log和飞书正文不入知识库。
