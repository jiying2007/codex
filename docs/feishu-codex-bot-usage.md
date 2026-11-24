# 飞书 Codex AI助手使用指南

## 1. 定位与安全边界

飞书 AI助手通过企业自建应用的长连接接收消息，在本机调用 Codex CLI，并将结果回复到指定飞书会话。

当前边界：

- 仅处理配置的 `FEISHU_TARGET_CHAT_ID`。
- 仅允许全局或仓库级 Open ID 白名单中的用户。
- 用户只能选择策略文件中登记的仓库别名，不能传入文件系统路径。
- `explain`、`review` 强制使用 Codex `read-only` sandbox；`edit` 使用 `workspace-write`。
- `edit` 默认直接修改登记仓库，不创建 worktree、分支或提交；禁止推送、创建 PR 和修改远端。
- 同一仓库的任务串行执行；写任务必须保留用户已有未提交改动，不得清理、回退或提交无关内容。
- 每条任务以触发消息为审计锚点，结果回复到该消息线程。
- 文件回传必须在 `edit` 任务中显式声明 `artifact=<仓库相对路径>`，并同时通过仓库目录、扩展名、大小和文件快照校验。
- 飞书凭据不会传给 Codex 子进程；Bubblewrap 同时把私有凭据目录从子进程文件系统中隐藏。
- SQLite 不保存消息正文或 Codex 输出。为了在重启后恢复**尚未启动**的排队任务，原始任务要求暂存于与数据库同级的私有 `feishu-pending-jobs/`（目录 0700、文件 0600），仅服务账号可读，任务结束后删除；这属于新的敏感主机数据，应纳入本地备份、磁盘加密和保留策略。任务一旦进入 `running`，重启时只会标为 `unknown` 并提示人工核对，绝不自动重复调用模型。

## 2. 基础策略与当前环境

| 别名 | 工作目录 | 模式 | edit 策略 |
| --- | --- | --- | --- |
| `codex` | `~/codex` | `explain`, `review` | - |
| `pcr02-demo` | `/vsdata/leiwenjun/work/sigmastar/pcr02_ssc305/SourceCode/sdk/verify/xcrz_sigmastar_demo` | `explain`, `review`, `edit` | `in_place` |
| `llm_apps` | `~/bin/llm_apps` | `explain`, `review`, `edit` | `in_place` |
| `x5` | `/vsdata/leiwenjun/work/rdk/x5` | `explain`, `review`, `edit` | `in_place` |

上述是原基础策略的仓库登记，默认项目为 `llm_apps`。当前环境使用独立的 `mcp/secrets/feishu-bot-current.json`：只登记 `codex`，默认项目为 `codex`，只允许 `explain`、`review`，未启用 `edit` 和文件上传；不需要每条消息指定 `repo=`。原策略和凭据文件保持不变。

当前环境通过 `~/.config/systemd/user/feishu-codex-bot.service.d/current-environment.conf` 覆盖 `FEISHU_BOT_CONFIG`。默认工作目录用于 Codex 的本地执行和隔离；飞书文档不需要保存到该仓库。单独使用 `read-source` CLI 时只需要应用凭据，不依赖任何仓库登记。

下文的直接写任务和文件回传示例仅适用于明确开放对应权限的部署策略。直接写任务会保留在所选仓库工作区中，便于本地审查；同一仓库一次只运行一个任务。
`llm_apps` 额外允许回传 `android-prototype/dist/android/` 下不超过 30 MiB 的非空 `.apk`；其他仓库默认不允许文件回传。

## 3. 飞书使用

### 3.1 分析和说明

```text
repo=codex mode=explain 说明当前仓库的目录结构
repo=pcr02-demo mode=explain 分析显示模块的主要入口
```

### 3.2 只读代码审查

```text
repo=codex mode=review 审查当前未提交改动
repo=pcr02-demo mode=review 检查当前分支的并发和资源释放风险
```

### 3.3 直接修改当前工作区

```text
mode=edit 修复初始化失败并补充验证
mode=edit task=<飞书任务GUID> 修复该任务描述的问题
mode=edit requirement=REQ-123 defect=BUG-456 log=om_xxx 根据需求、缺陷和日志修复崩溃
```

执行结果：

