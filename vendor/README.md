# vendor 目录

第三方能力实体统一放在 `vendor/`，`.codex` 根目录不保留第三方入口链接。
`skills/` 与 `agents/` 仅通过软链接激活。

- `vendor/skills/`：技能实体（按 name/version 分层）
- `vendor/agents/`：代理定义实体
- `vendor/plugins/`：外部插件镜像入口
- `vendor/lock/`：版本锁与来源记录
