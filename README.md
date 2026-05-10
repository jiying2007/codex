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

# 上下文压缩前 90 秒 preflight（会话接力模板）
rtk bash scripts/context-preflight.sh

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