1. 直接进入消息中选择的登记仓库。
2. 记录执行前工作区快照，并在仓库级锁内运行任务。
3. 保留用户已有改动，仅实施当前任务所需修改。
4. 执行仓库配置的验证命令；当前至少执行 `git diff --check`。
5. 在线程中返回实际工作目录，明确标记“未创建分支、未提交、未执行 push”。

`mode=edit` 本身就是单次写授权；不写 `mode=edit` 就不会修改。直接模式即使任务失败也不会自动回退或清理工作区，需本地审查残留改动。服务没有 push 代码路径，Codex 子进程无网络写权限，并强制使用拒绝推送的 `pre-push` 钩子。

如需恢复隔离分支和本地提交，仓库策略可显式设置 `"edit_strategy": "worktree"`、独立 `worktree_root` 和 `"commit_enabled": true`。Codex 进程仍运行在 Bubblewrap 文件系统视图中：除 Codex 自身运行目录和仓库/worktree 外均为只读，`mcp/secrets` 被空目录覆盖，无法读取 App Secret、策略、状态库和锁文件。`isolation_write_paths` 只应配置 Codex 自身必需的运行目录，不能与 `deny_read_paths` 重叠。

### 3.4 构建产物回传

`artifact=` 表示本次任务完成后，将一个指定构建产物上传到触发消息线程，也是本次显式文件外传授权。例如：

```text
repo=llm_apps mode=edit artifact=android-prototype/dist/android/1.0.0/jingdu-1.0.0-debug.apk 执行 Android 构建并生成 Debug APK
```

回传顺序：

1. Codex 在登记仓库中完成任务，生成声明的相对路径。
2. 服务完成仓库配置的验证，再检查产物是否位于允许目录、扩展名是否允许、文件是否非空且不超过上限。
3. 服务拒绝绝对路径、`..`、非规范路径、符号链接、非普通文件和验证后发生变化的文件。
4. 服务计算 SHA-256，通过流式接口上传；取得 `file_key` 后才在线程中发送文件消息。
5. 文件消息后回复文件名、字节数和完整 SHA-256，不记录或回复本机绝对路径。

当前只为 `llm_apps` 启用 APK 回传。每条任务只能声明一个 `artifact`，且必须使用 `mode=edit`；未声明时不会自动搜索或上传构建目录。飞书应用还需要开启“获取与上传图片或文件资源”权限。飞书上传接口拒绝空文件，并限制文件不超过 30 MB。

显式声明 `artifact` 的任务允许“只构建、不修改源码”，因为 APK 常位于 Git 忽略目录；这类任务仍必须通过仓库验证并成功生成声明文件。未声明 `artifact` 的普通 `edit` 继续要求实际产生工作区修改。

### 3.5 飞书对象联动

支持在命令前缀中组合以下引用：

- `task=<GUID>`：通过飞书任务 v2 读取标题、状态和描述，需要任务只读权限及该任务可见性。
- `log=<om_消息ID>`：读取指定飞书消息内容，需要消息历史读取权限，机器人必须在对应会话中。
- `requirement=<ID>`、`defect=<ID>`：记录飞书项目工作项关联。飞书项目是独立产品，未配置专用连接器时会明确提示“引用已记录、正文未拉取”。
- 当前触发消息始终自动关联，不需要手写 ID。

关联正文只进入当前 Codex 提示，不写入 SQLite；SQLite 只保存引用类型和 ID。入站附件下载尚未启用，日志请先用文本消息或 `log=<消息ID>` 引用；这不影响上述出站构建产物回传。

### 3.6 飞书文档与表格链接读取

在任务正文中粘贴链接，或使用 `doc=<链接>` 前缀，服务会在既有会话和用户白名单检查后读取内容，再交给 Codex。例如：

```text
repo=codex mode=explain doc=https://example.feishu.cn/wiki/NodeToken?sheet=SheetId&range=A1:C20 根据表格整理问题
repo=codex mode=review 根据需求文档检查当前代码 https://example.feishu.cn/docx/DocumentToken
```

支持 `wiki`、`docx`、`sheets` 链接；知识库节点仅支持底层新版文档或电子表格。多维表格、附件和飞书项目工作项正文尚未接入。链接只解析，实际网络请求发往飞书官方 API，不直接访问用户提供的主机。

每个任务最多 3 个链接。电子表格未指定 `sheet` 时读取第一个返回的工作表；未指定 `range` 时读取从 A1 开始至多 50 行、20 列，并按实际网格缩小。显式范围最多 100 行、26 列、2000 单元格。单文档正文会标记截断，关联上下文总量超过 12000 字符时要求缩小范围。拒绝权限不足、无效对象或不存在的工作表，不在缺少文档证据时继续调用 Codex。

