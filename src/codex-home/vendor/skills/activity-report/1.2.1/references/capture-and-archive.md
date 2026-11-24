# 活动采集与日报周报归档

三个独立状态：活动事实已采集、日报／周报reviewing候选已归档、报告已发布。默认 report-only；既有配置允许的当前会话回执通过 session-wrap 处理。用户要求补录／归档后，仅使用公开 Provider Adapter 持久化，不手写 Hub 内部目录，不写 memory 或飞书。

## 补录活动

以脱敏的 schema v2 输入文件承载明确主体的单条事项或回执。历史补录应保留真实 activity_date；不能把以前的工作伪装成本会话新成果。每条以原主题／记录ID稳定去重。已有冲突先 reconcile，不用另换item_id、重复receipt或latest mtime绕过冲突。

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh activity-capture --input /tmp/sanitized-activity.json --json
rtk bash ~/codex/scripts/knowledge-provider.sh activity-capture --input /tmp/sanitized-activity.json --apply --json
```

先核schema、主体、时间、证据及预览；只有 Provider 返回 `status=pass`、`applied=true` 才说明活动采集成功。receipt缓存不等于长期知识归档。历史会话自报测试不自动变成本轮verified；证据不足用reported或missing。

## 日报周报候选

同一规范化交付项供日报与周报引用，周报合并日报，避免双份“完成”事项。报告保留周期、主体／团队范围、项目计划基线、成果和验证层级、关联依赖、未闭环及来源覆盖。只保存脱敏结论和有界引用；不复制原始会话、现场日志、飞书整表或设备标识。

个人报告使用配置确认的 personal subject；团队／项目报告经Provider解析实际subject和权限，不能用团队显示名拼装新domain。报告period/scope/subject应在标题或正文固定，重复归档先核既有候选及hash，不把另一次归档成功当新成果。正文修订走Provider支持的修订契约；不支持时保留取代关系，不能冒充已更新原候选。

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh archive --subject personal:EXPLICIT_SUBJECT --source /tmp/sanitized-report.md --kind codex-session --title '周期与范围明确的工作周报' --sanitized --dry-run --json
rtk bash ~/codex/scripts/knowledge-provider.sh archive --subject personal:EXPLICIT_SUBJECT --source /tmp/sanitized-report.md --kind codex-session --title '周期与范围明确的工作周报' --sanitized --apply --json
```

参数中的 EXPLICIT_SUBJECT 必须来自配置或明确授权，不是占位符可直接执行。遵循当前 Provider help 确认 kind 与subject支持；仅 `ARCHIVED`／`ALREADY_ARCHIVED` 且 `persisted=true` 可称“已归档为reviewing候选”。权限不足、不支持、route unresolved或未知结果保持NEEDS_REVIEW，不直写内部路径，不改授权策略。归档成功不代表active提升、owner签收、工程验收或飞书发送。
