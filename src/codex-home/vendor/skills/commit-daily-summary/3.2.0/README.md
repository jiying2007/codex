# commit-daily-summary

将同一天 git 提交转成可读的中文工作摘要，适合“我今天提交了什么”的快速回顾。

## 适用场景

- 提交总结、今天做了什么（基于 commit）
- 需要日报但只关心已提交内容

## 不适用

- 当前会话收尾：`session-wrap`
- 按项目汇总会话 + 提交 + 未提交：`project-daily-summary`
- 调研纪要：`research-note-wrap`

## 标准流程

1. 确认日期与仓库范围（默认今天/当前仓库）。
2. 采集 commit 证据：

```bash
rtk git -C <repo> log --since="YYYY-MM-DD 00:00" --until="YYYY-MM-DD 23:59:59" --pretty=format:"%h%x09%s"
```

3. 按主题聚合，不按 commit 逐条复述。
4. 产出动作化中文摘要，并可附原始 commit 列表。

## 输出建议

- 日期、范围、提交数
- 主题摘要（2 到 6 条）
- 可选：原始提交列表

## 限制

- 无 commit 时必须明确说明“无可总结提交”
- 不伪造提交或验证结果
