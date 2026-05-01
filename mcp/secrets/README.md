# MCP Secrets

本目录不保存真实密钥。

建议做法：

1. 使用环境变量注入（例如 `GITHUB_PERSONAL_ACCESS_TOKEN`、`OPENAI_API_KEY`）。
2. 在 shell profile 或系统密钥管理中维护密钥。
3. `config.toml` 仅保留空值占位，避免泄露。
