# Codex V2 资产管理手册

## 日常维护

1. 修改 `src/codex-home/` 中的人工资产，或修改 `manifests/*.json`。
2. 运行 `rtk bash scripts/build.sh --profile team-collab`。
3. 运行 `rtk bash scripts/doctor.sh --scope all`。
4. 若修改了 workflow、project template 或 overlay，运行 `rtk bash scripts/doctor.sh --scope governance`。
5. 运行 `rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json` 生成审计计划。
6. 运行 `rtk bash scripts/apply.sh --dry-run --no-build` 预览。
7. 确认后运行 `rtk bash scripts/apply.sh --profile team-collab`。
8. 发布前运行 `rtk bash scripts/check.sh`。

默认 apply 只自动覆盖“上次由本仓库注入且 live 端未被本机改过”的文件；像 `config.toml` 这类已发生本机漂移的文件会被保留，并继续由 `drift.sh` 报告。需要强制覆盖时显式加 `--overwrite`。

允许长期保留的 live 本机差异记录在 `manifests/policies.json` 的 `allowed_live_drift_paths`。当前 `config.toml` 允许漂移，用于保留本机项目 trust、TUI 状态和运行时 notice。

## Profile / Agent / Skill / Workflow 治理

本仓库把长期维护对象拆成六层：

- `profiles`：运行能力边界，例如 `minimal`、`solo-dev`、`team-collab`。
- `skills`：可复用操作能力，存放版本、来源、目标路径和启用 profile。
- `agents`：可用子代理或本地 agent 配置，按 profile 激活。
- `workflows`：把触发词、skill、agent、命令和验证命令串成可复用流程。
- `project_templates`：把不同项目路径映射到默认 profile、推荐 workflow 和归档主题。
- `overlays`：定义个人、本地、团队共享和发布场景的允许漂移与阻断路径。

常用治理命令：

```bash
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/governance-report.sh
rtk bash scripts/governance-report.sh --json
```

维护原则：

- 新增 skill 或 agent 后，先登记对应 manifest，再由 workflow 引用。
- workflow 只能引用已登记且拼写一致的 profile、skill 和 agent。
- project template 只能引用已登记 workflow，并明确默认 profile。
- overlay 的 `allowed_live_drift_paths` 不能覆盖 protected path，例如认证、session、日志、缓存、密钥和系统 skill。
- 团队共享或发布前优先使用 `team-shared` / `release-sanitized` 视角审查，个人本机状态只保留在 live 目录或 `personal-local` overlay。

## 脚本与 Python 入口规范

- 面向用户和 skill 的稳定入口统一放在 `scripts/*.sh`。
- Python 实现默认统一收敛到 `tools.codex_assets`，通过 `rtk python3 -m tools.codex_assets <subcommand>` 调用。
- `scripts/*.sh` 应只负责三件事：定位仓库根目录、注入 `PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"`、转发到模块入口。
- 除非是明确独立的单文件工具，否则不要新增直接执行 Python 文件路径的入口，例如 `rtk python3 "$ROOT/tools/foo.py"`。
- CLI 公共参数统一使用 `--root`；内部历史参数名如 `repo`，在 `tools.codex_assets.cli` 中做映射适配。
- README、skill、agent 和运维文档默认只引用 `scripts/*.sh`，不要把模块路径或 Python 文件路径暴露为正式入口。
- 新增或修改入口脚本后，至少从一个非仓库 `cwd`（例如 `/tmp`）执行一次 `--help` 或 `--dry-run`，验证入口不依赖当前工作目录。

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

建议在 preflight、session wrap 和 memory curation 中显式保留：

- `自动结晶 / crystallized insights`
- `未决张力 / open tensions`

当会话很长且噪音较多时，可使用 `local-context-curator` 做提炼，但最终归档与结论由主 agent 输出。

## 归档检索

现有知识沉淀默认不靠人工翻目录，可直接检索：

```bash
rtk bash scripts/archive-search.sh "context-preflight"
rtk bash scripts/archive-search.sh "token 效率" --limit 10
rtk bash scripts/archive-search.sh "memory-curator" --json
rtk bash scripts/archive-search.sh "token 优化" --topic diag-architecture --since 2026-05-01
rtk bash scripts/archive-search.sh "会话总结" --type session-wrap --tag research
```

