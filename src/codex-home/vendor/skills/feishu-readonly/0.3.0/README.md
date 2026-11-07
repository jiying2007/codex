# feishu-readonly

本地只读路由和执行边界，复用官方 `larksuite/cli`，不重复实现飞书 API、文档块解析或 CSV 引擎。
官方 `lark-doc`、`lark-sheets`、`lark-shared`、`lark-wiki`、`lark-drive`、`lark-okr` 作为 intake/设计来源；按当前 AGENTS 不直接加入默认 runtime。上游包含写入及 user 身份流程，本地默认仅 bot 只读。

后端冻结为 v1.0.97 / commit `72579c80027c863ca51d5f9affda72a70ab0d8a6`，MIT。安装身份与校验和登记在 `manifests/feishu_cli.json`。
本地源码：`tools/codex_assets/feishu_cli_read.py`；入口：`scripts/feishu-read.sh`。
上传文件由 `tools/codex_assets/feishu_cli_files.py` 组织文本解码与覆盖；仍由官方CLI下载/预览，不复制其文件传输API。新增的 drive +download/+preview 经本机v1.0.97帮助和具体文件实测，不依赖新版CLI升级。正文仅在私有临时目录处理；文件哈希绑定的是下载得到的表示内容，不冒充原生文档revision。
配置来自本机既有私有应用凭据，不含在 Skill 中。失败时不自动登录，不切换身份。

OKR由tools/codex_assets/feishu_cli_okr.py核验周期映射、有界分页及目标/KR父子关系；仅接入三个只读接口，不提供写入或文档式会话恢复。详见references/okr-reading.md。

```bash
rtk bash ~/codex/scripts/feishu-read.sh inspect --url '<飞书链接>' --dry-run
```

关闭时在 skills manifest 禁用本 Skill，并通过原受管 apply plan 回滚；后端缺失或哈希变化会拒绝读取。原机器人和原 read-source 入口独立保留。
