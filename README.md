# Codex V2 资产仓库

`~/codex` 是本机 Codex CLI 的声明式资产仓库。v2 不再把仓库目录直接当成 `~/.codex` 镜像，而是采用清晰的三层模型：

```text
src/codex-home/      # 人工维护资产源
manifests/           # 声明式 SSOT：资产、profile、skill、agent、保护规则
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

# 预览注入
rtk bash scripts/apply.sh --dry-run --no-build

# 生成机器可读 apply plan
rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json

# 构建并注入到 ~/.codex，默认保留已有普通文件
rtk bash scripts/apply.sh --profile team-collab

# 覆盖已有普通文件，覆盖前备份
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
| `manifests/policies.json` | protected paths 与 apply 策略 |
| `manifests/lock.json` | build 生成的 vendor 锁定摘要 |
| `build/codex-home/` | `build.sh` 生成的可注入产物 |
| `docs/archive/` | 长期知识沉淀区，只放脱敏后的稳定材料 |
| `inbox/skills/` | 未审核 skill 候选区，默认不纳入 git |
| `tools/codex_assets/` | Python CLI 核心实现 |
| `schemas/` | manifest schema 文档与校验依据 |

## Skill 生命周期

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
```

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

## 设计约束

1. `manifests/*.json` 是能力编排的唯一事实源。
2. `src/codex-home/` 只保存可维护资产，不保存运行态。
3. `build/codex-home/` 可删除重建，不手工编辑。
4. `apply.sh` 只从 build 注入，不直接读取 source。
5. `skills/.system/` 永远以 `~/.codex` 为准。
6. 未审核资产先进入 `inbox/`，审核通过后 promote。
7. 每次改动后运行 `build.sh` 与 `doctor.sh`。
8. 发布前运行 `scripts/check.sh`。

更多细节见 `docs/design.md` 与 `docs/codex-asset-management.md`。
