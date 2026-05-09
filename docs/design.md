# Codex V2 设计

## 核心模型

v2 采用构建系统模型，而不是目录镜像模型：

```text
src/codex-home + manifests -> build/codex-home -> ~/.codex
```

- `src/codex-home/`：人工维护源资产。
- `manifests/`：声明式 SSOT。
- `build/codex-home/`：生成产物，可随时删除重建。
- `~/.codex`：Codex 运行目录，保留系统 skill、认证、session、日志、缓存和本机私有状态。

## Manifest

`manifests/assets.json` 定义源目录、构建目录、默认 profile 和复制根。

`manifests/skills.json` 与 `manifests/agents.json` 定义可激活能力：

```json
{
  "name": "skill-asset-manager",
  "enabled": true,
  "source_kind": "vendor",
  "version": "0.2.0",
  "vendor_rel": "vendor/skills/skill-asset-manager/0.2.0",
  "target_rel": "skills/skill-asset-manager",
  "profiles": ["solo-dev", "team-collab"]
}
```

`manifests/policies.json` 定义受保护路径。构建和注入必须跳过这些路径，尤其是 `skills/.system/**`、密钥、session、缓存和日志。

## 构建

`scripts/build.sh` 负责：

1. 清空并重建 `build/codex-home/`。
2. 从 `src/codex-home/` 复制声明的资产根。
3. 根据 profile 为 skills 和 agents 创建相对 symlink。
4. 生成 `skills/registry.csv`。
5. 生成 `control/state/active-profile.env` 与 `managed-files.json`。

构建产物不纳入 git，不手工编辑。

## 注入

`scripts/apply.sh` 只从 `build/codex-home/` 注入到 `~/.codex`：

- 新文件复制。
- 已存在普通文件默认保留。
- `--overwrite` 时先备份再覆盖。
- 生成文件和 profile symlink 会更新。
- 目录合并，不整体替换目标目录。
- protected paths 永远跳过。

## 体检

统一入口：

```bash
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope live
rtk bash scripts/doctor.sh --scope all
```

`repo` 检查仓库结构、manifest、脚本语法和旧入口残留。`build` 检查构建产物和 profile 激活 symlink。`live` 检查目标运行目录的 managed state 与系统 skill 状态。

## Skill 归档

第三方或运行中生成的 skill 生命周期：

```text
discovered -> inbox -> reviewed -> vendored -> built -> applied
```

命令：

```bash
rtk bash scripts/scan-skills.sh
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
rtk bash scripts/build.sh --profile team-collab
rtk bash scripts/apply.sh --profile team-collab
```

正式归档位置是 `src/codex-home/vendor/skills/<name>/<version>/`。`src/codex-home/skills/` 只保留 registry、README 和维护脚本等基础层。