内容仅作为不可信参考数据进入本次提示；SQLite 仅保存链接引用，不保存正文。需要应用身份权限 `wiki:wiki:readonly`、`docx:document:readonly`、`sheets:spreadsheet:readonly` 中与对象对应的权限，以及目标资源访问授权。开通权限不代表所有文档可读。

只读 CLI 复验入口：

```bash
rtk bash ~/codex/scripts/feishu-codex-bot.sh read-source --url 'https://example.feishu.cn/wiki/NodeToken?sheet=SheetId&range=A1:C3' --dry-run
rtk bash ~/codex/scripts/feishu-codex-bot.sh read-source --url 'https://example.feishu.cn/wiki/NodeToken?sheet=SheetId&range=A1:C3'
```

`--dry-run` 不读取凭据或联网；实际读取默认仅输出上下文长度与 SHA-256，不打印正文。显式添加 `--show-content` 才输出正文。此入口不会启动 Codex、发送消息或写入云端文档。

源码更新后需在真实部署端按第 5 节检查、重启常驻服务，再从白名单用户的目标会话验证。CLI 读取成功不能替代聊天端联调。

### 3.7 控制命令

```text
/help
/repo
/repo x5
/repo reset
/status
/cancel
```

- `/help`：显示仓库别名和命令格式。
- `/repo`：查看本人的当前默认项目和系统默认项目。
- `/repo <别名>`：持久修改本人的默认项目，不影响其他用户。
- `/repo reset`：清除个人设置，恢复系统默认项目 `llm_apps`。
- `/status`：显示本人任务的状态统计、最近任务、任务分支和提交。
- `/cancel`：取消本人排队中或运行中的任务，不影响其他用户任务。
- 以独立斜杠命令开头的未知或错误命令（例如 `/wl help`，末尾为小写 l）直接拒绝，不进入 Codex。正确工作项帮助命令为 `/wi help`（末尾为 i）。需要把斜杠词当作分析文本时，显式使用 `mode=explain` 或 `repo=<别名>` 前缀。

未指定 `repo=` 时，优先使用发送者的个人默认项目；未设置或个人别名已经从白名单移除时，回退到策略文件的 `default_repo`，当前为 `llm_apps`。命令中的 `repo=<别名>` 只覆盖当前任务，不修改个人默认项目。未指定 `mode` 时默认使用 `explain`。

## 4. 配置文件

### 4.1 凭据文件

默认路径：

```text
~/codex/mcp/secrets/feishu.env
```

最小内容：

```dotenv
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=replace-me
FEISHU_TARGET_CHAT_ID=oc_xxx
FEISHU_BOT_NAME=AI助手
FEISHU_BOT_CONFIG=~/codex/mcp/secrets/feishu-bot.json
```

文件必须设置为 `600`，不得提交到 Git、粘贴到工单或输出到日志。

### 4.2 策略文件

默认本机路径：

```text
~/codex/mcp/secrets/feishu-bot.json
```

可提交的脱敏示例：[feishu-codex-bot.example.json](../mcp/feishu-codex-bot.example.json)。

添加仓库：

```json
{
  "default_repo": "llm_apps",
  "allowed_open_ids": ["ou_owner"],
  "repositories": {
    "llm_apps": {
      "path": "~/bin/llm_apps",
      "allowed_modes": ["explain", "review", "edit"],
      "allowed_open_ids": [],
      "edit_strategy": "in_place",
      "commit_enabled": false,
      "artifact_upload": {
        "enabled": true,
        "allowed_roots": ["android-prototype/dist/android"],
        "allowed_extensions": [".apk"],
        "max_bytes": 31457280
      },
      "verification_commands": [["git", "diff", "--check"]]
    }
  }
}
```

白名单规则：

1. 顶层 `allowed_open_ids` 是全局白名单。
2. 仓库的 `allowed_open_ids` 为空时继承全局白名单。
3. 仓库白名单非空时，会在全局白名单基础上进一步收窄。
4. 任何仓库没有有效白名单时，`check` 和 `start` 都会拒绝运行。

仓库别名只能包含小写字母、数字、`_` 和 `-`，最长 32 个字符。仓库路径必须存在并包含 `.git`。

