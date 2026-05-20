# llm_tools 正常迭代策略记忆整理附录

## Source

- Date: 2026-05-17
- Project: `llm_tools` / `sigmastar-flasher` / `ota-packager`
- Scope: 用户明确决策：三仓后续不再保持单一初始化提交，改为正常迭代
- Evidence: `/home/leiwenjun/bin/llm_tools/AGENTS.md` 与 `/home/leiwenjun/bin/llm_tools/docs/initial-release-baseline.md` 当前未提交变更
- Base Report: `docs/archive/memory-curation/20260517-154939-memory-curation.md`
- Mode: report-only, no write to `~/.codex/memories`

## 新决策

用户已明确：不用再保持单一初始化提交，后续正常迭代。

项目规则已同步更新为：

1. 三仓后续按正常迭代方式新增提交、正常推送。
2. 不再默认通过 `git commit --amend` 合并历史。
3. 不再默认覆盖推送。
4. 禁止默认使用 `git commit --amend`、`rebase`、`push --force` 或 `push --force-with-lease` 改写历史。
5. 只有用户明确要求“改写历史 / 保持单一提交 / 覆盖推送”时，才允许执行历史改写，并且执行前必须完成提交前检查。

## 记忆候选分级

| Signal | Recommended Action | Reason |
| --- | --- | --- |
| 三仓后续正常迭代，不再默认保持单一初始化提交 | `write-to-memory-candidate` | 这是会影响未来 Git 操作的稳定项目规则 |
| 禁止默认 amend/rebase/force push | `promote-to-agents` + `write-to-memory-candidate` | 已写入项目 AGENTS，也适合做短记忆提醒 |
| 只有用户明确要求才允许覆盖推送 | `write-to-memory-candidate` | 避免未来误改历史 |
| 当前未提交文档变更 | `archive-only` | 状态性信息，不应长期记忆 |
| 历史上的单一初始化提交阶段 | `archive-only` | 已结束，仅保留背景即可 |

## 候选 memory 草案（未写入）

以下是建议人工确认后写入 `~/.codex/memories` 的短记忆草案：

```md
# llm_tools git workflow memory

- `llm_tools`、`sigmastar-flasher`、`ota-packager` 后续按正常迭代方式开发：新增提交、正常推送。
- 不再默认保持单一初始化提交。
- 不要默认使用 `git commit --amend`、`rebase`、`push --force` 或 `push --force-with-lease` 改写三仓历史。
- 只有用户明确要求“改写历史 / 保持单一提交 / 覆盖推送”时，才允许进入历史改写流程，并且必须先完成提交前检查。
```

## 不写入 memory 的内容

- 内网远端地址。
- 具体提交哈希。
- 具体 Windows 构建机身份、路径或授权细节。
- 本轮未提交文件状态。

## 下次恢复建议

```bash
cd /home/leiwenjun/bin/llm_tools
rtk git status --short --branch
rtk ./scripts/toolctl.py doctor
```

如果需要提交当前策略变更，建议使用正常新增提交：

```bash
rtk git add AGENTS.md docs/initial-release-baseline.md
rtk git commit -m "docs(llm-tools): 切换三仓为正常迭代策略"
rtk git push origin master
```

## 结论

- 当前应把“正常迭代、不默认改写历史”视为高优先级项目记忆候选。
- 本次仅归档整理结果，没有写入正式 memory。
