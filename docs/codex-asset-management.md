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

Codex CLI 配置字段、profile 策略和升级核验流程见 `docs/codex-cli-config-guide.md`。修改 `config*.toml` 时优先按该指南核对官方文档和本机 `codex --strict-config doctor` 结果。


## Git 管理边界

`~/codex` 是声明式交付仓库，必须记录可复现的构建输入；`~/.codex` 是运行态接收目录，不纳入 Git 管理。

应纳入 Git 的内容：

- `manifests/*.json`：profile、agent、skill、workflow、workflow recipe、automation、subagent contract、memory candidate、lock、change set 与 MCP 声明。
- `src/codex-home/vendor/agents/agent-dev-kit/<version>/`：从 `agent-dev-kit` 导入并由 manifest 引用的版本化 agent 资产。
- `src/codex-home/vendor/skills/adk-*/<version>/`：从 `agent-dev-kit` 导入并由 manifest 引用的版本化 skill 资产。
- 其他被 `scripts/build.sh` 明确消费的声明式源文件。

不得纳入 Git 的内容：

- `~/.codex` 运行态目录及其认证、session、日志、缓存、密钥和本机私有配置。
- `build/`、`.cache/`、`scratch/`、`inbox/`、`.backups/` 等可重建或本机临时目录。
- `/tmp/adk-codex-handoff`、`CODEX_HANDOFF.md`、`manifest-fragments/` 等导出包辅助文件。
- apply plan 和运行日志，除非作为脱敏审计证据单独归档到 `docs/archive/`。

处理 `agent-dev-kit` 应用时，先将 handoff 合并到 `manifests/` 与 `src/codex-home/vendor/`，再运行 `build -> doctor -> plan/dry-run -> apply -> drift/diff -> check`。验证通过后只提交上述声明式资产，不提交运行态或临时产物。

## Profile / Agent / Skill / Workflow 治理

本仓库把长期维护对象拆成六层：

- `profiles`：运行能力边界，例如 `minimal`、`solo-dev`、`team-collab`。
- `skills`：可复用操作能力，存放版本、来源、目标路径和启用 profile。
- `agents`：可用子代理或本地 agent 配置，按 profile 激活。
- `workflows`：把触发词、skill、agent、命令和验证命令串成可复用流程。
- `workflow_recipes`：把 workflow 的上下文输入、完成标准、审查产物和失败模式固化为可审计契约。
- `automations`：只登记等待型或定时任务的只读/报告边界，不直接创建调度器或后台执行器。
- `subagent_contracts`：约束子代理读写范围、禁止路径、sandbox 和输出契约。
- `memory_candidates`：登记长期记忆候选、人工审查、secret scan 和提升门禁。
- `eval_suites`：登记 routing、governance、completion 和 prompt eval 的 cases、通过率、负例和 promotion gate。
- `cli_command_contracts`：登记 slash command 控制面的输入、允许动作、禁止动作、输出和验证契约。
- `guidance_promotions`：登记从会话、归档、manifest、测试或官方资料提升到长期规则、skill、archive 或 memory 的审查路径。
- `goal_templates`：登记 weak、strong、continuous 目标模板和验证/产物契约。
- `prompt_experiments`：登记 AGENTS、skill 和 prompt 指导规则实验、样例、grader、人工评审和回退。
- `trace_eval_contracts`：登记过程轨迹评分契约、必要事件、禁止事件、rubric 和最低分。
- `context_state_contracts`：登记 stable、dynamic、evidence 和 excluded context 的状态契约。
- `automation_run_records`：登记 automation 单次运行记录模板、triage、清理、保留和人工审查状态。
- `skill_mcp_dependencies`：登记 skill 对 MCP server/tool 的依赖、访问模式、审批、fallback 和禁止动作。
- `slash_command_runtime_audits`：登记 slash command 运行态审计事件、证据、保留策略和禁止动作。
- `official_docs_freshness_gates`：登记官方文档来源、检索时间要求、审查状态、过期策略和回退方式。
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

## Codex 工作模型

`docs/codex-operating-model.md` 约束日常使用层：常驻线程、强目标、实时干预/任务排队、可审查产物、记忆边界、自动化边界和 MCP 治理。

维护原则：

- 一个线程服务一个长期职责；跨职责切换前先 `context-preflight`。
- 强目标必须包含成功标准、验证命令和可审查产物；没有验证机制的任务只能标为探索。
- UI、数据、文档、代码和高风险变更优先输出可审查产物，而不是只输出过程描述。
- 等待型或周期性自动化必须限定数据源、频率、停止条件和人工审批点。
- 可复用 workflow 的操作契约进入 `manifests/workflow_recipes.json`；周期性或等待型任务先进入 `manifests/automations.json`，默认保持禁用或 report-only。
- 并行子代理的边界进入 `manifests/subagent_contracts.json`；长期记忆候选进入 `manifests/memory_candidates.json`，不得绕过审查直接写 memory。
- MCP server 先进入 `manifests/mcp_servers.json`，再由 build 渲染到 `config.toml`；启用前必须有 transport、权限边界、凭证边界、工具清单、可执行 deny-path、日志脱敏、smoke 和回滚方式。
- `manifests/mcp_servers.json` 只存声明和空 env key，不存真实 token；`tools.codex_assets` 会在 build 时把匹配 profile 的条目渲染到 `config.toml`。
- eval、slash command、guidance promotion、goal template、prompt experiment、trace eval、context state contract、automation run record、skill MCP dependency、slash runtime audit 和 official docs freshness gate 也属于治理输入。新增或修改后必须运行 `doctor --scope governance`、相关单元测试和 `check.sh`。
- 上下文压缩遵循 `docs/context-layout.md`，把 stable、dynamic、evidence 和 excluded context 分开，避免把短期工作区状态提升为长期规则。

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

本地沉淀和 Chronicle 派生 skill 是持续迭代的声明式资产。`adk-*`、Superpowers、OpenAI、Composio、Anthropic 等外部导入 skill 默认是版本化镜像，通过上游更新后重新导入，不在本仓直接迭代其正文。完整策略见 `docs/skill-lifecycle.md`。

维护边界：

- 本地 / Chronicle 派生 skill：`description` 负责触发，`SKILL.md` body 只保留执行必须知道的流程、边界和输出契约。
- 本地 / Chronicle 派生 skill：manifest 必须可筛选，至少包含 `owner=local`、`source_repo=local/codex` 和 `tags=["local", ...]`；Chronicle 派生项额外包含 `chronicle-derived`。
- Chronicle 派生 skill：`SKILL.md` frontmatter 和 README 使用 `origin: local-chronicle-derived` / `Lifecycle: iterative-local` 做人工识别。
- 本地 / Chronicle 派生 skill：细节资料进入 `references/`，确定性重复操作进入 `scripts/`，长证据进入 `docs/archive/`。
- 本地 / Chronicle 派生 skill：已提交并投入使用后，优先通过新版本目录迭代，再更新 `manifests/skills.json`。
- 外部导入 skill：优先更新上游源或导入新版本；不得把本地需求直接改进外部 skill 正文形成隐式 fork。
- routing 问题优先改 `description` 或 `manifests/workflows.json`，不要把大量触发词堆进正文。

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
