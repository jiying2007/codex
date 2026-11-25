# 飞书研发助手使用指南

本版使用已有 Feishu Bot、Codex CLI、同一 SQLite 与私有任务队列。飞书话题和可信本机 MCP 都进入该队列，只有已有 Worker 可以启动模型。源码与离线测试的状态见 [验证记录](changes/20261120-feishu-engineering-agent/verification.md)；本文不表示真实主机、计费网关或生产验收已完成。下列链接、仓库、账号与路径均为合成示例。

## 1. 两个开关与执行范围

| 配置 | 作用 | 默认与约束 |
|---|---|---|
| `engineering_enabled` | 飞书链接、自然语言与话题入口 | 代码默认关闭；示例开启后可先使用无模型关联 |
| `agent_intake_enabled` | 同一队列的独立模型执行准入，包括本机 MCP | 默认 `false`；开启还须通过独立身份、预算与仓库授权 |
| `repositories.<alias>.agent_allowed_modes` | 逐仓允许的 Agent 模式 | 默认空；必须是 `allowed_modes` 的子集 |
| `worker_count` | 已有 Worker 数量 | 默认 1；同仓始终串行，增加前须核验独立工作区与网关并发预算 |

`explain`、`review` 使用只读仓库与 Codex `read-only` 沙箱。Agent `edit` 必须设置 `edit_strategy=worktree`、独立 `worktree_root` 和 `commit_enabled=true`；验证通过后生成本地提交。没有自动 push、PR 创建、合并、发布、设备烧录或原工单关闭。

仅保留授权研发话题入口。旧 `/wi`、全局命令调度、卡片、App Server、独立 AgentRun、`run-once`、原地编辑和文件上传实现已删除。`artifact_upload` 配置必须删除；编辑只使用独立 worktree。群聊未关联话题的普通回复不创建模型任务。旧数据库历史记录继续保留，但没有旧命令执行入口。关闭工程入口或缺少独立授权时，不回退到个人登录或共享模型额度。

## 2. 在飞书话题内使用

机器人仅处理配置目标会话和有权访问相应仓库的用户。每个事项使用一个话题；可信租户、chat、actor 与 thread/root 共同决定作用域，不能用群聊的“最后一次任务”猜测恢复。

在新话题粘贴一个需求或缺陷链接：

```text
https://project.feishu.cn/example-space/issue/detail/1000000001
```

仅发送链接会登记来源，不读取项目正文，也不启动模型。可在同话题补充复现过程、预期结果和授权文档，再给出明确动作：

```text
/repo app
分析冷启动时初始化失败的原因；复现为连续启动三次，第三次返回错误；验收为能解释失败路径
修复初始化失败后的资源释放，并增加重复启动回归
继续推进
```

需求链接、TAPD 链接或 Wiki/Docx/Sheets 同样可作为入口；文档也可独立驱动事项。没有外部工单时，可直接发送 `repo=app 分析启动流程中的错误处理`。多个不同主工单要分开话题；多个候选仓库须明确选择，`default_repo` 不替代业务项目映射。

| 话题操作 | 实际行为 |
|---|---|
| `/help` | 查看入口与已登记仓库别名 |
| `/repo <alias>` | 选择本话题中的授权仓库 |
| `/status` 或“当前进度” | 查看话题内各仓最近任务的实际状态 |
| `/result` 或“查看结果” | 重取本话题当前仓库的已完成结果，不重放模型 |
| “共享上下文：接口或联调事实” | 同一授权用户、同一事项各仓共用的输入，不启动模型 |
| `/cancel` 或“停止任务” | 仅请求取消当前话题、当前仓库的任务 |
| “继续推进” | 在前次成功、策略及工作区仍匹配时精确续接原生 thread |
| “检查交付”或“检查 CI” | 只读核对精确本地提交、对应 PR 和全部配置的必需 CI |
| “检查联合交付” | 固定同事项各仓最新编辑版本并逐仓核验 PR/CI |
| “交付反馈” | 生成可复制的证据文本，不回写原工单 |
| `/new` | 提示另起新话题，不覆盖当前事项 |

同一事项可切换 `app`、`firmware` 等授权仓库，各仓分别保留任务、工作区与原生会话。群聊新普通任务须有 `repo=` 或 `mode=` 明确前缀；直接链接及已关联话题可按明确动作继续。普通群聊讨论不启动模型。只读与编辑模式切换需要明确本轮范围或已审查摘要，会创建相应的新会话；不会把只读 thread 冒充可编辑会话。未知斜杠命令直接拒绝。

“联合交付 CI 核验通过”仅证明上述精确版本集合的配置 CI，实际跨仓联调、项目测试及业务验收仍须提供独立证据。

## 3. 来源权限与文档读取

