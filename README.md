# Codex V2 资产仓库

`~/codex` 是本机 Codex CLI 的声明式资产仓库。v2 不再把仓库目录直接当成 `~/.codex` 镜像，而是采用清晰的三层模型：

```text
src/codex-home/      # 人工维护资产源
manifests/           # 声明式 SSOT：资产、profile、skill、agent、workflow、项目模板、overlay
build/codex-home/    # 生成产物，可删除重建，不纳入 git
```

注入链路固定为：

```text
src/codex-home + manifests -> build/codex-home -> ~/.codex
```

`~/.codex/skills/.system`、认证、session、日志、缓存、密钥和本机私有配置始终由运行目录优先，本仓库不跟踪、不复制、不覆盖。

## 常用命令

```bash
# 生成默认 token-lean profile 的可注入产物
rtk bash scripts/build.sh

# 分别检查 source、build 和治理关系
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope governance

# build 与 live 已使用同一 profile 时做完整体检
rtk bash scripts/doctor.sh --scope all

# 输出 profile、skill、agent、workflow、项目模板和 overlay 关系
rtk bash scripts/governance-report.sh
rtk bash scripts/governance-report.sh --json

# 生成机器可读 apply plan；清理上一个 profile 遗留的受管入口
rtk bash scripts/plan.sh --target ~/.codex --prune-stale --output build/apply-plan.json

# 预览并应用同一份计划
rtk bash scripts/apply.sh --plan build/apply-plan.json --dry-run
rtk bash scripts/apply.sh --plan build/apply-plan.json

# 强制覆盖已有普通文件，覆盖前备份
rtk bash scripts/apply.sh --prune-stale --overwrite

# 对比 build 与 ~/.codex
rtk bash scripts/diff.sh

# 检查 live 是否偏离上次 managed state
rtk bash scripts/drift.sh

# 检查 bwrap 新沙箱参数能力（默认告警）
rtk bash scripts/check-bwrap-capability.sh

# 强制要求满足新沙箱参数（不满足返回失败）
rtk bash scripts/check-bwrap-capability.sh --require-modern

# 用自适应参数执行 bwrap 沙箱命令
rtk bash scripts/run-sandbox.sh -- /bin/true

# 备份当前 ~/.codex
rtk bash scripts/backup.sh

# 归档一份长期知识材料到 Knowledge Hub
rtk bash scripts/archive-note.sh /path/to/note.md --topic embedded-debug

# 周期性整理 memories、AGENTS 与归档知识，默认只生成审计报告
rtk bash scripts/curate-memory.sh

# 搜索归档知识与 AGENTS 规则
rtk bash scripts/archive-search.sh "context-preflight"

# 上下文压缩前 90 秒 preflight（会话接力模板）
rtk bash scripts/context-preflight.sh

# 查看会话连续性下一步提醒
rtk bash scripts/session-coach.sh
rtk bash scripts/session-coach.sh --deep
rtk bash scripts/session-coach.sh --deep --top 5
rtk bash scripts/session-coach.sh --event final --deep
rtk bash scripts/session-coach.sh --event commit --deep --fail-on high
rtk bash scripts/session-coach.sh --reset-state
rtk bash scripts/session-coach.sh --ack ARCHIVE_REVIEW

# final / commit / apply 前门禁 wrapper
rtk bash scripts/final-ready.sh
rtk bash scripts/commit-ready.sh
rtk bash scripts/apply-ready.sh
SESSION_COACH_FAIL_ON=high rtk bash scripts/commit-ready.sh

# 查看当前线程和近 7 天用量
rtk bash scripts/usage-report.sh

# 实时刷新终端用量面板
rtk bash scripts/usage-tail.sh --once

# 从低上下文 catalog 查询长尾 skill；命中后再读取返回的 load_path
rtk bash scripts/skill-search.sh --query "多源搜索和交叉验证" --summary-json

# 从指定 apply plan 回滚
rtk bash scripts/rollback.sh --plan build/apply-plan.json --dry-run
rtk bash scripts/rollback.sh --plan build/apply-plan.json

# 端到端 smoke
rtk bash tests/smoke.sh

# 发布前统一检查
rtk bash scripts/check.sh
```

