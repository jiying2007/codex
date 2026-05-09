# Codex 全局设计方案与使用说明

- 版本：v1.1.0
- 更新时间：2026-05-01
- 适用范围：`~/.codex` 全局工程化治理

## 1. 设计方案

### 1.1 分层架构

1. 运行时层：`sessions/`、`logs_*`、`state_*`、`cache/`，仅运行态数据。
2. 控制层：`control/`，维护 catalog、角色、流程、脚本、归档。
3. 激活层：`skills/`、`agents/`、`config.toml`，供 Codex 直接读取。
4. 供应层：`vendor/`，统一存放第三方能力实体与版本。

### 1.2 核心原则

1. 第三方实体只放 `vendor/`，不直接放 `skills/`、`agents/`。
2. `.codex` 根目录不保留第三方入口链接。
3. 激活层只保留入口（软链接或最小配置）。
4. 以 `control/catalog/*.csv` 作为单一事实源（SSOT）。
5. profile 驱动启停与切换，禁止手工分散改配置。
6. 升级采用“新增版本目录 + 切换激活”策略，保证可回滚。

### 1.3 目录要点

1. `control/catalog/`：能力清单与 profile 路由规则。
2. `control/scripts/`：同步、激活、渲染、体检自动化。
3. `vendor/skills/<name>/<version>/`：技能版本实体。
4. `vendor/plugins/<name>/<version>/`：插件版本入口或镜像。
5. `mcp/`：策略、示例配置、密钥规范文档。

### 1.4 角色与协作

1. `commander`：任务拆解、分派、收口。
2. `architect`：边界与风险设计。
3. `implementer`：边界内实现与定向验证。
4. `reviewer`：缺陷与回归风险审查。
5. `tester`：验证覆盖与复现闭环。
6. `integrator`：冲突整合与最终交付。

## 2. 使用说明

### 2.0 新手上手清单

1. 执行 `sync-vendor.sh` 完成供应层与激活层同步。
2. 选择并激活一个 profile（如 `minimal` / `solo-dev` / `team-collab`）。
3. 执行 `doctor.sh`，确认 `errors=0`。
4. 打开 `config.toml`，检查 MCP 托管区块是否按预期渲染。
5. 若有治理规则变更，执行归档脚本更新知识快照。

### 2.1 日常命令

```bash
# 一键同步 vendor、激活 profile、执行体检
~/.codex/control/scripts/sync-vendor.sh ~/.codex team-collab

# 切换 profile（重建 skills/agents 软链接并渲染 config）
~/.codex/control/scripts/activate-profile.sh ~/.codex solo-dev

# 单独渲染 config.toml 的 managed MCP 区块
~/.codex/control/scripts/render-config.sh ~/.codex solo-dev

# 执行一致性体检
~/.codex/control/scripts/doctor.sh ~/.codex solo-dev
```

补充说明：

1. 详细脚本参数与故障说明见 `control/scripts/README.md`。
2. 流程选型与角色分工见 `control/workflows/README.md`。

### 2.2 Profile 建议

1. `minimal`：最小能力集，适合轻量单人任务。
2. `solo-dev`：个人深度开发，含 daily/summary 与本地角色代理。
3. `team-collab`：团队协作与并行开发，含 superpowers 能力集合。

### 2.3 新增技能流程

1. 将技能实体放入 `vendor/skills/<name>/<version>/`。
2. 在 `control/catalog/skills.csv` 增加一条记录（source/target/profiles）。
3. 执行 `activate-profile.sh` 激活软链接。
4. 执行 `doctor.sh` 确认无错误。

### 2.4 新增 Agent 流程

1. 本地角色代理放在 `control/agents-local/*.toml` 或 `vendor/agents/...`。
2. 在 `control/catalog/agents.csv` 增加映射与 profile。
3. 执行 `activate-profile.sh` 生效。
4. 执行 `doctor.sh` 检查软链接与源路径一致性。

### 2.5 MCP 配置流程

1. 在 `control/catalog/mcp.csv` 维护 server、args、env_keys、profiles。
2. 执行 `render-config.sh` 将受管区块写入 `config.toml`。
3. 密钥通过环境变量注入，不在仓库保存真实值。

### 2.6 常见操作场景

1. 新增第三方技能：放入 `vendor/skills/<name>/<version>/`，更新 `control/catalog/skills.csv`，执行 `activate-profile.sh` + `doctor.sh`。
2. 新增本地角色代理：放入 `control/agents-local/*.toml`，更新 `control/catalog/agents.csv`，执行 `activate-profile.sh` + `doctor.sh`。
3. 新增 MCP server：更新 `control/catalog/mcp.csv`，执行 `render-config.sh`，执行 `doctor.sh`。
4. 调整 profile 能力组合：更新 `profiles.csv` 与相关 catalog 的 `profiles` 字段，执行 `activate-profile.sh <profile>`，执行 `doctor.sh <profile>`。

### 2.7 故障排查

1. 软链接未更新：先执行 `activate-profile.sh`，再执行 `doctor.sh` 查看具体 target/source 差异。
2. MCP 配置不生效：检查 `control/catalog/mcp.csv` 的 `profiles` 是否包含目标 profile，执行 `render-config.sh` 并确认 `config-managed.toml` 已更新。
3. 启动出现 agent 重名告警：检查 `agents/*.toml` 中 `name` 字段是否重复，执行 `doctor.sh` 获取冲突名单。
4. 根目录出现第三方入口目录：检查 `control/catalog/plugins.csv`，执行 `sync-skills-vendor.sh` 清理根目录入口，再执行 `doctor.sh` 复核。

## 3. 归档机制

### 3.1 归档命令

```bash
~/.codex/control/scripts/archive-guidance.sh \
  ~/.codex \
  ~/.codex/control/knowledge/codex-design-and-usage.md \
  ~/.codex/control/archives/guidance \
  ~/.codex/control/archives/guidance/index.md \
  codex-design-and-usage
```

### 3.2 归档产物

1. 按时间戳生成快照文件。
2. 自动更新 `index.md` 索引。
3. 自动更新 `latest.md` 到最新快照。

### 3.3 触发时机

1. 目录结构策略变更后。
2. profile / catalog 规则变更后。
3. 团队协作流程升级后。