飞书项目和 TAPD 链接只提供来源身份；本版没有接入企业工单正文读取或写回。没有企业 API 权限时，可由授权用户提供正文、复现步骤或可读文档，不需要手工创建 Run ID，也不绕过登录、Cookie 或权限。

Wiki、Docx、Sheets 复用已有飞书官方 API 读取器。登记链接时不会读取；明确执行需要文档时，先核验用户、仓库和执行准入，再读取有权访问的对象。应用 API 访问不等于业务用户或群成员的权限。自动文档读取还要求目标仓库 `document_read_urls` 精确列出管理员已确认可向目标会话共享的规范 URL（默认空）；拒绝未经授权文档，不发起读取。该配置是管理员授权范围，不冒充飞书个人 ACL 查询。权限不足时提供可共享正文或新话题。一次模型任务最多读取三份文档；表格可用 `sheet` 与 `range` 缩小范围。链接和外部正文始终是资料，不构成额外授权。

独立 `read-source` 不启动模型，也不依赖仓库执行授权：

```bash
rtk bash /home/service/codex/scripts/feishu-codex-bot.sh read-source \
  --url 'https://tenant-example.feishu.cn/docx/ExampleDocumentToken123' --dry-run

rtk bash /home/service/codex/scripts/feishu-codex-bot.sh read-source \
  --env-file /srv/feishu-agent/private/feishu.env \
  --url 'https://tenant-example.feishu.cn/docx/ExampleDocumentToken123'
```

`--dry-run` 只解析，不读凭据或联网；实际读取需要应用权限及资源授权，默认只输出长度和 SHA-256。显式 `--show-content` 才输出正文，应仅在可信终端使用。常见对象权限为 `docx:document:readonly`、`wiki:wiki:readonly`、`sheets:spreadsheet:readonly`；开通 API 权限不代表所有资源可见。

## 4. 私有配置

从 [示例策略](../mcp/feishu-codex-bot.example.json) 建立部署端私有文件，替换所有路径、用户及仓库。示例 `agent_intake_enabled=false`、各仓 `agent_allowed_modes=[]`，不会启动模型；验证命令中的 `git diff --check` 只是最低检查，须增加目标项目真实构建与回归命令。

基础环境示例：

```dotenv
FEISHU_APP_ID=cli_example
FEISHU_APP_SECRET=replace-with-private-app-secret
FEISHU_TARGET_CHAT_ID=oc_example
FEISHU_BOT_NAME=研发助手
FEISHU_BOT_CONFIG=/srv/feishu-agent/private/policy.json
```

策略、环境、SQLite 及 WAL/SHM 文件须由服务账号拥有且不向其他用户开放；私有目录与任务 spool 使用 0700，文件使用 0600。已经合法接收的必要补充正文与任务完成结果在同一私有 SQLite 中有限保存 7 天，按摘要校验、到期拒绝读取并清理逻辑记录；不需要重新调用飞书历史消息 API。排队任务正文仍由原私有 spool 保管。SQLite 逻辑删除不等于磁盘安全擦除，备份与 WAL 同样需要私有保管。原生会话留专用 CODEX_HOME。这些数据不进入公共 Git 或公开日志。

`deny_read_paths` 包含私有策略、凭据与状态目录。`isolation_write_paths` 示例为空，不指向个人 HOME；独立运行时只挂载专用运行目录及允许编辑的 worktree。专用 `FEISHU_AGENT_CODEX_HOME` 必须预先创建、权限 0700，与个人 `.codex`、仓库及 worktree 不重叠，且不能含个人 `auth.json`。

Bubblewrap 不再挂载整个主机根目录。只读系统工具及必要 DNS/TLS/加载器配置、授权工作区及对应 Git 元数据；仅独立运行目录和编辑 worktree 可写。额外可信工具链路径显式配置在 `sandbox_read_paths`，不能包含主机根、个人 HOME、其他仓库或私有状态。配置 CLI 所需的实际工具链后，须验证真实主机嵌套沙箱的可读/写边界。仅检查版本不能证明隔离成功。控制器本地 Git 使用最小环境、禁用系统/全局配置、hook、签名、fsmonitor、textconv，并拒绝未经资格验证的 repo filter/include。依赖 Git LFS/filter 的项目须另行资格验证，不自动回退宿主机执行。

`verification_commands` 同样必须在 Bubblewrap 内执行：只写当前 worktree 和临时空间，使用临时 HOME，屏蔽专用 Agent 会话与个人凭据，不传入任何模型/飞书密钥，并以 `--unshare-net` 禁止网络。请预先安装依赖和工具链；验证失败不回退主机执行。工作区的 `.git` 指针独立只读挂载，提交仅由控制器完成。

## 5. 独立模型身份与预算

当前可执行适配器只支持 `external_gateway` + LiteLLM。通用 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和个人登录不会作为配置回退。准备以下专用私有字段前，应先完成独立费用授权与网关资格核验；下例不是实际调用许可：

