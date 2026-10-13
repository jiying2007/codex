# feishu-readonly

本地只读路由和执行边界，复用官方 `larksuite/cli`，不重复实现飞书 API、文档块解析或 CSV 引擎。
官方 `lark-doc`、`lark-sheets`、`lark-shared`、`lark-wiki` 作为 intake/设计来源；按当前 AGENTS 不直接加入默认 runtime。上游包含写入及 user 身份流程，本地默认仅 bot 只读。

后端冻结为 v1.0.97 / commit `72579c80027c863ca51d5f9affda72a70ab0d8a6`，MIT。安装身份与校验和登记在 `manifests/feishu_cli.json`。
本地源码：`tools/codex_assets/feishu_cli_read.py`；入口：`scripts/feishu-read.sh`。
配置来自本机既有私有应用凭据，不含在 Skill 中。失败时不自动登录，不切换身份。

```bash
rtk bash ~/codex/scripts/feishu-read.sh inspect --url '<飞书链接>' --dry-run
```

关闭时在 skills manifest 禁用本 Skill，并通过原受管 apply plan 回滚；后端缺失或哈希变化会拒绝读取。原机器人和原 read-source 入口独立保留。
