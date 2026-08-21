# project-daily-summary

按“项目 -> 工作流”汇总同日 Codex 工作，默认消费治理事实包和结构化 session receipt。

## 适用场景

- 项目日报、按项目总结今天
- 需要跨仓库归并同一天工作
- 需要同时覆盖会话、提交、工作区差异

## 数据来源优先级

1. Knowledge Hub activity facts JSON
2. 结构化 `session-wrap` receipt
3. 已登记 Git 证据与脱敏 memory cue

## 标准流程

1. 锁定日期（默认今天）。
2. 从 session 证据映射项目根目录。
3. 按项目聚合目标、执行、结果、阻塞。
4. 追加当日提交与未提交改动。
5. 输出高密度日报，避免时间流水账。

## 输出建议

- 每个项目至少包含：`目标`、`完成`、`验证`、`未完成/风险`
- 若用户要求“收口附录”，追加调用 `worktree-closeout`

## 限制

- facts/receipt 缺失时必须标注覆盖缺口
- 不把推测写成事实