`edit_strategy` 缺省为 `in_place`。该模式不需要初始提交或 `worktree_root`，并强制禁止自动提交。显式使用 `worktree` 时必须配置仓库外部的 `worktree_root`；此时可按需启用受控本地提交。

`artifact_upload` 缺省关闭。启用时必须同时允许 `edit`，并配置至少一个仓库相对 `allowed_roots` 和 `allowed_extensions`。服务端硬上限为 30 MiB；可通过 `max_bytes` 进一步收紧，不能放宽平台上限。目录可以在构建前不存在，但实际回传时目标必须是目录内的普通文件。

## 5. 配置变更流程

修改凭据或策略后先检查，再重启服务：

```bash
rtk bash scripts/feishu-codex-bot.sh check
rtk systemctl --user restart feishu-codex-bot.service
rtk systemctl --user show feishu-codex-bot.service \
  -p ActiveState -p SubState -p MainPID -p NRestarts
```

检查不会连接飞书或发送消息，但会验证：

- 私有文件权限。
- chat ID 格式。
- 仓库别名、路径、Git 工作目录和允许模式。
- 产物上传开关、相对目录、扩展名和大小上限。
- 全局及仓库级白名单。
- SQLite 路径。
- Codex CLI 可执行性。

## 6. 常驻服务管理

仓库内 unit：

```text
mcp/systemd/feishu-codex-bot.service
```

模板使用 systemd `%h` 指向运行用户的主目录，默认仓库位置为 `~/codex`。
仓库安装在其他位置时，安装前调整 unit 的 `WorkingDirectory` 和 `ExecStart`；
文档中的 `~/codex` 命令也应使用实际位置。本次源码修改不会更新已安装的 unit 或重启服务。

本机安装位置：

```text
~/.config/systemd/user/feishu-codex-bot.service
```

常用命令：

```bash
rtk systemctl --user status feishu-codex-bot.service
rtk systemctl --user restart feishu-codex-bot.service
rtk systemctl --user stop feishu-codex-bot.service
rtk journalctl --user -u feishu-codex-bot.service -f
rtk loginctl show-user "$USER" -p Linger
```

预期状态：

```text
ActiveState=active
SubState=running
Linger=yes
```

服务启用了单实例锁。手工重复启动会返回“已有飞书 Codex 服务实例在运行”。

## 7. 任务与并发模型

- 飞书事件先经过 chat ID、消息类型、白名单、别名和模式校验。
- 消息 ID 和个人默认项目写入 SQLite，服务重启后仍能识别重复事件并保留用户选择。
- 队列有最大长度，避免无限积压。
- 用户请求有时间窗口限流。
- 同一个仓库的任务通过仓库锁串行执行。
- 不同仓库最多按 `worker_count` 并行。
- `/cancel` 会标记排队任务为 canceled，并终止本人正在运行的 Codex 子进程。
- Codex 超时后先 terminate，必要时再 kill；不会无限等待。

### 7.1 重启后的任务恢复（2026-11-20）

- 只恢复 SQLite 仍为 `queued`、私有任务载荷完好且**当前仓库/用户/模式白名单再次通过**的任务；后台每秒有界扫描遗漏入队的任务。
- 原有只存 SQLite 但未保存任务输入的排队项标记 `unknown / QueuedPayloadUnavailable`，不重新请求模型，需从飞书重新提交。
- 上次处于 `running` 的任务在本机服务重启后标记 `unknown / UnobservedServiceRestart`，即便遗留文件存在也不自动执行；应先核实 Git/worktree、进程和费用，再明确重新发起。
- 任务正文不进入 SQLite 或 Git。此暂存机制不会保留长久全文；磁盘空间、目录权限与备份需要在实际部署主机验证。服务重启不是成本回滚或远程操作撤销。
- 仅 Git/本地测试绿色无法证明服务已在实际飞书环境连续运行，也不等于自动获准消耗 Codex/Work 额度。

## 8. 状态与日志

状态数据库默认位于：

```text
mcp/secrets/feishu-codex-state.sqlite3

# 与数据库目录相同的私有队列载荷目录（仅排队任务，结束即删除）
mcp/secrets/feishu-pending-jobs/
```

日志只输出：

- 动作类型。
- 仓库别名。
- 任务 ID。
- 消息 ID 后缀。
- 成功、失败或取消状态。