## Profile 选择与切换

Profile 决定 build 和 live 中常驻的受管 Skill、Custom Agent、Workflow 以及并行上限。它不删除 `src/codex-home/vendor/` 中的能力实体，也不触碰 `~/.codex/skills/.system`。当前默认 profile 是 `token-lean`，由 `manifests/assets.json:default_profile` 声明。

### 五个 Profile 的区别

下表是当前 manifest 的实际绑定数量；“Skill”和“Agent”只统计本仓受管资产，不包含 Codex 内置 `.system` Skill 和平台默认 Agent。

| Profile | 常驻 Skill | Custom Agent | Workflow | 并行 / 深度 | Catalog | 适用场景 |
|---|---:|---:|---:|---:|---|---|
| `minimal` | 1 | 0 | 0 | 2 / 2 | eager | 极简运行和资产 smoke；当前只常驻 `caveman` |
| `solo-dev` | 38 | 5 | 5 | 4 / 3 | eager | 个人深度开发、嵌入式专项、总结归档和本地工具 |
| `token-lean` | 11 | 0 | 5 | 4 / 3 | lazy | 默认日常配置；常驻 ADK 核心路由，长尾 Skill 延迟发现 |
| `team-collab` | 70 | 16 | 14 | 6 / 4 | eager | 完整 ADK、多 Agent、复杂研发、研究、发布与治理 |
| `superpowers-compat` | 13 | 0 | 1 | 4 / 3 | eager | 显式 Superpowers 兼容、迁移回归或 ADK 无等价能力时使用 |

选择建议：

- 日常编码、调试、审查：优先 `token-lean`。
- 单人嵌入式专项、归档和工具开发：使用 `solo-dev`。
- 多 Agent 或需要完整 catalog：使用 `team-collab`。
- 极低上下文实验：使用 `minimal`。
- 只有用户明确点名、做兼容回归或 ADK 不适用时才使用 `superpowers-compat`。

Profile 中的 `enabled_mcp_groups` 是能力声明；当前 `github`、`openaiDeveloperDocs` 和 `figma` MCP 条目仍为 `enabled=false`，切换 profile 不会自动启用外部服务或凭证访问。

### 查看当前 Profile

```bash
rtk bash scripts/doctor.sh --scope live
```

输出中的 `PROFILE=<name>` 来自 `~/.codex/control/state/active-profile.env`。当前线程已经注入的 catalog 不会热刷新；切换成功后需要新开 Codex 线程。

### 一条命令快速切换

下面以 `team-collab` 为例；把 profile 名替换为 `minimal`、`solo-dev`、`token-lean` 或 `superpowers-compat` 即可：

```bash
rtk bash scripts/apply.sh \
  --profile team-collab \
  --target ~/.codex \
  --prune-stale \
  --plan-out build/apply-plan.switch.json
```

这条命令会依次 build、生成计划并应用到 live，同时保存可审计的 apply plan。它适合已经理解变更范围、希望快速切换的场景。

切换后验证：

```bash
rtk bash scripts/doctor.sh --scope all
rtk bash scripts/diff.sh --target ~/.codex
rtk bash scripts/drift.sh --target ~/.codex
```

### 先审计再切换

生产性工作或从大 profile 切到小 profile 时，优先使用以下流程：

```bash
# 1. 只构建目标 profile，不修改 live
rtk bash scripts/build.sh --profile team-collab

# 2. 校验 source、目标 build 和治理引用
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope governance

# 3. 生成包含 stale 清理动作的计划
rtk bash scripts/plan.sh \
  --target ~/.codex \
  --prune-stale \
  --output build/apply-plan.switch.json

# 4. 预览并应用完全相同的计划
rtk bash scripts/apply.sh --plan build/apply-plan.switch.json --dry-run
rtk bash scripts/apply.sh --plan build/apply-plan.switch.json

# 5. 验证 build、live 和 managed state 一致
rtk bash scripts/doctor.sh --scope all
rtk bash scripts/diff.sh --target ~/.codex
rtk bash scripts/drift.sh --target ~/.codex
```

