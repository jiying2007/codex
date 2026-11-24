# 飞书 Codex：可信本机 Agent MCP 接口

**2026-11-20；默认关闭。不代表真实主机部署、模型额度或设备资格已验证。**

这不是第二套 eng。Agent 通过 MCP stdio 将任务登记到已有 Feishu Codex Bot 的 SQLite + 私有任务 spool；原 Bot 的 Worker 执行、验证并将结果发给飞书。没有公共 HTTP、任意远程 Shell、第二个模型 Runner 或新的调度数据库。

## 安全与配置

1. 仅可信且同一个 OS 用户使用；本机 Agent 进程与飞书服务共享该用户的文件权限。不同用户/不可信 Agent 必须以隔离账号另行设计，不能认为同 UID 是安全边界。
2. 飞书服务必须是真实已运行的 systemd 服务。MCP 进程只提交任务，不负责启动 Bot、登录 Codex 或授权调用费用。
3. 在现有**私有** `mcp/secrets/feishu-bot.json` 策略中显式设置顶层 `agent_intake_enabled: true`，并仅给指定仓库添加 `agent_allowed_modes: ["explain", "review"]`。两项默认关闭。允许集合必须是原 `allowed_modes` 子集。
4. Agent `edit` 必须由配置逐仓显式授权，且 `edit_strategy=worktree` 并有独立 `worktree_root`；仍没有自动 Push、PR 或 Merge。
5. MCP 读取服务同一份本地策略/凭据路径以获得队列配置，但不会向工具响应输出凭据；**不要让不可信本地 Agent 以飞书服务 OS 用户运行。**
6. Codex/ChatGPT Work 额度限制不因本 MCP 入口改变；本地单元测试不调用模型，实际远程执行需要当前批准的 Runtime/费用来源。

## MCP stdio 启动

在可信主机的 Agent MCP 配置中使用（替换为本机绝对路径）：

```json
{
  "command": "/absolute/path/codex/scripts/feishu-agent-mcp.sh",
  "args": [],
  "env": { "FEISHU_AGENT_ENV_FILE": "/private/path/feishu.env" }
}
```

脚本仅转发到 `tools.codex_assets.feishu_agent_mcp`。支持传统 MCP `2025-06-18` 的 `initialize`、`tools/list`、`tools/call`，每条 stdio 消息一行 JSON-RPC。其他协议版本/客户端应做真实兼容测试；远程 Agent 可经已认证的 SSH stdio 运行此命令，不对公网开放服务。

| 工具 | 最小参数 | 行为 |
|---|---|---|
| `submit_task` | repo, mode, task, idempotency_key | 当前仓库/模式白名单下异步排队；从不在 MCP 进程中执行模型 |
| `submit_workitem_task` | run_id, task | 关联飞书已登记的精确研发提案与现有队列；scope hash 必须匹配 |
| `get_workitem_task` | run_id | 查询 Run、原生 thread、后续回合及交付证据 |
| `verify_workitem_delivery` | run_id, pr_number, ci_run_ids | 只读核验配置仓库的精确 PR 与全部必需 workflow；推进 waiting_qa |
| `accept_workitem_qa` | run_id, reviewer, evidence_ref, attested_at, signature | 独立 QA 签名和精确 PR/CI 再核验；仅完成研发 Run |
| `get_task` | task_id | 返回同 OS 用户任务的最小状态、commit/branch 摘要，不返回提示词、日志或凭据 |
| `cancel_queued_task` | task_id | 仅取消 queued；running 必须走已有飞书控制路径，不伪造成功 |

幂等键长度为 8–128 个允许字符；相同键相同内容返回原任务 ID，不同内容拒绝。同一队列上限由现有 `queue_size` 控制。MCP 返回 `queued` 不代表服务在线或模型已执行。

## 运行与失败的语义

- `queued` 只有在持久化任务正文及权限仍有效时可于 Bot 重启后重排；`running` 重启后只能标记 `unknown`，不会自动重新调用模型。
- `completed` 是现有本机 Codex 与项目约定验证完成，不表示 PR、QA、HIL、设备或量产通过。
- 模型进程执行异常、未知外部效果、费用状态都不能从 MCP 任务文件数推导；需核对真实主机、Git/CI 和授权来源。
- Agent 任务通知发送到配置的飞书目标会话（无原始 Feishu 消息，因此不伪装成已存在的消息回复线程）。
- 如果服务没运行，任务会在受控队列中等待；查询为 `queued`，不要宣称真正启动或已完成。实际主机停机/恢复演练是部署验收前提。

## 无模型验证

```bash
rtk python3 -m unittest tests.test_feishu_agent_mcp tests.test_feishu_codex_bot
```

还需在实际主机核对 systemd、白名单、`agent_intake_enabled`、对应仓库编辑策略、spool 文件权限、Feishu 通知/失败回执、重启与重复请求；没有该证据不得宣称 production-ready。

## WorkItem 实际开发与交付
另启用 `manual_workitems_enabled`，按 [飞书助手使用指南](feishu-codex-bot-usage.md) 登记工作项，创建 `/wi attempt` 或 `/wi continue`，使用 `submit_workitem_task` 提交**完全相同的范围文本**。独立计费必须配置 `FEISHU_AGENT_BILLING_SOURCE`、专用 0700 `FEISHU_AGENT_CODEX_HOME` 和私有 API 凭据；不复用个人 auth.json。模型执行仅发生在现有 Worker。编辑任务为隔离 worktree 且允许本地提交。连续执行必须复用精确 thread、工作区和原提交，不自动重试未知结果。每仓的 `github_delivery` 配置、只读 GitHub 凭据、独立 QA 验证配置及现场步骤见 [pilot](changes/20261120-feishu-engineering-agent/pilot.md)。Git 发布继续使用原有工具，MCP 不自动 push/merge。`completed` 的 AgentRun 不代表已关闭原需求或缺陷。

### 独立模型执行与金额预算（候选）
生产不读取个人或通用 `OPENAI_API_KEY` / `OPENAI_BASE_URL`。在私有服务环境配置
`FEISHU_AGENT_OPENAI_API_KEY`、`FEISHU_AGENT_OPENAI_BASE_URL`、`FEISHU_AGENT_BILLING_SOURCE=external_gateway`、
`FEISHU_AGENT_BUDGET_BACKEND=litellm`、`FEISHU_AGENT_BUDGET_KEY_ALIAS`、
`FEISHU_AGENT_BUDGET_MAX_USD` 和 `FEISHU_AGENT_MODEL`。目前仅接入可读取自身 key 信息的 LiteLLM 网关预算适配器，不宣称其他计费后端已验证，也不要求另起调度服务。
在真实模型启动前用同一专用 bearer 读取同源 `/key/info`，核对 key alias、不自动重置的正数上限、累计 spend 及本地批准额度；无证据、超限或不可读取时拒绝执行。Codex CLI 显式选择同一个 gateway provider 与模型。前后金额观测写入私有 SQLite `engineering_budget_receipts`，只保留非秘密字段和密钥指纹，不打印完整响应。执行后无法取得回执记未知，不自动重试。默认 worker=1，显式配置仍可调整。
该观测是服务端累计金额，不是单任务最终结算，不证明网关具有原子硬限额。超时/中断可能仅有 before 回执。真实网关必须另外验证独占密钥、请求级拒绝/在途预留、账单一致性及超额拒绝，再允许生产付费执行。所有测试为合成响应，未访问真实模型或网关。
