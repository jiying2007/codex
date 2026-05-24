# Codex Operating Model

本文件把 Codex 从“一次性编码助手”约束为可恢复、可验证、可审查的工作系统。它只记录本机 `~/codex` 可落地的通用方法，不引入外部服务、不放宽默认权限、不自动写长期 memory。

## 常驻线程

一个线程应长期服务一个清晰职责。跨职责切换前先收口，避免把 unrelated context 滚进同一个长线程。

| 线程角色 | 主要职责 | 默认入口 | 收口动作 |
| --- | --- | --- | --- |
| `asset-governance` | 维护 `~/codex` 资产、manifest、skill、agent、apply 链路 | `rtk bash scripts/session-coach.sh --event target-switch --deep` | `build -> doctor -> plan/dry-run -> apply -> check` |
| `implementation` | 单仓实现、修复、重构和验证 | 项目 `AGENTS.md` + 定向测试 | `final-ready`，必要时 `session-wrap` |
| `release-ops` | 发布、版本、产物、NAS/OTA/量产闭环 | release 脚本和发布 runbook | 记录版本、产物路径、校验和、回退方式 |
| `research-archive` | 外部资料核验、调研结论、归档与记忆候选 | `multi-search-engine`、`browser-reader`、`archive-search` | `research-note-wrap -> knowledge-archive -> memory-curator --dry-run` |
| `external-monitor` | 等待型任务、PR/文档/外部反馈跟踪 | 明确数据源、刷新频率和只读边界 | 输出 action queue，不自动提交或发送 |

线程角色不是权限提升。需要网络、登录态、桌面 GUI、Slack/Gmail 或第三方 API 时，必须按任务显式授权，并记录只读/写入边界。

## 强目标

目标必须带验收机制。没有验证机制的目标只能作为探索任务，不得声明完成。

目标模板：

```text
线程角色：
目标：
范围：
非目标：
成功标准：
验证命令：
可审查产物：
阻塞条件：
完成后收口动作：
```

目标模板的可维护版本登记在 `manifests/goal_templates.json`。新增强目标类型时，必须同时声明必填字段、验证契约、产物契约、停止条件和反例。

目标强度：

- `weak`：只有方向或计划，适合探索、拆解、估算；输出必须标注未验证假设。
- `strong`：有明确成功标准和可执行验证命令；完成前必须跑对应验证。
- `continuous`：等待型或周期性目标；必须限定数据源、刷新频率、停止条件和人工审批点。

强目标示例：

```text
目标：把 context-preflight 模板扩展为可恢复的强目标模板。
成功标准：模板包含线程角色、目标强度、验收标准、可审查产物、恢复提示。
验证命令：rtk bash scripts/context-preflight.sh /tmp/context-preflight-check.md
可审查产物：生成的 Markdown preflight。
```

## 实时干预与任务排队

用户在执行中补充指令时，先判断语义：

- `steer`：修正当前方向，立即调整当前执行；需要说明改动影响的文件和验证。
- `queue`：追加后续任务，不打断当前验证；放入“下一步”或计划队列。
- `scope-change`：改变目标、范围或验收标准；先更新目标模板，再继续执行。

若新指令和当前目标冲突，以最新用户指令为准，但必须保留旧目标的未完成状态和风险。

## 可审查产物

优先生成用户能直接检查的产物，而不是只给过程描述。

| 工作类型 | 推荐产物 | 验证方式 |
| --- | --- | --- |
| 文档、调研、架构 | Markdown note | 链接、日期、结论和未决项可追溯 |
| UI 或交互原型 | `index.html`、项目预览、截图 | Playwright 或人工可视检查 |
| 数据分析 | CSV、Markdown 表格、可重跑脚本 | 输入、转换、输出三者可复现 |
| 代码变更 | diff、测试报告、review report | lint/test/build/smoke |
| 高风险变更 | `ImplementationPlan`、`ReviewReport`、`TestReport` | artifact 字段完整且证据可复查 |