切换时必须理解以下边界：

1. `build.sh --profile ...` 只更新 `build/codex-home`，不会切换 `~/.codex`。
2. 从 `team-collab` 切到较小 profile 必须使用 `--prune-stale`，否则旧的受管 Skill/Agent 入口可能残留。
3. 不要直接使用 `apply.sh --dry-run --profile ...` 预览新 profile；当前 dry-run 不会自动重建，必须先显式 build。
4. 切换过程中 build 和 live 暂时不同，因此 apply 前的 `doctor.sh --scope all` 可能报告预期的 profile drift；此时分别检查 `repo`、`build` 和 `governance`，应用后再检查 `all`。
5. `scripts/check.sh` 默认重建 `token-lean`；同轮已有 build/plan 时可用 `--no-build --plan <path>`，source fingerprint、build receipt 或 target 不一致会失败。非默认 live profile 使用上面的 `doctor`、`diff` 和 `drift` 验收。
6. `build.sh` 会更新 `manifests/lock.json`，临时切换也可能让 Git 工作区出现 lockfile 变更。

### 回切与回滚

最可靠的回切方式是重新 apply 原 profile，例如回到默认配置：

```bash
rtk bash scripts/apply.sh \
  --profile token-lean \
  --target ~/.codex \
  --prune-stale \
  --plan-out build/apply-plan.switch-back.json
```

如果一次 apply 中途失败，或需要撤销该计划记录的 copy、overwrite 和 delete 动作，可使用当次 plan：

```bash
rtk bash scripts/rollback.sh --plan build/apply-plan.switch.json --dry-run
rtk bash scripts/rollback.sh --plan build/apply-plan.switch.json
```

rollback 恢复的是 live 文件；随后应重新 build 原 profile，并运行 `doctor --scope all`、`diff` 和 `drift`，确保 build 与 live 再次一致。

## 目录职责

| 路径 | 职责 |
|------|------|
| `src/codex-home/` | 手工维护的 Codex Home 资产源，不包含系统 skill、运行态和密钥 |
| `manifests/assets.json` | 源目录、构建目录、默认 profile、复制根 |
| `manifests/profiles.json` | profile 元数据 |
| `manifests/skills.json` | skill 版本、来源、启用 profile 与激活路径 |
| `manifests/agents.json` | agent 版本、来源、启用 profile 与激活路径 |
| `manifests/workflows.json` | workflow 触发词、profile、skill、agent、命令与验证闭环 |
| `manifests/workflow_recipes.json` | workflow 的上下文输入、完成标准、审查产物和失败模式 |
| `manifests/automations.json` | 等待型/定时任务候选的只读边界、审批策略和停止条件 |
| `manifests/mcp_servers.json` | MCP server 声明、空 env key、readiness 和回滚边界 |
| `manifests/subagent_contracts.json` | 子代理读写范围、禁止路径、sandbox 和输出契约 |
| `manifests/memory_candidates.json` | 长期记忆候选、人工审查、secret scan 与提升门禁 |
| `manifests/eval_suites.json` | routing、governance、completion 等 eval 契约和 promotion gate |
| `manifests/cli_command_contracts.json` | slash command 的输入、允许动作、禁止动作、输出和验证契约 |
| `manifests/guidance_promotions.json` | 从会话、归档、manifest 或官方资料提升到 AGENTS/skill/archive/memory 的门禁 |
| `manifests/goal_templates.json` | weak、strong、continuous 目标模板及验证/产物契约 |
| `manifests/prompt_experiments.json` | AGENTS、skill 和 prompt 指导规则实验、grader、人工评审和回退契约 |
| `manifests/trace_eval_contracts.json` | 过程轨迹评分契约，约束必要事件、禁止事件、rubric 和最低分 |
| `manifests/context_state_contracts.json` | stable/dynamic/evidence/excluded context 的可验证状态契约 |
| `manifests/automation_run_records.json` | automation 单次运行记录模板、triage、清理、保留和人工审查状态 |
| `manifests/skill_mcp_dependencies.json` | skill 对 MCP server/tool 的依赖、权限、禁止动作、审批和 fallback |
| `manifests/slash_command_runtime_audits.json` | slash command 运行态审计事件、证据、保留策略和禁止动作 |
| `manifests/official_docs_freshness_gates.json` | 官方文档来源 URL、检索时间、审查状态、过期和回退门禁 |
| `manifests/project-templates.json` | 项目类型到默认 profile、workflow 与归档主题的映射 |
| `manifests/overlays.json` | 个人、本地、团队和发布场景的允许漂移与阻断路径 |
| `manifests/policies.json` | protected paths 与 apply 策略 |
| `manifests/lock.json` | build 生成的 vendor 锁定摘要 |
| `build/codex-home/` | `build.sh` 生成的可注入产物 |
| `~/knowledge-hub/domains/codex/archive/codex-archive/` | 旧归档区，只读历史来源；新增长期知识进入 `~/knowledge-hub` |
| `inbox/skills/` | 未审核 skill 候选区，默认不纳入 git |
| `tools/codex_assets/` | Python CLI 核心实现 |
| `schemas/` | manifest schema 文档与校验依据 |

