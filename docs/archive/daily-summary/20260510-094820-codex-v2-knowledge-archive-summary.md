# 2026-05-10 Codex V2 日总结

## 摘要

今天围绕 `~/codex` 的 Codex Home v2 管理体系继续收敛，重点从“运行资产管理”扩展到“长期知识沉淀”。当前边界已经明确：`~/.codex` 是运行目录，`src/codex-home/` 是可注入资产源，长期知识进入 `docs/archive/`。

## 已完成

- 收敛 v2 control 边界，阻止 `archives`、`knowledge`、`roles`、`workflows` 等旧知识态目录回流到 `src/codex-home/control/`。
- 优化插件 skill 构建范围，仅复制 manifest 激活的 plugin skills，避免未声明 skill 被一起带入。
- 增加知识沉淀归档入口 `scripts/archive-note.sh` 和 CLI 子命令 `archive-note`。
- 固定知识归档路径为 `docs/archive/<topic>/`，每次归档生成材料、`.meta.json` 和主题 `index.md`。
- 增加安全边界：拒绝归档 `.codex` 运行态、session、日志、cache、tmp、密钥、`auth.json` 和 protected paths。

## 今日提交

- `5507e03 feat: 增加知识沉淀归档入口`
- `7b93ffe refactor: 收敛control为v2运行边界`
- `25b2e10 feat: 收敛插件技能构建范围`

## 当前决策

- `~/.codex` 不作为长期知识库，只作为运行目录。
- `src/codex-home/` 不承载知识归档，只承载可注入、可构建、可验证的 Codex Home 资产。
- `docs/archive/` 是长期知识沉淀区，适合保存脱敏后的总结、调研、排障记录和设计结论。
- skill 走 `inbox -> promote -> vendor -> manifest -> build -> apply`，普通知识走 `archive-note -> docs/archive/<topic>/`。

## 验证

- `rtk bash scripts/check.sh` 已通过。
- `archive-note` dry-run 已验证。
- 敏感文件拒绝归档已验证。
- 当前工作区在归档前为干净状态。

## 后续建议

- 对高价值会话总结固定归档到 `docs/archive/daily-summary/` 或更具体 topic。
- 对可复用排障经验沉淀为独立 topic，例如 `embedded-debug`、`codex-assets`、`mcp-integration`。
- 当某类知识反复复用时，再提升为 docs 正文、AGENTS 规则或 skill。