日志不得出现 App Secret、access token、WebSocket ticket、完整 Open ID、消息正文或 Codex 输出。

查看最近日志：

```bash
rtk journalctl --user -u feishu-codex-bot.service -n 50 --no-pager
```

## 9. 常见问题

### 服务无法启动

```bash
rtk bash scripts/feishu-codex-bot.sh check
rtk systemd-analyze --user verify mcp/systemd/feishu-codex-bot.service
rtk journalctl --user -u feishu-codex-bot.service -n 50 --no-pager
```

重点检查私有文件权限、仓库路径、`.git`、白名单和 Codex CLI 登录状态。

### 飞书没有回复

确认：

1. 应用已发布，机器人已加入目标群。
2. 已订阅 `im.message.receive_v1`。
3. 用户 Open ID 在有效白名单中。
4. 使用的是已登记仓库别名和允许模式。
5. 服务处于 `active/running`。

### 请求被限流或队列已满

等待当前任务完成后重试。个人阶段不要盲目增大并发；嵌入式大仓分析通常消耗较多时间和上下文。

### 配置修改后没有生效

策略文件由进程启动时加载。修改后必须运行 `check` 并重启 systemd user service。

### APK 已生成但回传失败

依次确认：

1. 命令使用了 `mode=edit artifact=<仓库相对路径>`。
2. 路径位于 `android-prototype/dist/android/` 且扩展名为 `.apk`。
3. 文件非空、不超过 30 MiB，构建后没有被其他进程继续改写。
4. 飞书应用已开启“获取与上传图片或文件资源”权限，并仍具有向目标会话发送消息的权限。
5. 查看服务日志中的错误类型；日志不会输出文件绝对路径或 `file_key`。

## 10. 团队扩展建议

团队化时保持以下顺序：

1. 为每个仓库设置独立白名单。
2. 将个人 Codex 身份替换为公司管理的自动化身份。
3. 为每个任务创建独立 worktree 或容器。
4. 增加配额、成本、保留期限和审计策略。
5. 推送和创建 PR 继续保持禁用；需要启用时应另做审批卡片和独立发布身份。
6. 为飞书项目配置专用工作项连接器后，再读取需求和缺陷正文，并坚持最小只读权限。

当前服务允许本地写和提交，但不会自动合并、rebase、push 或创建 PR。需要把任务分支合入开发分支时，由开发者本地审查后手工处理。

## 11. 回退

停止并禁用服务：

```bash
rtk systemctl --user disable --now feishu-codex-bot.service
```

重新启用：

```bash
rtk systemctl --user enable --now feishu-codex-bot.service
```

本机凭据、策略、SQLite 和锁文件均在 `mcp/secrets/`，默认被 Git 忽略。不要删除用户数据；需要清理或重建状态库时必须单独确认。

## 12. 其他 Agent 的可信本地 MCP 入口（默认关闭）

入口见 [feishu-agent-mcp.md](feishu-agent-mcp.md)。该接口使用当前 Bot 私有 SQLite/任务 spool，不启动第二个执行器，也不提供公共 HTTP。必须在真实主机私有策略显式开启 `agent_intake_enabled` 和每个仓库的 `agent_allowed_modes`，默认全部关闭。启用不等于获得模型额度或生产部署资格。

## 13. 无人值守结果与提交保护（2026-11-20）

- Codex 模型运行发生超时，无法仅凭本机子进程退出证明费用或远端效果不存在；服务将任务记为 `unknown`，保留原现场并通知飞书，不自动再次调用模型。
- 使用 `worktree + commit_enabled` 自动本地提交前，进行有界 Git 文件清单扫描；敏感名称（环境/密钥/认证文件）、异常未跟踪链接、超大文件或大量文件均拒绝暂存，留给人工检查。这是**保守防护**而非完整 secrets 检测器，仍不能替代人工审查及专用密钥扫描。
- 权限、远程 Push/PR、模型费用和设备操作的授权条件不因这两个安全补丁改变。

### 13.1 飞书事件与任务 ID 原子登记

消息去重 ID 与新任务的 queued 记录在同一个 SQLite `BEGIN IMMEDIATE` 事务提交；如果创建任务或来源记录失败，整个事务回滚，不留下“已收消息但无任务”的去重记录。若接收后进程在私有输入 spool 持久化前崩溃，保留原来的 fail-closed `unknown` 处理，**不自动猜测提示或重复调用模型**。这是同机可靠性保障，不等于真实飞书重连资格。