## Skill 生命周期

详细使用、迭代和长期维护规则见 `docs/skill-lifecycle.md`。日常原则是：通过自然语言或显式技能名触发；重复三次以上且有证据的本地流程再沉淀为 local/Chronicle-derived skill；使用 manifest 的 `local` / `chronicle-derived` 标签识别来源，不通过改名牺牲任务语义；`adk-*`、Superpowers 和其他第三方 skill 通过上游版本重新导入，不在本仓直接迭代正文。

```bash
# 扫描运行目录中真实存在且未登记的 skill
rtk bash scripts/scan-skills.sh --dry-run
rtk bash scripts/scan-skills.sh

# 审核后归档为正式 vendor 资产
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0

# 重新构建、体检、注入
rtk bash scripts/build.sh
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/plan.sh --target ~/.codex --prune-stale --output build/apply-plan.json
rtk bash scripts/apply.sh --plan build/apply-plan.json --dry-run
rtk bash scripts/apply.sh --plan build/apply-plan.json
```

正式 skill 存放在 `src/codex-home/vendor/skills/<name>/<version>/`，激活入口由 `build.sh` 在 `build/codex-home/skills/<name>` 生成相对 symlink。不要把第三方 skill 直接放进 `src/codex-home/skills/`。

## 工作模型

`docs/codex-operating-model.md` 定义本机 Codex 的常驻线程、强目标、实时干预/任务排队、可审查产物、记忆边界、自动化边界和 MCP 治理规则。它是 `AGENTS.md` 的操作层补充：规则仍以 `AGENTS.md` 为准，具体工作台和收口模板参考该文档。

## 治理模型

profile、agent、skill、workflow、项目模板和 overlay 分层管理：