默认搜索范围：

- `docs/archive/`
- `AGENTS.md`
- `src/codex-home/AGENTS.md`

需要时可用 `--include` 追加其他文本路径。默认索引位于 `.cache/archive-search.sqlite`，支持：

- `--topic`
- `--tag`
- `--type`
- `--since`
- `--until`
- `--rebuild-index`

## Codex 用量观察

第一版直接读取本机一手数据，不依赖 `status` 的刷新策略：

- 实时层：`~/.codex/sessions/**/*.jsonl` 中的 `token_count`
- 状态层：`~/.codex/state_5.sqlite` 中的 `threads` / `thread_goals`

常用入口：

```bash
rtk bash scripts/usage-report.sh
rtk bash scripts/usage-report.sh --json
rtk bash scripts/usage-tail.sh
rtk bash scripts/usage-tail.sh --once
rtk bash scripts/usage-tail.sh --interactive
```

说明：

- `usage-report` 输出当前活跃线程、top threads、今日累计和近 7 天累计。
- `usage-tail` 默认每 3 秒刷新一次终端面板。
- `usage-tail` 会提示两类风险：长线程累计过高、最近 token 增速过快。
- `usage-tail --interactive` 启动轻交互 TUI，支持 `1/2/3/a/r/p/+/-/j/k/h/q`。
- `usage-tail` 在 `summary` 视图额外给出 `Likely Cause`，用启发式方式提示当前最可能的高消耗来源。
- `usage-tail` 在 `summary` 视图额外给出 `Trim Mode`，将高风险状态直接映射为缩范围读取建议。
- 第一版不写入长期时序文件；如需沉淀，可后续增加 `docs/metrics/codex-usage.jsonl`。

## Codex 省 Token 操作规范

- 一个主题尽量一个线程；主题切换、目标变化或验收点完成后，优先收口再新开线程。
- 长线程达到高风险区后，优先执行 `context-preflight -> session-wrap -> archive-note -> memory-curator --dry-run`，不要继续无边界滚大上下文。
- 先定位再读取：优先 `rg` 缩小范围，再读命中文件片段，不直接全仓扫描。
- 控制工具输出：大日志、大 JSON、大 diff 默认先裁剪，只看关键窗口或关键字段。
- 非必要不并行：高耦合问题、单点 bug、核心文件集中修改时，优先单线程处理。
- 提问和任务定义尽量收敛：明确模块、文件、目标和验收标准，减少来回改口造成的重复消耗。
- 先用 `rtk bash scripts/usage-report.sh` 或 `rtk bash scripts/usage-tail.sh --once` 观察当前消耗，再决定是否需要压缩上下文或切线程。

### 分阶段回答压缩与输出裁剪

- 回答压缩默认只压缩表达噪音，不压缩必要思考；不要把 brainstorming、设计、计划、风险权衡一刀切压成极简输出。
- `brainstorming` / `writing-plans` 阶段允许中等展开，但仍应避免寒暄、重复背景、同义改写和无行动价值的延展说明。
- `implementation` / `debugging` 阶段默认低噪音，优先输出：当前动作、证据、验证、阻塞、下一步。
- `verification` / `wrap-up` / `archive` 阶段默认最严格压缩，只保留结论、验证结果、风险和后续动作。
- 默认压缩对象：过渡语、寒暄、重复解释、大段工具输出复述、已确认事实的重复说明。
- 默认保留对象：方案对比、设计边界、关键权衡、风险分析、计划依赖、验收标准。
- 当 `usage-tail` 状态进入 `HOT` / `CRITICAL` 时，即使还在设计阶段，也只允许“受控展开”：讲清关键取舍，不做无边界铺陈。
- 输出裁剪也按阶段处理：探索/设计阶段可保留支撑结论的必要证据；实现和验证阶段默认先给摘要、关键窗口、关键字段，需要时再展开全文。
- 推荐读取范式：
  - 定位优先：`rg`
  - 片段优先：`sed -n`
  - 日志窗口优先：`tail`
  - diff 先摘要：`git diff --stat`
  - 结构化数据先筛字段，再决定是否展开全文

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
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope live
rtk bash scripts/governance-report.sh --json
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
