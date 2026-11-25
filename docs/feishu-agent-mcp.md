# 飞书研发助手：可信本机 MCP

MCP stdio 仅把任务提交到已有 Feishu Bot 的 SQLite 与私有 spool，使用同一 Worker、授权和独立计费配置。它不启动第二个 Runner、公共 HTTP 服务、App Server 或状态库。飞书话题入口见 [使用指南](feishu-codex-bot-usage.md)。

## 使用条件

- 客户端与 Bot 使用同一可信服务 OS 用户；同 UID 共享文件权限，不是隔离不可信 Agent 的安全边界。
- 读取与 Bot 一致的私有配置和状态路径。存在未迁移旧 ledger 时先完成 [离线迁移](changes/20261120-feishu-engineering-agent/pilot.md)。
- `agent_intake_enabled=true`，指定仓库的 `agent_allowed_modes` 明确允许请求模式，且属于 `allowed_modes`。示例默认关闭执行、逐仓模式为空。
- `edit` 只允许隔离 worktree 和本地提交：`edit_strategy=worktree`、`worktree_root`、`commit_enabled=true`。
- 真实调用必须先有独立费用授权和可核验的网关预算；MCP 客户端不能通过参数改变计费身份、仓库路径或授权。

`engineering_enabled` 控制飞书话题解析；MCP 不需要先在飞书登记 `/wi` 或创建 Run ID。旧 WorkItem、QA 签名和交付 MCP 工具已删除，不再列入协议，也不会恢复旧执行路径。

## 连接已有服务

以下为合成配置，替换为真实主机的绝对路径：

```json
{
  "command": "/home/service/codex/scripts/feishu-agent-mcp.sh",
  "args": [],
  "env": {
    "FEISHU_AGENT_ENV_FILE": "/srv/feishu-agent/private/feishu.env"
  }
}
```

脚本转发至 `tools.codex_assets.feishu_agent_mcp`。协议版本为 `2025-06-18`，支持 `initialize`、`ping`、`tools/list`、`tools/call`，每条 stdio 消息为一行 JSON-RPC，单行有界。客户端兼容性须在实际环境核验；不在公网暴露该同 UID 接口。

| 工具 | 参数 | 结果与限制 |
|---|---|---|
| `submit_task` | `repo`, `mode`, `task`, `idempotency_key` | 在已授权仓库中登记任务与策略摘要；返回任务回执，MCP 进程不执行模型 |
| `get_task` | `task_id` | 查询当前本机 Agent 用户的任务状态及最小 Git 结果信息，不返回正文、模型日志或凭据 |
| `cancel_queued_task` | `task_id` | 只取消尚未运行的任务并清理私有输入；已运行或未知任务不会伪造取消成功 |

`mode` 为 `explain`、`review` 或 `edit`。幂等键为 8–128 字符，以字母或数字开头，其余可用字母、数字、`_`、`.`、`:`、`-`；旧 `workitem-` 命名空间拒绝。相同键和内容返回原任务，不重复启动；同键不同内容拒绝。

## 计费与安全边界

当前模型路径只支持 `FEISHU_AGENT_BILLING_SOURCE=external_gateway` 与 `FEISHU_AGENT_BUDGET_BACKEND=litellm`。专用字段包括：

- `FEISHU_AGENT_CODEX_HOME`：已存在的 0700 私有运行目录，不重叠个人登录目录、仓库或 worktree，不含 `auth.json`。
- `FEISHU_AGENT_OPENAI_API_KEY` 与 `FEISHU_AGENT_OPENAI_BASE_URL`：独立 key 与 HTTPS `/v1` 网关地址，不回退到通用环境变量。
- `FEISHU_AGENT_BUDGET_KEY_ALIAS`、`FEISHU_AGENT_BUDGET_MAX_USD`、`FEISHU_AGENT_MODEL`：真实批准的 key 身份、金额与显式模型名。

实际 Worker 启动模型前，用同一 bearer 读取同源 `/key/info`，核验 key/alias、`blocked=false`、显式 `budget_duration=null`、允许模型列表、有效状态/到期时间及 cap/spend。具体规则见 [预算契约](feishu-codex-bot-usage.md#5-独立模型身份与预算)。缺少可信信息即拒绝，不接受本地计数代替网关金额。

私有预算回执是 provider key 的累计观测，不是单任务最终账单或在途请求的原子硬 cap。独占 key、请求级拒绝、在途预留与最终账单核验仍为 `NOT_RUN`。配置通过或任务 `queued` 不代表获准真实调用，也不证明网关已验证。

MCP 输出不包含原始提示、模型输出或秘密。原始任务正文暂存在 0700/0600 私有 spool；Worker 重新核验策略、来源和身份后才执行。文件系统沙箱与已知个人凭据掩蔽由统一 Runner 负责。

## 状态与运维

| 状态/事件 | 应如何理解 |
|---|---|
| `queued` | 已登记；Bot 离线时继续等待，不表示模型已启动 |
| 重复提交 | 返回原任务；缺少原私有输入时记未知，不补造输入重放 |
| 策略、key、模型或输入变化 | 启动前拒绝旧任务，须核对原任务后重新确定范围 |
| `running` 后服务中断 | 保留为 `unknown`，禁止自动重复调用 |
| `completed` | 本地执行及配置验证完成；不代表 PR、QA、设备或原工单验收 |
| 运行中取消 | 本 MCP 不发送进程终止；服务操作者须按精确任务核对和处置，不能用新幂等键重跑替代取消 |

本机 MCP 任务没有飞书原始消息或已认证的话题绑定，不向配置会话广播任务正文、结果或恢复通知；`get_task` 和 `cancel_queued_task` 仅作用于本机 MCP 创建的任务，不读取或取消飞书话题任务。`get_task` 返回有界状态与 Git 元数据；完成结果保存在服务账号的私有 SQLite。持续话题研发、精确原生续接与跨仓交付核验使用飞书话题入口。

`cancel_queued_task` 的取消请求不会使费用或外部效果自动归零。真实运行、恢复和通知需要实际主机验收；测试 mock 不能代替这些证据。
