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
# 生成可注入产物
rtk bash scripts/build.sh --profile team-collab

# 体检仓库、构建产物和当前 ~/.codex
rtk bash scripts/doctor.sh --scope all

# 只检查 workflow / project template / overlay 引用关系
rtk bash scripts/doctor.sh --scope governance

# 输出 profile、skill、agent、workflow、项目模板和 overlay 关系
rtk bash scripts/governance-report.sh
rtk bash scripts/governance-report.sh --json

# 预览注入
rtk bash scripts/apply.sh --dry-run --no-build

# 生成机器可读 apply plan
rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json

# 构建并注入到 ~/.codex，默认只覆盖未被本机改过的已管理文件
rtk bash scripts/apply.sh --profile team-collab

# 强制覆盖已有普通文件，覆盖前备份
rtk bash scripts/apply.sh --profile team-collab --overwrite

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

# 归档一份长期知识材料到 docs/archive/<topic>/
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

# 多源搜索能力由 multi-search-engine skill 提供，仅 team-collab profile 激活

# 从指定 apply plan 回滚
rtk bash scripts/rollback.sh --plan build/apply-plan.live.json

# 端到端 smoke
rtk bash tests/smoke.sh

# 发布前统一检查
rtk bash scripts/check.sh
```

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
| `manifests/project-templates.json` | 项目类型到默认 profile、workflow 与归档主题的映射 |
| `manifests/overlays.json` | 个人、本地、团队和发布场景的允许漂移与阻断路径 |
| `manifests/policies.json` | protected paths 与 apply 策略 |
| `manifests/lock.json` | build 生成的 vendor 锁定摘要 |
| `build/codex-home/` | `build.sh` 生成的可注入产物 |
| `docs/archive/` | 长期知识沉淀区，只放脱敏后的稳定材料 |
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
rtk bash scripts/build.sh --profile team-collab
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/apply.sh --profile team-collab
```

正式 skill 存放在 `src/codex-home/vendor/skills/<name>/<version>/`，激活入口由 `build.sh` 在 `build/codex-home/skills/<name>` 生成相对 symlink。不要把第三方 skill 直接放进 `src/codex-home/skills/`。

## 工作模型

`docs/codex-operating-model.md` 定义本机 Codex 的常驻线程、强目标、实时干预/任务排队、可审查产物、记忆边界、自动化边界和 MCP 治理规则。它是 `AGENTS.md` 的操作层补充：规则仍以 `AGENTS.md` 为准，具体工作台和收口模板参考该文档。

## 治理模型

profile、agent、skill、workflow、项目模板和 overlay 分层管理：

- profile 决定当前启用的能力集合，例如 `minimal`、`solo-dev`、`team-collab`。
- skill 与 agent 是可注入能力资产，由 `manifests/skills.json` 和 `manifests/agents.json` 记录版本、来源和 profile 绑定。
- workflow 是可复用工作流编排，显式声明触发词、依赖 skill、依赖 agent、入口命令和验证命令。
- workflow recipe 把 workflow 的输入、完成标准、审查产物和失败模式变成可评测契约。
- automation 只登记候选任务的只读/报告边界、审批策略和停止条件，不直接启动后台调度。
- MCP server 默认可以声明但禁用，支持 `stdio` 和 `http` transport；官方 OpenAI Docs MCP 使用 `openaiDeveloperDocs` + `https://developers.openai.com/mcp`，启用前必须补齐 readiness、凭证边界和 smoke 证据。
- subagent contract 约束并行子代理的读写范围、禁止路径、sandbox、最大并行和输出格式。
- memory candidate 只记录候选和提升门禁，不直接写入 `~/.codex/memories`。
- project template 用路径模式把不同项目类型映射到默认 profile、推荐 workflow 和归档主题。
- overlay 约束个人、本地、团队共享和发布场景下哪些 live 差异允许存在，哪些路径必须阻断。

治理层不直接写入 `~/.codex`；它提供可审计的能力关系图。修改治理 manifest 后运行：

```bash
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/governance-report.sh --json
rtk bash scripts/check.sh
```

## 知识沉淀

运行中产生的总结、调研、排障记录和外部资料，默认不进入 `src/codex-home/`，而是先脱敏、定题后归档到 `docs/archive/<topic>/`：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name --title "Readable Title"
rtk bash scripts/archive-note.sh /path/to/note-dir --topic topic-name --description "why this matters"
```

归档默认复制来源，不删除原文件；使用 `--move` 才移动。脚本会拒绝归档 Codex 运行态、密钥、日志、session、cache、`auth.json` 和旧 v2 control 知识态目录。

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
