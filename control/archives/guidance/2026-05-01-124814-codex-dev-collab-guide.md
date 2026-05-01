# 归档快照：codex-dev-collab-guide

- 归档时间：2026-05-01 12:48:14 +0800
- 来源文件：`/home/aiot03/.codex/control/knowledge/codex-dev-collab-guide.md`

## 自动摘要（按二级标题提取）
- 目标与原则
- 推荐目录分层
- 个人开发模式
- 团队协作模式
- 协作执行回合（推荐）
- 协作交接模板（可复用）
- 技巧与实践清单
- 流程选型建议
- 自动总结与归档机制
- 当前落地状态（v1.2.0）
- 归档节奏建议

## 正文快照

# Codex 全局开发与协作指南

- 版本：v1.2.0
- 更新时间：2026-05-01
- 适用范围：`~/.codex` 全局目录治理、个人开发、团队协作、技能与代理分工

## 目标与原则

1. 控制复杂度：把“运行时状态”和“可维护资产”分层，避免目录污染。
2. 可扩展：第三方能力统一进入 `vendor/`，激活层只放软链接或最小入口。
3. 可回滚：版本目录显式化，激活策略可切换，任何变更能快速撤回。
4. 可协作：角色职责清晰，分工并行但收口统一。

## 推荐目录分层

1. 运行时层：日志、会话、缓存、状态数据库（不作为协作资产）。
2. 控制层：规则、目录清单、角色职责、工作流、脚本。
3. 激活层：`skills/`、`agents/`、`config.toml`（Codex 直接读取）。
4. 供应层：`vendor/`（第三方资源与版本仓）。

## 个人开发模式

1. 默认使用 `minimal` profile，保持技能与 MCP 最小集。
2. 新增能力先在 `vendor/<name>/<version>` 落地，再激活软链接。
3. 任何实验能力先走 `experimental` 标签，不直接进入默认 profile。
4. 每次调整后至少执行一次健康检查：软链接、配置渲染、核心命令可用性。

## 团队协作模式

1. 角色分工建议：
- commander：拆解任务、调度并行、最终裁决。
- explorer：只读勘探、证据收集。
- implementer：按边界实施改动。
- reviewer：风险与回归审查。
- tester：测试与验收验证。
- integrator：收口整合、冲突解决、交付输出。
2. 并行写入规则：
- 同一文件同一时段只允许一个写入 owner。
- shared contract/schema/root config 统一串行收口。
3. 交付门禁：
- 必须有验证证据。
- 必须有风险说明。
- 必须有回滚路径。

## 协作执行回合（推荐）

1. 回合 1：目标与边界
- 明确目标、范围、验收标准、不可触碰边界。
- 形成任务拆分与 ownership，避免同文件并行写冲突。

2. 回合 2：实现与验证
- 每个子任务按“最小改动 + 定向验证”执行。
- 中途发现共享 contract/schema 冲突时立即上报并串行收口。

3. 回合 3：收口与交付
- 汇总改动面、依赖顺序、最终验证结果。
- 输出 merge plan、残余风险、回滚建议。

## 协作交接模板（可复用）

1. 任务目标：一句话说明要达成什么。
2. 修改范围：涉及目录/文件与禁止越界范围。
3. 验证命令：已执行命令、关键输出、失败重现步骤。
4. 风险清单：已知风险、影响面、缓解措施。
5. 待决事项：需要决策的点与可选方案。

## 技巧与实践清单

1. “新增不覆盖”：升级第三方能力时新增版本目录，不覆盖旧目录。
2. “入口最薄”：激活层只保留入口，不存放第三方实体内容。
3. “声明式启停”：通过 profile 或清单激活，不手工散改配置。
4. “每日小归档”：当天关键策略变化做快照，避免口头约定漂移。
5. “先证据后结论”：协作评审中优先列证据文件与验证结果。

## 流程选型建议

1. 新功能优先 `feature-flow`。
2. 故障修复优先 `bugfix-flow`。
3. 结构治理优先 `refactor-flow`。
4. 不确定时先走 `bugfix-flow` 的根因确认阶段，再切到对应流程。

流程文件位置：

1. `control/workflows/README.md`
2. `control/workflows/feature-flow.md`
3. `control/workflows/bugfix-flow.md`
4. `control/workflows/refactor-flow.md`

## 自动总结与归档机制

1. 主文档：本文件维护“当前有效策略”。
2. 归档脚本：`control/scripts/archive-guidance.sh`。
3. 归档目录：`control/archives/guidance/`。
4. 索引文件：`control/archives/guidance/index.md`。
5. 建议触发时机：
- 目录治理策略调整后。
- profile 或角色职责发生变化后。
- 团队协作规范升级后。

## 当前落地状态（v1.2.0）

1. 已建立 `control/catalog/*.csv` 作为 SSOT（skills/agents/subagents/mcp/profiles/plugins）。
2. 已建立 `vendor/` 供应层，第三方 skills 统一存放在 `vendor/skills/<name>/<version>`。
3. `skills/` 与 `agents/` 作为激活层，由 `activate-profile.sh` 自动重建软链接。
4. `render-config.sh` 负责渲染 `config.toml` 中受管的 MCP 区块。
5. `doctor.sh` 提供 profile 级一致性检查。

## 归档节奏建议

1. 个人：每周至少一次策略快照。
2. 团队：每次协作规范变更立即归档。
3. 发布前：针对最终规则状态追加一次归档。
