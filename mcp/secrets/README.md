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

从 `mcp/feishu-codex-bot.example.json` 复制本地策略文件，并设为 `600`。`FEISHU_BOT_CONFIG` 必须显式指向该文件；仓库、全局/仓库级白名单、模式、队列、SQLite 和锁只有这一处策略来源。

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

旧单仓 `FEISHU_CODEX_WORKDIR`、`FEISHU_ALLOWED_OPEN_IDS` 配置已退役。将实际仓库与白名单写入私有策略后删除这两个环境字段；不再从环境生成隐含仓库或覆盖策略白名单。

文件权限必须为 `600`。检查配置不会连接飞书：

```bash
rtk bash scripts/feishu-codex-bot.sh check
```

不知道本人 Open ID 时，启动只读发现模式，然后在目标会话中给机器人发送一条文本消息；终端输出 `allowed_open_ids` JSON 字段，可核对后写入私有策略。该模式不会回复消息或运行 Codex：

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

同一仓库任务串行，不同仓库最多按 `worker_count` 并行。现役任务只使用一个私有 SQLite；必要的补充正文与完成输出按摘要校验、有限保存 7 天，队列输入在私有 spool，原生会话在专用 CODEX_HOME。备份、WAL 与原生会话同样属于私有数据，不进入 Git 或公共日志。

只读 GitHub 交付核验使用可选的 `FEISHU_AGENT_GITHUB_READ_TOKEN`。需要受控发布时，逐仓明确开启 `github_delivery.publish_enabled`，并在同一私有环境文件中提供独立的 `FEISHU_AGENT_GITHUB_WRITE_TOKEN`；凭据须只授权目标仓库的 Contents 与 Pull requests 写入。该凭据仅供控制器使用，不传给模型或验证命令。执行入口、发布入口均默认关闭，发布还要求可信话题中的完整提交 SHA 命令。配置和现场步骤见使用指南。

systemd user unit 模板位于 `mcp/systemd/feishu-codex-bot.service`。安装后使用：

```bash
systemctl --user daemon-reload
systemctl --user enable --now feishu-codex-bot.service
systemctl --user status feishu-codex-bot.service
journalctl --user -u feishu-codex-bot.service -f
```