- profile 决定当前启用的能力集合；默认 `token-lean` 只常驻核心路由，`team-collab` 保留完整 catalog，`minimal`、`solo-dev` 用于显式场景。
- skill 与 agent 是可注入能力资产，由 `manifests/skills.json` 和 `manifests/agents.json` 记录版本、来源和 profile 绑定。
- workflow 是可复用工作流编排，显式声明触发词、依赖 skill、依赖 agent、入口命令和验证命令。
- workflow recipe 把 workflow 的输入、完成标准、审查产物和失败模式变成可评测契约。
- automation 只登记候选任务的只读/报告边界、审批策略、run lifecycle、清理/保留策略和停止条件，不直接启动后台调度。
- MCP server 默认可以声明但禁用，支持 `stdio` 和 `http` transport；官方 OpenAI Docs MCP 使用 `openaiDeveloperDocs` + `https://developers.openai.com/mcp`，启用前必须补齐 readiness、凭证边界和 smoke 证据。
- subagent contract 约束并行子代理的读写范围、禁止路径、sandbox、最大并行和输出格式。
- memory candidate 只记录候选和提升门禁，不直接写入 `~/.codex/memories`。
- eval suite 把 routing、governance、completion 和 prompt 行为固化为可复跑的测试契约。
- CLI command contract 约束 `/goal`、`/review`、`/compact` 等控制面的输入、输出、禁止动作和验证要求。
- guidance promotion 定义从资料或会话经验提升到长期规则、skill、archive 或 memory 的审查和回退路径。
- goal template 定义 weak、strong、continuous 目标的必填字段、验证契约、产物契约和停止条件。
- prompt experiment 用小规模样例、grader、人工评审和 rollback 验证 AGENTS、skill 或 prompt 指导规则变更。
- trace eval contract 把“过程是否可靠”纳入评分，要求必要事件、禁止事件、rubric 权重和最低通过分。
- context state contract 把上下文分层从文档约定提升为可校验契约，避免 dynamic/excluded context 进入长期规则。
- automation run record 只记录单次运行 triage、清理、保留、人工审查和禁止动作，不启动调度器。
- skill MCP dependency 把 skill 和 MCP server/tool 的读写边界、审批、fallback 和禁止动作显式化。
- slash command runtime audit 把 `/goal`、`/review`、`/compact` 等控制面动作的运行态事件、证据和保留策略纳入治理。
- official docs freshness gate 要求官方资料提升前具备 source URL、retrieved_at、review_status、expires_at、stale action 和 rollback。
- project template 用路径模式把不同项目类型映射到默认 profile、推荐 workflow 和归档主题。
- overlay 约束个人、本地、团队共享和发布场景下哪些 live 差异允许存在，哪些路径必须阻断。

治理层不直接写入 `~/.codex`；它提供可审计的能力关系图。修改治理 manifest 后运行：

```bash
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/governance-report.sh --json
rtk bash scripts/check.sh
```

## 知识沉淀

