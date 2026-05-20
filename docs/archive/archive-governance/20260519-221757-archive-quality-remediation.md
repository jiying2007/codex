# Archive Quality Remediation - 2026-05-19

## Scope

本次治理只修改 `docs/archive/` 下的归档材料、索引与元数据，不写入 `~/.codex/memories`，不提升任何规则到 `AGENTS.md`。

## Decisions

- Topic index 的标题必须表达 topic，而不是最近一次归档条目的标题。
- 每个归档条目 Markdown 必须有同名 `.meta.json`。
- 项目专属材料保留为 `scope=project-specific`，不得直接作为全局 Codex 规则提升。
- 高度重复的历史报告不直接删除，先以 `governance_status=superseded` 和 `superseded_by` 标记，等待显式 prune。
- 原始 session/log/cache/tmp/private state 不进入归档；脱敏后的 session-wrap 和 summary 允许归档。

## Verification Targets

- Missing meta count: 0
- Orphan meta count: 0
- Invalid meta JSON count: 0
- Secret-like assignment pattern count: 0
- Credential block marker count: 0


## Verification Results

- Entries: `47`
- Meta files: `47`
- Missing meta count: `0`
- Orphan meta count: `0`
- Invalid meta JSON count: `0`
- Secret-like assignment pattern count: `0`
- Credential block marker count: `0`
- Superseded entries marked in meta: `8`
- Root-cause guard: `tools/codex_assets/core.py` now keeps topic-level index titles across multiple archive-note runs.
- Regression test: `rtk python3 -m unittest tests.test_archive_note` passed.
- Compile check: `rtk python3 -m compileall -q tools/codex_assets/core.py tests/test_archive_note.py` passed.

## Archive Governance v2 Landing

本次后续治理把 archive 从“每条材料自带 meta”推进到“registry + meta v2 + 查询 + 门禁”的可恢复系统：

- 新增 `_registry/projects.json`、`workstreams.jsonl`、`sessions.jsonl`、`topics.json`、`schema.md`。
- 全量归档 meta 迁移到 `schema_version=2`，补齐 `archive_id`、`scope`、`status`、`governance_status`、`memory_action`、`content_sha256` 等治理字段。
- `archive-note` 支持 `--project`、`--source-repo`、`--workstream`、`--session`、`--status`、`--scope`、`--memory-action` 和 `--tag`。
- 项目识别支持从 `source_repo`、source path、cwd 自动匹配 registry，并按嵌套最近匹配原则选择项目。
- `archive-search` 支持按 project/workstream/session/scope/status/governance_status/memory_action/owner 过滤，`--open-only` 可列出未关闭会话。
- `archive-check` 纳入 `scripts/check.sh`，强制校验 meta v2、registry 引用、hash、open/superseded follow-up 和敏感信息模式。

## Physical Layout Remediation

本次继续把已归档材料按 v2 物理规范修正：

- 将 `control-archives/knowledge/bwrap/` 下的 legacy bwrap 归档拉平到 `control-archives/` topic 根目录。
- 删除嵌套 topic index，只保留每个 topic 的 canonical `index.md`。
- 将归档文件名统一为 `YYYYMMDD-HHMMSS-slug.md`，移除 date-only 文件名、slug 中重复的 `YYYY-MM-DD`、`YYYYMMDD` 和二次时间前缀。
- 同步更新 meta 的 `archive_id`、`destination`、`metadata`、`content_sha256` 和 session-wrap 的 `session_id`。
- 将 meta 中的 `destination` 与 `metadata` 统一为仓库相对路径，避免 checkout 路径变化导致归档不可移植。
- 从当前 `session-wrap/*.meta.json` 重建 `_registry/sessions.jsonl`，确保会话恢复入口和真实文件名一致。
- 把文件正文与 meta 中指向旧 archive 路径的引用替换为新路径；保留 `source` 中的历史来源路径作为 provenance。
- `archive-check` 新增目录层级与文件名门禁，防止后续重新引入嵌套归档或日期噪音文件名。

补充验证结果：

- `rtk bash scripts/archive-check.sh --json` passed: `0` errors, `0` warnings.
- `rtk bash scripts/archive-search.sh "构建" --project pcr02-ssc305 --json` passed and returned project-scoped hits with `project_id=pcr02-ssc305`.
- `rtk bash scripts/archive-search.sh "" --open-only --json` passed and returned no open entries.
- `rtk python3 -m unittest discover -s tests` passed: `32` tests.
- `rtk bash scripts/check.sh` passed, including build, doctor, archive-check, governance report, unit tests, routing precedence, skill checks, smoke profiles, diff and drift.
