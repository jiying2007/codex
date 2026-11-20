# Codex Skill 中文显示说明

本仓当前管理的非 ADK Skill 均提供中文 `agents/openai.yaml:interface.display_name/short_description`。本次只调整 Codex 仓受管的界面文案，不改 `SKILL.md`、外部上游来源声明、Skill identity、权限、安装目标或默认 Profile。

ADK 来源 Skill 的中文显示由 ADK 11.4.16 的受信资产负责，不在 Codex 仓建立第二套翻译目录。正式导入时需要精确版本、签名验证和受保护 PR；不能通过直接覆盖 `~/.codex/skills` 达成。

这些 Git 源文件只证明构建源可用。用户实际 CLI 是否展示中文，以完成 `build → plan → apply → doctor`、新会话重新加载后的真实 UI 观察为准。外部来源的原方法及许可证保持不变。