运行中产生的总结、调研、排障记录和外部资料，默认不进入 `src/codex-home/` 或本仓 `~/knowledge-hub/domains/codex/archive/codex-archive/`，而是先脱敏、定题后归档到 `~/knowledge-hub/domains/codex/archive/<topic>/`：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name --title "Readable Title"
rtk bash scripts/archive-note.sh /path/to/note-dir --topic topic-name --description "why this matters"
```

归档默认复制来源，不删除原文件；使用 `--move` 才移动。脚本会拒绝归档 Codex 运行态、密钥、日志、session、cache、`auth.json` 和旧 v2 control 知识态目录。旧 Codex archive 历史来源不再作为新增归档入口。

可直接检索长期沉淀与规则：

```bash
rtk bash scripts/archive-search.sh "context-preflight"
rtk bash scripts/archive-search.sh "token 效率" --limit 10
rtk bash scripts/archive-search.sh "memory-curator" --json
rtk bash scripts/archive-search.sh "token 优化" --topic diag-architecture --since 2026-05-01
rtk bash scripts/archive-search.sh "会话总结" --type session-wrap --tag research
```

- `archive-search` 默认在 `.cache/archive-search.sqlite` 维护轻量索引。
- 支持 `--topic`、`--tag`、`--type`、`--since`、`--until`、`--rebuild-index` 做 metadata 过滤与索引控制。

## 用量观察

第一版不依赖 `status`，直接读取本机运行数据：

- `~/.codex/sessions/**/*.jsonl` 中的 `token_count`
- `~/.codex/state_5.sqlite` 中的 `threads` / `thread_goals`

```bash
rtk bash scripts/usage-report.sh
rtk bash scripts/usage-report.sh --json
rtk bash scripts/usage-tail.sh
rtk bash scripts/usage-tail.sh --once
rtk bash scripts/usage-tail.sh --interactive
rtk bash scripts/usage-tail.sh --view threads
rtk bash scripts/usage-tail.sh --view trends
```

默认会提示两类风险：

- 长线程风险：当前线程累计 token 过高
- 高增速风险：最近一段时间 token 增长过快

显示优化：

- 终端面板中的 token 数值统一按 `M` 显示
- 额外展示 `Cache Hit`、`Last In Ctx`、`Think Ratio`、`Live Rate`
- 额外展示 `Top Models`、`Top Repos`、`Recent 30m`
- 额外展示 `5m / 15m / 30m` 三档速率
- 默认 `summary` 视图压成单屏；可切换 `threads` / `trends`
- 默认 `summary` 视图会给出 `Status`（`CRITICAL/HOT/WATCH/STABLE`）以及最优先的 `Alerts/Next Action`
- 默认 `summary` 视图会给出 `Likely Cause`，用启发式方式说明当前最可能的高消耗来源
- 默认 `summary` 视图会给出 `Trim Mode`，直接提示当前应采用的缩范围读取范式
- `--interactive` 会启动轻交互 TUI，支持 `1/2/3/a/r/p/+/-/j/k/h/q`
- `threads` 视图支持 `s` 切换排序：`updated -> tokens -> model -> repo`
- `--interactive` 需要真实 TTY，不能在管道或非终端环境下运行

可配阈值：

```bash
rtk bash scripts/usage-tail.sh --warn-thread-tokens 30000000
rtk bash scripts/usage-tail.sh --top-models 3 --top-repos 3
rtk bash scripts/usage-tail.sh --interactive
rtk bash scripts/usage-tail.sh --view summary
rtk bash scripts/usage-tail.sh --view threads
rtk bash scripts/usage-tail.sh --view threads --thread-sort tokens
rtk bash scripts/usage-tail.sh --view trends
rtk bash scripts/usage-tail.sh --view auto
```

## 回答压缩与输出裁剪边界

- 回答压缩默认只压缩表达噪音，不压缩必要思考。
- `brainstorming` / `writing-plans` 保留方案对比、边界、风险与推荐，不做无边界铺陈。
- `implementation` / `debugging` 默认低噪音，优先讲动作、证据、验证、阻塞。
- `verification` / `wrap-up` / `archive` 默认最严格压缩，只保留结论、结果、风险和后续动作。
- 输出裁剪也分阶段：设计阶段保留必要证据，实现与验证阶段默认先给摘要、关键字段和关键窗口。
- `usage-tail` 在高风险状态下会给出 `Trim Mode`，常见动作包括：
  - 只保留定向 `rg`
  - 只读局部 `sed -n`
  - 日志仅看短窗口 `tail`
  - 大 diff 先看 `--stat`
  - 大 JSON 只筛关键字段
- `Likely Cause` 是启发式归因，不是精确审计；它用于提示最可能的高消耗模式，例如长线程滚上下文、大读入负载、扩范围扫描、重复背景重喂。

## 设计约束

1. `manifests/*.json` 是能力编排的唯一事实源。
2. `src/codex-home/` 只保存可维护资产，不保存运行态。
3. `build/codex-home/` 可删除重建，不手工编辑。
4. `apply.sh` 只从 build 注入，不直接读取 source。
5. `skills/.system/` 永远以 `~/.codex` 为准。
6. 未审核资产先进入 `inbox/`，审核通过后 promote。
7. workflow、project template 和 overlay 必须只引用已登记的 profile、skill 与 agent。
8. 每次改动后运行 `build.sh` 与 `doctor.sh`。
9. 发布前运行 `scripts/check.sh`。

默认 apply 策略会对比 live 的 `managed-files.json`：如果目标文件仍等于上次注入的 managed hash，会自动更新；如果已被本机改过，会保留并由 `drift.sh` 报告。`--overwrite` 才会强制覆盖本机改动。

`manifests/policies.json` 的 `allowed_live_drift_paths` 记录允许长期保留的本机差异。当前允许 `config.toml` 漂移，以保留项目 trust、TUI notice 等运行时状态。

更多细节见 `docs/design.md` 与 `docs/codex-asset-management.md`。
