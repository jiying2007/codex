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
- SQLite 不保存消息正文或 Codex 输出，只保存去重 ID、用户 ID、仓库别名、个人默认项目、模式和任务状态。

## 2. 当前仓库别名

| 别名 | 工作目录 | 模式 | edit 策略 |
| --- | --- | --- | --- |
| `codex` | `/home/leiwenjun/codex` | `explain`, `review` | - |
| `pcr02-demo` | `/vsdata/leiwenjun/work/sigmastar/pcr02_ssc305/SourceCode/sdk/verify/xcrz_sigmastar_demo` | `explain`, `review`, `edit` | `in_place` |
| `llm_apps` | `/home/leiwenjun/bin/llm_apps` | `explain`, `review`, `edit` | `in_place` |
| `x5` | `/vsdata/leiwenjun/work/rdk/x5` | `explain`, `review`, `edit` | `in_place` |

系统默认项目是 `llm_apps`。直接写任务会保留在当前仓库工作区中，便于本地立即审查；同一仓库一次只运行一个任务。
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

### 3.6 控制命令

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

未指定 `repo=` 时，优先使用发送者的个人默认项目；未设置或个人别名已经从白名单移除时，回退到策略文件的 `default_repo`，当前为 `llm_apps`。命令中的 `repo=<别名>` 只覆盖当前任务，不修改个人默认项目。未指定 `mode` 时默认使用 `explain`。

## 4. 配置文件

### 4.1 凭据文件

默认路径：

```text
/home/leiwenjun/codex/mcp/secrets/feishu.env
```

最小内容：

```dotenv
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=replace-me
FEISHU_TARGET_CHAT_ID=oc_xxx
FEISHU_BOT_NAME=AI助手
FEISHU_BOT_CONFIG=/home/leiwenjun/codex/mcp/secrets/feishu-bot.json
```

文件必须设置为 `600`，不得提交到 Git、粘贴到工单或输出到日志。

### 4.2 策略文件

默认本机路径：

```text
/home/leiwenjun/codex/mcp/secrets/feishu-bot.json
```

可提交的脱敏示例：[feishu-codex-bot.example.json](../mcp/feishu-codex-bot.example.json)。

添加仓库：

```json
{
  "default_repo": "llm_apps",
  "allowed_open_ids": ["ou_owner"],
  "repositories": {
    "llm_apps": {
      "path": "/home/leiwenjun/bin/llm_apps",
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

## 8. 状态与日志

状态数据库默认位于：

```text
mcp/secrets/feishu-codex-state.sqlite3
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
