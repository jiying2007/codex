# worktree-closeout

按日期做 worktree/分支收口盘点，输出优先级与可执行提示词；全程只读，不执行危险 git 操作。

## 适用场景

- 工作树收口、分支收口、并行收口
- 多会话后需要统一盘点哪些分支还未收口

## 标准流程

1. 先解析并复述确切日期。
2. 再确认范围：`repo` 或 `all`。
3. 运行扫描脚本：

```bash
python -X utf8 ./scripts/scan_closeout.py --date <YYYY-MM-DD> --scope <repo|all> [--repo <ABSOLUTE_REPO_PATH>]
```

4. 读取 artifact，输出阶段顺序：
   - `Phase 1: safe_prune`
   - `Phase 2: ready_to_merge`
   - `Phase 3: blocked / orphaned`
5. 给出总控 prompt 与每项 prompt。

## Fallback（脚本不可用）

若脚本不可运行，改用 `git worktree list --porcelain`、`git branch --merged/--no-merged`、`git status --short` 做手工只读分流，并明确标注 `manual-triage` 与不确定项。

## 限制

- 不自动 merge、push、delete、prune
- 不把 `blocked/orphaned` 提升为并行 merge 波次