## 无飞书项目企业 API 权限时：工作项人工登记（可选）

`manual_workitems_enabled` 在策略中默认 `false`。它**不申请**飞书项目、TAPD、卡片或额外模型权限；如果当前已授权的应用机器人能正常收发消息，管理员可在现有私有策略文件内设置 `"manual_workitems_enabled": true`，并按原第 5 节验证和重启已有的**唯一** Bot。该能力不会新增第二个进程或 WebSocket 消费者。

聊天中可发送：

```text
/wi help
/wi add tapd 缺陷 10104801 123456 repo=robot-app | 低速回充过流；复现、预期和验收条件
/wi add feishu_project 需求 project123 98765 repo=robot-app | OTA回滚需求和验收条件
/wi list
/wi status <AgentRun完整ID>
```

实际仓库别名必须是当前策略允许的值，示例 `robot-app` 不代表已在你的生产策略登记。不写 `repo=` 时继承用户当前项目。工作项 ID 和空间由发送者填写，**不会自动读取/验证** 飞书项目或 TAPD 中的内容；本地独立 0600 数据库只保存消息 ID、来源元数据和摘要哈希，不保存明文需求。来源状态是“用户提供，未核验”。单独批准的分析/开发仍走原有 Codex 权限检查，`/wi` 本身不启动任何模型、写代码或关闭缺陷。

如果连现有应用机器人的接收消息权限也没有，不能把仅能单向推送的自定义 Webhook 机器人当成双向聊天助手。此时使用 `python -m tools.codex_assets.feishu_engineering_agent --manual` 的本地 stdin CLI；完整示例和能力边界参见 `docs/changes/20261120-feishu-engineering-agent/pilot.md`。勿使用非授权的网页登录态、cookie 或企业账号进行绕过。

### 无企业 API：从登记到研发交接

`/wi add` 返回的完整 `AgentRun` ID 可以用于 `/wi handoff <RunID> | 最新需求/复现/验收信息`。机器人会返回按需求或缺陷分类的**只读研发交接草稿**，包括仓库、工作项身份、SDD 或复现/负向测试方向；不会启动模型或自动执行代码。旧 Codex 执行仍需独立授权，操作人再在本地 Codex CLI/既有研发渠道明确发起。交接内容不存入新 SQLite，工作项原系统的权限和最终 QA/关闭仍归产品、测试负责人。

## SDD 代码批次：工作项到独立 AgentRun 与可选卡片

`/wi add` 仅登记来源工作项；`/wi handoff` 仅输出只读研发交接草稿；`/wi attempt <原始RunID> <read|review|edit> | 本次范围和验收` 仅新建一个 `proposed` 的独立 Run。三者都不会自动执行模型。实际排队/执行必须经过外部签名 SDD+范围+仓库+费用门禁，并在真实 Codex 主机上独立验证。原来的 `mode=edit` 命令仍按旧 Bot 权限运行，不会自动获得新 WorkItem 的签名授权。

卡片交互为可选开关 `engineering_cards_enabled=false`，不是企业 API 无权限场景的前置条件；需私有环境中的 `FEISHU_CARD_VERIFICATION_TOKEN` 和 `FEISHU_CARD_SIGNING_KEY_HEX`，且 `manual_workitems_enabled=true`。回调只记录待审批请求和状态，不是模型权限，切忌在未通过真实 SDK/应用权限试验时打开生产开关。

迁移、离线回滚演练、安全边界及验收门禁详见 `docs/changes/20261120-feishu-engineering-agent/pilot.md`。当前代码实施并不代表已经在 vstrong100 部署、授权收费或完成真实产品/QA 测试。

## 研发工作项模式（可选，默认关闭）
无需飞书项目/TAPD 企业 API，使用已授权的同一个飞书会话。以下为源码能力，尚需在实际主机资格验证。

| 命令 | 行为 |
|---|---|
| `/wi add tapd 缺陷 <空间ID> <工作项ID> repo=<别名> \| 描述` | 登记用户提供的来源，不调用模型 |
| `/wi handoff <来源RunID> \| 当前范围与验收` | 生成研发交接文本 |
| `/wi attempt <来源RunID> edit \| 精确范围` | 创建待授权执行记录 |
| `/wi continue <上一轮RunID> \| 新范围` | 建立同一 Codex thread 的后续回合 |
| `/wi status <RunID>`、`/wi list` | 查询真实研发状态 |
| `/wi cancel <尝试RunID>` | 取消提案/排队或请求终止精确运行进程 |
| `/wi delivery <尝试RunID> <PR号> <CI运行ID...>` | 只读核验本地提交对应的全部必需 CI |
| `/wi feedback <尝试RunID>` | 输出可复制的交付结果与证据 |