临时预览和 scratch 产物不进入 `src/codex-home/`。长期可复用结论进入 `docs/archive/`，稳定规则才提升到 `AGENTS.md` 或 memory 候选。

## 记忆边界

重要上下文不只留在聊天记录里，但也不能无审查地写入长期记忆。

- 工作过程和结论：优先 `docs/archive/<topic>/`。
- 可复用规则：人工审查后提升到项目 `AGENTS.md`。
- 偏好、稳定事实、长期坑点：由 `memory-curator --dry-run` 生成候选，再人工确认。
- 一次性日志、长 diff、构建输出：只保留摘要、命令和关键证据路径。

## 自动化边界

等待型任务可以沉淀为操作模型，但默认不自动执行外部写操作。

- 定时任务每次从清晰目标重新开始，必须记录输入源和输出位置。
- 线程持续任务必须带上下文收口机制，避免无限滚动。
- 草稿可以生成，发送、提交、发布、删除、覆盖和外部写入必须人工确认。
- 自动化候选先登记到 `manifests/automations.json`，默认保持 `enabled=false` 或 `mode=report-only`；不得仅凭文档声明创建真实后台调度。
- 自动化必须声明 run lifecycle：首跑审查、稳定运行行为、stale threshold、retry budget、cleanup 和 retention。缺少 lifecycle 的自动化不得进入 source-to-live 链路。
- 任何 connector、MCP、桌面 GUI 或登录态操作都必须先声明权限边界、凭证边界和回退方式。

## MCP 治理

MCP server 先登记到 `manifests/mcp_servers.json`，再由 build 渲染到 `config.toml`。默认可以声明但禁用；OpenAI 官方文档优先使用只读 remote MCP `openaiDeveloperDocs`，URL 为 `https://developers.openai.com/mcp`。启用前必须满足：

- 声明 `transport`、profiles、用途和 owner；`stdio` 需要 `command/args`，`http` 需要 `url`。
- 不提交真实 token、API key 或本机私有 endpoint。
- 有 tool/resource/prompt 暴露范围、网络目标、可执行 deny-path 测试、日志脱敏、smoke 方式和禁用回滚方式。
- 涉及网络、登录态或第三方写操作时，必须单独完成安全和供应链审查。

## 子代理与记忆候选

- 并行子代理默认遵循 `manifests/subagent_contracts.json`，必须声明读写范围、禁止路径、sandbox、输出契约和最终整合验证。
- 长期记忆候选默认进入 `manifests/memory_candidates.json`，保持 `enabled=false`，经人工 review、secret scan 和 promotion gate 后再决定提升到 `AGENTS.md`、`docs/archive/` 或 memory。

## Eval、命令与提升路径

- 可复用 workflow 和治理能力必须有 eval 契约。routing、governance、completion 和 prompt 行为登记到 `manifests/eval_suites.json`，至少包含 cases、成功指标、负例、命令和 promotion gate。
- slash command 是控制面入口，登记到 `manifests/cli_command_contracts.json`。命令契约必须说明输入、允许动作、禁止动作、输出、review 和验证要求；禁止绕过验证。
- 会话经验、官方资料、归档结论和 manifest 决策要提升为长期规则前，先匹配 `manifests/guidance_promotions.json`。提升必须有来源、review、secret scan、最小证据、验证和回退。
- 上下文压缩按 `docs/context-layout.md` 分层：stable context 才能进入长期规则候选，dynamic context 只用于恢复当前线程，evidence context 支撑交付声明，excluded context 不沉淀。

## 收口

准备 final、commit、push、apply 或目标切换前：

```bash
rtk bash scripts/session-coach.sh --event final --deep
rtk bash scripts/final-ready.sh
```

长线程或 context 压力高时：

```text
context-preflight -> session-wrap -> archive-note -> memory-curator --dry-run -> new session
```
