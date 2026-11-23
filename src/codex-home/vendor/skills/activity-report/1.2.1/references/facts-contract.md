# Activity Facts v2

公开 `activity-report` 返回 report-only 回执；确定性底稿在其 `facts` 字段，仅接受 `schema_version=2`、`kind=knowledge-hub.activity-facts-v2`。核验 facts 中 period、timezone、subject、summary、work_items、source_coverage、warnings、privacy，并与回执period对照；生成文件时复核 SHA256，stdout-only 不假称已保存文件。缺少facts保持needs-review，不回读Hub内部路径补足。

work item 必须为 schema v2，具备 item_id、subject_id、activity_date、title、status、verification、raw_content_stored=false。`done + verified` 必须有有界 evidence_refs。隐私标记必须声明无 raw session/log、凭据、绝对工作区路径、身份推断、memory/external write。

冲突、无效、缺日期和截断项分别报告，不强选最新 mtime。不接受旧输入、不自动迁移。`needs-review` 可提供有界草稿，不能显示整体 PASS。

经授权补查获得的历史总结、计划、飞书行属于补充证据，不冒充已经采集的 v2 work item。补录前单独规范化、脱敏和去重，不能为了数量扩大 collector 的可信输入集合。