待授权回合由可信同 UID [MCP](feishu-agent-mcp.md) 提交精确范围；聊天提案本身不批准模型费用。独立 QA 后仅完成研发 Run，产品/测试在原系统决定是否关闭。卡片、企业 API、App Server 不是文本 + CLI 路径的前置条件。部署前暂停原 Bot 与所有 MCP 写入，按 [现场操作说明](changes/20261120-feishu-engineering-agent/pilot.md) 对双数据库、spool、配置备份并演练恢复；保留专用 CODEX_HOME 与活跃 worktree。不创建第二个 systemd 服务。

**部署权限注意：** 新版 Bot 状态 SQLite 新建为 0600，既有 DB、WAL/SHM 均须为服务用户拥有的私有普通文件；旧实例可能由较宽 umask 创建。暂停 Bot 与本机 MCP 写入，核对实际路径和所有者，再由操作者将相关现有文件权限收紧为 0600，不删除 WAL 或重建数据库。仓库 unit 新增 `UMask=0077`，不会自动更新用户已安装的 unit。`check` 会验证/初始化私有数据库和 spool；已有 WorkItem 任务关联但 sibling 数据库缺失时拒绝继续，先恢复配对备份。

### Linux 嵌套沙箱兼容性

现场 Codex CLI 0.171.0 在旧外层 Bubblewrap 的递归只读根挂载内运行时，内层 Bubblewrap 报 `setting up uid map: Read-only file system`。外层命令使用独立 PID namespace（`--unshare-pid`），在只读根之后挂载自身的 `/proc`（`--proc /proc`），不直接可写绑定宿主机 procfs。保留原有秘密目录掩蔽、受控 writable roots、Codex 内层 sandbox 和 systemd 安全配置。主机需要实际通过嵌套无模型 shell 探针；参数回归测试不能替代真实 Linux 命名空间验收。

### 链接与话题入口（终态重构第一阶段）

在现有 `manual_workitems_enabled=true` 时，直接发送 `https://project.feishu.cn/example-space/issue/detail/1000000001`、`story/detail/1000000002` 或租户 Wiki/Docx/Sheets 链接，程序先于普通任务入口识别引用。示例均为合成数据。TAPD 支持常见 `/{workspace}/prong/stories/view/{id}` 和 `/{workspace}/bugtrace/bugs/view/{id}` 形式，未进行企业租户接口现场验证。可在私有策略增加 `link_repositories`（来源 `feishu_project:<space>`/`tapd:<workspace>` -> 已授权仓库别名数组），不存在映射或有多个候选则在话题内 `/repo <alias>`。以 SDK root/thread、租户、chat、actor 精确隔离。同话题重复链接去重，不自动选择其他工作项或仓库；新事项另起话题。链接单独输入只登记。明确分析、审查、修复、开发或继续推进时，既有 agent_intake_enabled、独立计费身份及逐仓模式授权均满足才原子入队；Worker 再核对策略与来源摘要，文档复用既有 API 读取器，已补充的历史消息仅按精确身份/哈希读取，失败明确拒绝而不是丢弃。普通旧聊天模型入口在工程模式启用时停止。旧 /wi 命令仍为迁移诊断接口。远程队列及原生会话候选需完整 CI 和现场验证；旧 DB 合并、交付与冗余删除仍未完成。

同一研发话题发送“检查 CI”会从实际本地 edit 的 branch+commit 查找唯一关联 PR 和最新必需 workflow，并复用严格只读证据核验；没有配置仓库 GitHub delivery、PR/CI 不完整、当前版本变化时不宣称 PASS。“交付反馈”只返回当前本地提交及已观察的精确证据，不写原系统、不宣称产品验收。

完成实际冻结、备份和恢复后，管理员可使用 migration_cli `unify`（见终态 pilot）将旧工作项历史归档到现有 Bot SQLite。迁移标记生效后，旧 /wi 及旧 WorkItem MCP 执行入口停止；用户直接发送链接。原旧库保留离线恢复，不能再作为活动状态权威。
