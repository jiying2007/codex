# Local MCP and connector secrets

完整使用、配置、运维和排障说明见 [飞书 Codex AI助手使用指南](../../docs/feishu-codex-bot-usage.md)。

此目录只保存本机凭据，除本 README 外均被 Git 忽略。

`feishu.env` 最小配置：

```dotenv
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=replace-me
FEISHU_TARGET_CHAT_ID=oc_xxx
FEISHU_BOT_NAME=AI助手
FEISHU_BOT_CONFIG=/absolute/path/to/mcp/secrets/feishu-bot.json
```

从 `mcp/feishu-codex-bot.example.json` 复制本地策略文件，并设为 `600`。仓库别名、全局/仓库级白名单、只读模式、并发、限流、SQLite 和锁文件均在策略中配置。

全局白名单适用于所有仓库：

```json
{
  "allowed_open_ids": ["ou_owner"],
  "repositories": {
    "codex": {
      "path": "/home/user/codex",
      "allowed_modes": ["explain", "review"],
      "allowed_open_ids": []
    }
  }
}
```

仓库级 `allowed_open_ids` 非空时，会在全局白名单基础上进一步收窄。任何仓库没有有效白名单时，`check` 和 `start` 都会拒绝运行。

旧版单仓配置仍兼容：

```dotenv
FEISHU_ALLOWED_OPEN_IDS=ou_xxx
FEISHU_CODEX_WORKDIR=/absolute/path/to/repository
```

文件权限必须为 `600`。检查配置不会连接飞书：

```bash
rtk bash scripts/feishu-codex-bot.sh check
```

不知道本人 Open ID 时，启动只读发现模式，然后在目标会话中给机器人发送一条文本消息；终端会输出可复制的 `FEISHU_ALLOWED_OPEN_IDS`，该模式不会回复消息或运行 Codex：

```bash
rtk bash scripts/feishu-codex-bot.sh discover-owner
```

真实发送属于外部写操作，只有显式确认才执行：

```bash
rtk bash scripts/feishu-codex-bot.sh send-test --confirm-send
```

启动长连接：

```bash
rtk bash scripts/feishu-codex-bot.sh start
```

飞书使用示例：

```text
repo=codex mode=explain 说明仓库结构
repo=codex mode=review 审查当前改动
/status
/cancel
/help
```

同一仓库任务串行，不同仓库最多按 `worker_count` 并行。SQLite 仅保存消息 ID、发送者 Open ID、仓库别名、模式和状态，不保存消息正文或 Codex 输出。

systemd user unit 模板位于 `mcp/systemd/feishu-codex-bot.service`。安装后使用：

```bash
systemctl --user daemon-reload
systemctl --user enable --now feishu-codex-bot.service
systemctl --user status feishu-codex-bot.service
journalctl --user -u feishu-codex-bot.service -f
```
