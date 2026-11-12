---
name: activity-report
description: Generate evidence-bounded personal, team, project, and portfolio daily or weekly reports; reconcile activity facts with authorized local records, project plans, and related teams, and archive sanitized report candidates when requested. Use for 日报、周报、个人工作总结、团队周报、周报补漏 or 日报周报归档. Use git-activity-summary for Git-only history and session-wrap for the current session.
version: 1.2.0
last_updated: 2026-11-09
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Activity Report

生成可追溯的中文日报、周报。Activity Facts v2 是确定性事实底稿，不代表整天或整周工作已完整采集。

## 范围与来源

1. 固定周期、Asia/Hong_Kong 截止时间、个人主体、团队或项目范围及输出用途。个人主体使用显式 `subject_id` 或有效配置；真实姓名、团队声明可确认本次展示身份，不能据此猜另一个 Provider principal、owner 或授权。
2. 若存在 `~/codex/manifests/activity_report_sources.json`，读取用户配置的来源及映射；它是本机报告取材配置，不是项目事实、凭据或外部写授权。其他环境无此文件时使用用户本次明确提供的来源。
3. 读取 [routing-matrix.md](references/routing-matrix.md)。团队是展示与取材范围，现有 collector 仅支持 personal/project/portfolio；不得虚构 `--scope team`，也不能将全部 portfolio 当作团队成员成果。

## 采集与补漏

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh activity-report --period weekly --scope personal --as-of YYYY-MM-DD --json
```

先核验 [facts-contract.md](references/facts-contract.md)，再按 [source-reconciliation.md](references/source-reconciliation.md) 检查本地记录和飞书覆盖。发现个人行为空、事项明显偏少，或用户指出遗漏时，必须说明覆盖缺口并补查，不能把空行当作没有工作。

用户指出的主要项目或模块逐项核对；冲突事项不计完成数，但仍保留补查线索。不能因为未进入有效统计而漏掉整块工作，也不能用工具维护等次要事项填补主要项目缺口。

项目计划、成员或部门关联内容按 [plan-and-dependencies.md](references/plan-and-dependencies.md) 对照。日报保留当天增量和阻塞；周报按交付主题合并，不累计每日重复进展。只读飞书使用现有 `feishu-readonly` 入口，范围内分段续读不重复询问。

## 证据与成稿

- 按 [authority-policy.md](references/authority-policy.md) 区分验证成果、自报成果、推进中、阻塞和计划；本地历史补查单列来源与可信边界。
- 有事项、无完成证据时可以报告“开展排查／完成分析，修复待验证”，不能漏报也不能升级为修复完成。
- 合并同一任务的分析、修改、审查、提交和日报重复记录；按实际工作日期处理跨周结转，按后续明确修订处理 superseded 结论。
- 按 [output-contract.md](references/output-contract.md) 同时给成果、计划偏差、跨部门依赖、下步动作和覆盖边界；已验证数量、补查候选数量、成员自报数量分开统计。
- 用户要求团队和个人两份时分别成稿；要求去AI化、精简或粘贴Excel时，采用该契约中的纯文本排版，保留正常换行，不自动改成长行TSV。

## 记录与归档

默认只读成稿。用户要求补录或归档时，按 [capture-and-archive.md](references/capture-and-archive.md) 通过公开 Provider Adapter 执行；v2 活动采集、报告候选归档、飞书发布是三种独立结果。仅明确成功回执可声明已记录／已归档。

不得写 memory、自动修改飞书、发送消息、提升 active、签收 owner、提交或推送。不得读取凭据、原始现场日志或设备标识；历史补查仅在有授权且结构化证据不足时有界读取相关会话的总结，不能批量保存会话正文。Provider unavailable 或 route unresolved 的相关部分保持 NEEDS_REVIEW，不用路径猜测补主体。
