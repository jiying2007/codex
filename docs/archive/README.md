# Knowledge Archive

`docs/archive/` 保存长期可复用、已脱敏、可追溯的知识材料，不保存 Codex 原始运行态。

## 结构

```text
docs/archive/
  _registry/
    projects.json
    workstreams.jsonl
    sessions.jsonl
    topics.json
    schema.md
  <topic>/
    index.md
    <archive>.md
    <archive>.md.meta.json
```

目录仍按 topic 分组；项目、会话、工作流、状态等身份信息写入 registry 与 meta v2，避免多项目并行时按目录形成知识孤岛。

归档入口：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md \
  --topic session-wrap \
  --project pcr02-ssc305 \
  --workstream build-hardcut \
  --session 20260518-223733-pcr02-ssc305-build-hardcut \
  --status closed \
  --memory-action archive-only \
  --tag build
```

查询入口：

```bash
rtk bash scripts/archive-search.sh "构建" --project pcr02-ssc305 --json
rtk bash scripts/archive-search.sh "" --open-only --json
```

门禁入口：

```bash
rtk bash scripts/archive-check.sh
```

约定：

- 先脱敏，再归档。
- 默认复制，只有明确迁移时使用 `--move`。
- 每个 topic 目录维护 `index.md`；每条归档材料必须有同名 `.meta.json`，且使用 `schema_version=2`。
- 归档正文必须位于 `docs/archive/<topic>/` 一层，不再按项目、知识类型或工具名继续嵌套子目录。
- 归档文件名使用 `YYYYMMDD-HHMMSS-slug.md`；不允许 date-only 文件名，slug 不得再次包含 `YYYY-MM-DD`、`YYYYMMDD` 或重复时间前缀。
- meta 中的 `destination` 与 `metadata` 使用仓库相对路径，`archive_id` 必须等于正文文件 stem。
- Topic index 的标题只描述 topic，不得被单条归档材料标题覆盖。
- 不归档原始 secrets、auth、`.codex/sessions`、logs、cache、tmp 和本机私有运行态。
- 允许归档脱敏后的 `session-wrap`、日报、调研结论、排障总结和治理报告。
- 项目专属材料必须在 meta 中标记 `scope=project-specific` 与 `project_id`，且 `project_id` 必须存在于 `_registry/projects.json`。
- 未显式传 `--project` 时，`archive-note` 会按 `--source-repo`、source path、当前 cwd 的顺序匹配 project registry；嵌套路径采用最近匹配原则。
- `status=open` 必须有 `owner` 与 `next_action`，用于恢复会话和继续推进。
- 近重复历史材料先标记 `governance_status=superseded` 与 `superseded_by`；删除或迁移必须另行显式确认。

## 记忆边界

- `docs/archive/` 保存脱敏长期材料。
- `~/.codex/memories` 只保存人工确认后的短小稳定记忆。
- `memory_action=archive-only` 是默认值；只有经过审查的材料才能标记为 `candidate`、`promote-to-agents` 或 `write-to-memory`。
