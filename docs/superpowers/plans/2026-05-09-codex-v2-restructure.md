# Codex V2 资产仓库重构实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 `~/codex` 重构为声明式 Codex Home 构建系统，清除旧镜像式资产边界。

**架构：** `src/codex-home` 保存人工维护资产，`manifests/*.json` 保存声明式清单，`build/codex-home` 是可删除重建的生成产物，`scripts/apply.sh` 只从 build 注入 `~/.codex`。`doctor.sh` 按 repo/build/live 三层检查，避免源资产、构建产物、运行目录混淆。

**技术栈：** POSIX bash、Python 3 标准库、JSON manifest、git。

---

### 任务 1：迁移目录边界

**文件：**
- 移动：旧镜像资产目录 -> `src/codex-home/`
- 创建：`manifests/`
- 修改：`.gitignore`

- [x] 创建 `src/`、`manifests/`、`build/` 边界。
- [x] 移除旧镜像入口。
- [x] 将 `build/`、`inbox/`、`.backups/` 设为非跟踪产物。

### 任务 2：声明式 manifest

**文件：**
- 创建：`manifests/assets.json`
- 创建：`manifests/profiles.json`
- 创建：`manifests/skills.json`
- 创建：`manifests/agents.json`
- 创建：`manifests/policies.json`

- [x] 从旧 catalog 迁移 skills、agents、profiles。
- [x] 将 protected/runtime/secrets 规则集中到 policies。
- [x] 让 profile 选择只依赖 manifest，不依赖旧 CSV。

### 任务 3：重写脚本入口

**文件：**
- 创建：`scripts/build.sh`
- 创建：`scripts/apply.sh`
- 创建：`scripts/doctor.sh`
- 创建：`scripts/diff.sh`
- 创建：`scripts/backup.sh`
- 创建：`scripts/scan-skills.sh`
- 修改：`scripts/promote-skill.sh`
- 删除：旧 v1 脚本入口

- [x] `build.sh` 从 src + manifests 生成 build，并创建 profile symlink。
- [x] `apply.sh` 只从 build 注入目标，默认跳过已有普通文件，`--overwrite` 时备份。
- [x] `doctor.sh` 支持 `--scope repo|build|live|all`。
- [x] `diff.sh` 比较 build 与 live。
- [x] skill 扫描和 promote 改用 `src/codex-home` 与 JSON manifest。

### 任务 4：文档与验证

**文件：**
- 重写：`README.md`
- 重写：`docs/design.md`
- 重写：`docs/codex-asset-management.md`

- [x] 文档只描述 v2，不保留旧入口说明。
- [x] 运行脚本语法检查。
- [x] 运行 build、doctor、diff、apply dry-run。
- [x] 扫描敏感文件、运行态文件和旧入口残留。
