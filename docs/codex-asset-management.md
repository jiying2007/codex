# Codex V2 资产管理手册

## 日常维护

1. 修改 `src/codex-home/` 中的人工资产，或修改 `manifests/*.json`。
2. 运行 `rtk bash scripts/build.sh --profile team-collab`。
3. 运行 `rtk bash scripts/doctor.sh --scope all`。
4. 运行 `rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json` 生成审计计划。
5. 运行 `rtk bash scripts/apply.sh --dry-run --no-build` 预览。
6. 确认后运行 `rtk bash scripts/apply.sh --profile team-collab`。
7. 发布前运行 `rtk bash scripts/check.sh`。

## 新增普通资产

普通资产放入 `src/codex-home/` 对应目录。如果是新的顶层目录，需要加入 `manifests/assets.json` 的 `copy_roots`。

不要把以下内容放入源资产：

- `skills/.system/`
- `auth.json`
- `sessions/`
- `log/` 或 `logs_*.sqlite*`
- `state_*.sqlite*`
- `cache/`
- `tmp/`
- `mcp/secrets/`
- `config.local.*`
- `*.secret`、`*.key`、`*.pem`

## Skill 接入

扫描运行目录：

```bash
rtk bash scripts/scan-skills.sh --dry-run
rtk bash scripts/scan-skills.sh
```

审核候选目录：

```text
inbox/skills/<name>/<timestamp>/
```

归档：

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

第三方目录也用同一入口：

```bash
rtk bash scripts/promote-skill.sh /path/to/third-party-skill --version 1.0.0 --tags third-party
```

归档脚本会更新 `manifests/skills.json`，下一次 build 会生成 `skills/registry.csv` 与激活 symlink。

## 知识材料归档

