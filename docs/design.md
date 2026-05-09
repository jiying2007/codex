# Codex 资产仓库设计

## 结构

```text
~/codex/
├── AGENTS.md
├── README.md
├── assets/
│   └── codex/
│       ├── AGENTS.md
│       ├── control/
│       ├── skills/
│       ├── prompts/
│       ├── vendor/
│       ├── mcp/
│       ├── rules/
│       ├── agents/
│       └── config*.toml
├── scripts/
│   ├── apply-to-codex.sh
│   ├── diff-codex.sh
│   ├── backup-codex.sh
│   ├── scan-codex-skills.sh
│   ├── promote-skill.sh
│   └── doctor-assets.sh
├── docs/
└── .gitignore
```

## 约定

- `assets/codex/` 是注入到 `~/.codex` 的 source of truth。
- `scripts/` 是仓库维护入口，不默认注入到 `~/.codex`。
- `docs/` 记录长期设计与维护说明。
- `skills/.system/` 以 `~/.codex` 中已有内容为准，不纳入仓库资产。
- 运行时、密钥、缓存、日志、session 不纳入仓库资产。

## 注入策略

默认命令：

```bash
rtk bash scripts/apply-to-codex.sh
```

默认行为：

- 新文件复制到 `~/.codex`。
- 已存在文件跳过并报告。
- 已存在目录递归合并。
- `skills/.system/` 始终跳过。
- secrets/runtime/cache/logs 始终跳过。

覆盖模式：

```bash
rtk bash scripts/apply-to-codex.sh --overwrite
```

- 新文件复制。
- 已存在文件先备份，再覆盖。
- 已存在目录递归合并。
- `skills/.system/` 仍然跳过。

结构体检：

```bash
rtk bash scripts/doctor-assets.sh
```

该检查确认根目录没有旧运行资产入口、`assets/codex/skills/.system` 不存在、根级脚本语法有效，并调用资产源内的 `control/scripts/doctor.sh` 做 profile 体检。

## Skill 归档策略

第三方或运行中生成的 skill 不直接进入 `assets/codex/skills/`，而是先进入候选区，再提升为 vendor 资产。

发现 `~/.codex/skills` 中的未知 skill：

```bash
rtk bash scripts/scan-codex-skills.sh --dry-run
rtk bash scripts/scan-codex-skills.sh
```

候选目录：

```text
inbox/skills/<name>/<timestamp>/
```

归档审核通过的 skill：

```bash
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
```

归档后位置：

```text
assets/codex/vendor/skills/<name>/<version>/
```

归档脚本会更新：

- `assets/codex/control/catalog/skills.csv`
- `assets/codex/skills/registry.csv`

自动化 skill：

```text
assets/codex/vendor/skills/skill-asset-manager/0.1.0/
```

当用户要求接入、扫描、归档、提升 Codex skill 时，AI 应使用 `skill-asset-manager`，按发现、审核、promote、验证、注入的顺序执行。
