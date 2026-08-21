# Routing Matrix

- 我的日报、本周个人周报、本周事项: personal.
- `<project>` 项目日报/周报: project with explicit project id.
- 所有项目、跨项目、本周整体工作: portfolio.
- Bare 日报/周报: use configured default scope; otherwise return `needs-input`.
- 只看提交、Git 周期总结: use `git-activity-summary`.
- 当前会话、本次会话: use `session-wrap`.

Never use a fallback Skill when required scope or subject is missing.
