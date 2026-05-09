# Codex Home Source

本目录是 `~/codex` v2 的人工维护源资产。它不会直接注入 `~/.codex`，必须先由仓库根目录的 `scripts/build.sh` 生成 `build/codex-home/`。

规则：

- 不保存 `skills/.system/`。
- 不保存认证、session、日志、缓存、密钥和本机私有配置。
- 第三方 skill 的正式源放在 `vendor/skills/<name>/<version>/`。
- `skills/` 只保留 README、registry 模板和维护脚本等基础文件。
- profile 激活入口由 build 阶段生成 symlink。
- `config/base.toml` 是 `config.toml` 的构建模板。