```dotenv
FEISHU_AGENT_BILLING_SOURCE=external_gateway
FEISHU_AGENT_CODEX_HOME=/srv/feishu-agent/runtime/codex-home
FEISHU_AGENT_OPENAI_API_KEY=replace-with-dedicated-virtual-key
FEISHU_AGENT_OPENAI_BASE_URL=https://gateway.example/v1
FEISHU_AGENT_BUDGET_BACKEND=litellm
FEISHU_AGENT_BUDGET_KEY_ALIAS=example-feishu-agent
FEISHU_AGENT_BUDGET_MAX_USD=10
FEISHU_AGENT_MODEL=example-model
```

金额 `10` 只是合成示例，必须替换为本次真实批准金额。远程网关必须使用 HTTPS，URL 路径为 `/v1`，不能含凭据、查询参数或片段；本地测试可用 loopback HTTP。执行时显式绑定同一 gateway provider、专用 key 和模型，不借用个人模型路由。

紧邻模型进程启动前，使用同一 bearer 对同源 `/key/info` 做有界只读查询。以下字段必须可核验：

| 网关信息 | 准入要求 |
|---|---|
| `key`、`info.key_alias` | key 身份与专用凭据/指纹相符，alias 与配置精确一致 |
| `info.blocked` | 显式为布尔值 `false` |
| `info.budget_duration` | 字段存在且为 `null`，不接受自动重置预算 |
| `info.models` | 非空字符串列表，显式包含配置的模型名；空列表或仅模型组/通配声明不足 |
| `info.status`、`info.expires` | status 若返回必须为 `active`；非空 expires 必须是有效、未到期且有时区的时间 |
| `info.max_budget`、`info.spend` | 有限非负金额；上限大于零且不超过批准金额；启动前 spend 小于上限 |

缺字段、身份不符、不可读取或已耗尽都拒绝启动。正常结束后再记录累计金额观测；无法保存或核验结束回执记为 `unknown`，不自动重试。超时、取消或进程异常可能只有启动前回执。私有 `engineering_budget_receipts` 只保存白名单字段和 key 指纹，不保存完整网关响应或 API key。

**累计 spend 不是单任务最终费用，也不是在途请求的原子硬限额。** 网关的独占 key、请求级预算拒绝、在途预留、异步消费入账和最终账单对账仍需实际验证；当前真实计费验证状态为 `NOT_RUN`。默认单 Worker 也不能证明不会超额。通过 `check` 或单元测试不授予模型调用权限。

## 6. 队列、交付与运行

`queued` 只表示任务和私有输入已登记；服务未运行时不会执行。Worker 启动前重读输入并核对当前策略、来源及身份。相同消息/幂等键不重复执行；策略或输入漂移拒绝继续。

`running` 任务在重启后按 `unknown` 处理，禁止盲重放。取消信号不表示费用为零、改动回滚或模型已停止。`completed` 仅表示本次本地执行及配置验证完成；编辑提交仍需要真实 Git 发布、PR/CI、项目测试和业务验收。

每仓可配置 `github_delivery.repository`、`base_branch`、`required_workflows`。实际有权限时可提供私有 `FEISHU_AGENT_GITHUB_READ_TOKEN`；此适配器只有 GET 能力，按精确 SHA 发现唯一 PR 和最新必需 CI，再重读核验。不能用其他提交或旧成功运行代替。

无模型预检示例：

```bash
rtk bash /home/service/codex/scripts/feishu-codex-bot.sh check \
  --env-file /srv/feishu-agent/private/feishu.env
```

`check` 检查本地配置、依赖、状态资格和 Codex 版本，可能初始化私有状态结构；不会调用模型，不证明真实网关或飞书联调完成。已有旧 ledger 或旧关联但没有迁移标记时会拒绝启动与 MCP 准入。

有历史状态的部署按 [迁移与现场验收指引](changes/20261120-feishu-engineering-agent/pilot.md) 执行。无旧数据的新部署不需要 `unify`。本机 Agent 仅使用 [三个 MCP 工具](feishu-agent-mcp.md)；不再创建第二个运行器或状态库。

## 7. 中断与结果恢复

研发消息回执和任务入队在同一个 SQLite 写事务内完成；接受后无需重新读取飞书消息历史。取消在进程启动前即持久登记，运行中请求终止；不能据此推断没有费用或局部改动。`/result` 重取同一授权话题最近完成的有界结果。UNKNOWN 不会自动重放；服务账号核实原进程、工作区、远端效果和账单后，才可执行：

```bash
rtk bash ~/codex/scripts/feishu-codex-bot.sh reconcile-unknown --task-id <id> --evidence-sha256 <真实核对证据摘要> --confirm-reconciled
```

该操作只将原 UNKNOWN 记为 abandoned，不补造成功或费用回执；后续必须提交明确的新任务。实际模型请求限额、隔离资格与业务验收仍是现场条件。