当会话总结、调研笔记、排障结论或外部材料值得长期复用时，先脱敏，再归档到 `docs/archive/`：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name --dry-run
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name --title "Readable Title"
```

目录也可以归档：

```bash
rtk bash scripts/archive-note.sh /path/to/note-dir --topic topic-name
```

归档规则：

- 默认复制，保留来源；`--move` 才移动来源。
- 每条材料生成独立 `.meta.json`，主题目录自动维护 `index.md`。
- 禁止归档 `.codex` runtime、session、日志、cache、tmp、密钥、`auth.json` 和 protected paths。
- `src/codex-home/control/` 只保留运行边界配置，不再承载 archives、knowledge、roles 或 workflows。

## 记忆周期整理

`memory-curator` 用于周期性整理 `~/.codex/memories`、项目 `AGENTS.md`、日报、会话总结、排障结论和决策记录。

默认只生成审计报告，不直接改 memory 或 AGENTS：

```bash
rtk bash scripts/curate-memory.sh --dry-run
rtk bash scripts/curate-memory.sh
```

报告位置：

```text
docs/archive/memory-curation/<timestamp>-memory-curation.md
```

需要候选 memory 时显式开启：

```bash
rtk bash scripts/curate-memory.sh --write-memory-candidate
```

候选文件写入 `~/.codex/memories/.codex/curation-inbox/`，仍需人工审核后再提升为正式 memory 或 AGENTS 规则。

`memory-curator` 兼容 `codex-agent-mem` 导出材料，但不要求安装该工具。存在以下路径时会作为候选输入扫描：

```text
~/.codex_agent_mem/
~/.codex/memories/.codex-agent-mem/
docs/archive/codex-agent-mem/
```

报告会将建议分为：

- `promote-to-agents`
- `write-to-codex-agent-mem`
- `archive-only`
- `drop-or-review`

记忆治理分三阶段：

- Phase 1 报告归档：默认阶段，只生成 `docs/archive/` 归档和 memory-curator 审计报告，不写入任何长期 memory。
- Phase 2 手动写入：先由 `memory-curator` 生成候选，再人工确认是否写入 `~/.codex/memories` 或 codex-agent-mem note/snapshot。
- Phase 3 任务闭环：会话开始读取可用 context pack，会话结束执行 `knowledge-archive + memory-curator`，重要决策人工提升到 `AGENTS.md` 或 memory。

## 上下文压缩与会话接力

`context-compress-handoff` 用于在主动压缩上下文前做快速收口，固定输出 preflight、会话总结归档和恢复提示。

常用入口：

```bash
rtk bash scripts/context-preflight.sh
```

建议闭环：

```bash
rtk bash scripts/context-preflight.sh
rtk bash scripts/archive-note.sh <session-summary.md> --topic session-wrap --title "<title>"
rtk bash scripts/curate-memory.sh --dry-run
```

当会话很长且噪音较多时，可使用 `local-context-curator` 做提炼，但最终归档与结论由主 agent 输出。

## 多源搜索能力

`multi-search-engine` 按 v2 skill 方式接入，只在 `team-collab` profile 激活。它用于需要外部证据的问题，例如当前信息、资料核验、标准/库/工具对比和多来源交叉验证。

约束：

- 不作为主动 agent 常驻。
- 不处理本地代码库问题，本地问题优先读仓库。
- 结论必须附来源链接、日期判断、置信度与不确定性。
- OpenAI 产品/API 问题优先官方 OpenAI 文档。

## 浏览器读取能力

`browser-reader` 与 `agent-browser` 用于普通 HTTP 抓取不可达、需要 JS 渲染或用户手动验证后的单页读取。默认只在 `team-collab` profile 激活。

边界：

- 只读读取用户授权页面。
- 不自动登录、不提交表单。
- 不绕过验证码或安全验证。
- 微信公众号等安全验证页只能提示用户手动完成验证，再整理可见内容。
- 需要长期保存时，输出再交给 `knowledge-archive`。

## 发布到运行目录

默认注入不会覆盖已有普通文件：

```bash
rtk bash scripts/apply.sh --profile team-collab
```

需要覆盖时：

```bash
rtk bash scripts/apply.sh --profile team-collab --overwrite
```

覆盖备份位于 `.backups/apply/<timestamp>/`。

## 排障

```bash
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope live
rtk bash scripts/diff.sh
rtk bash scripts/drift.sh
rtk bash scripts/check.sh
```

## 沙箱能力与兼容

平台上可能存在旧版 `bwrap`（如仅支持 `--ro-bind-try`，不支持 `--perms`/`--size`）。v2 提供两层支持：

1. 能力检查：

```bash
rtk bash scripts/check-bwrap-capability.sh
```

2. 自适应运行（自动降级参数）：

```bash
rtk bash scripts/run-sandbox.sh -- /bin/true
```

严格模式（发布门禁）：

```bash
rtk bash scripts/check-bwrap-capability.sh --require-modern
REQUIRE_MODERN_BWRAP=1 rtk bash scripts/check.sh
```

说明：

- 默认 `scripts/check.sh` 只记录 bwrap 能力并告警，不阻断发布。
- 设置 `REQUIRE_MODERN_BWRAP=1` 后，若缺少 `--perms`/`--size` 或运行态不满足，将直接失败。

若 `diff.sh` 报告普通文件不同，先判断目标文件是否为本机私有修改；若需要仓库版本覆盖，再使用 `apply.sh --overwrite`。

若 `drift.sh` 报告 changed，表示 live 中受管理文件偏离了上次 apply 时的 managed state；先确认是否为人工修改，再决定重新 apply 或将修改提升回源资产。

## 回滚

如果一次 apply 后需要撤回，使用当次保存的 apply plan：

```bash
rtk bash scripts/rollback.sh --plan build/apply-plan.live.json --dry-run
rtk bash scripts/rollback.sh --plan build/apply-plan.live.json
```

rollback 只处理 plan 中记录的 copy/overwrite 项：新增文件会移除，被覆盖文件会从备份恢复。
