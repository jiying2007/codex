# 全局 Agent 规则

细节见 `docs/codex-operating-model.md`、`docs/codex-asset-management.md`。优先级：用户要求 > 深层规则/README > 本文件 > skill/workflow。

## 1. 路由与执行
- 默认 adk-first、`token-lean`；外部参考只用于 intake/设计证据，不进入 runtime profile、workflow 或 fallback。
- 小任务直接实现验证；非平凡任务先冻结目标、边界、风险、验收与阻塞；长任务使用 `adk-planning-execution-loop`。
- 每场景仅一个 primary skill；需求、拆解、调试、review、完成验证使用对应 `adk-*`，收尾用 `session-wrap`。
- 可报告的实质产出需要持久化时，只允许通过 `rtk bash ~/codex/scripts/knowledge-provider.sh ...` 访问 Knowledge Provider；仅 Provider 明确返回成功语义才能声明已记录。不得依赖 Hub 内部目录、临时 receipt、缓存或实现脚本作为跨仓契约，也不得从 Git、路径、memory 或聊天身份推断主体。
- catalog 未命中时运行 `rtk bash ~/codex/scripts/skill-search.sh --query "<任务>" --profile token-lean --limit 3 --summary-json`；只加载选中项完整 `SKILL.md`，零命中可直接执行。

## 2. 上下文与知识
- 一个线程一个职责；范围或验收变化先更新目标。先摘要后原文，按 stable/dynamic/evidence/excluded 管理上下文。
- 项目事实、决策、runbook、release、debug 或长期结论优先通过 Provider Adapter 查询：
  `rtk bash ~/codex/scripts/knowledge-provider.sh context --cwd "$PWD" --query "<任务>" --task-type <type> --context-budget small --limit 3 --summary-json`
- Provider unavailable / route unresolved 必须 BLOCKED 或 NEEDS_REVIEW；不得把本地缓存或路径猜测升级为事实。耐久结论只能形成 reviewing candidate/proposal，或声明无可归档结论。
- final/apply/目标切换前运行 Runtime Control；按 `checkpoint`、`compact`、`replan`、`stop` 决策收口接力。automation 默认 disabled/report-only。

## 3. 命令与安全
- shell 必须经 `rtk`；手工源码、脚本、配置和文档修改用 `apply_patch`，禁用 heredoc、重定向、cat、tee、Python 写仓库文件。
- 修改前读局部规则；dirty 属于用户，不回退、覆盖或清理无关内容。
- 禁止破坏性命令、直接写 `.git`、硬编码密钥和不可信输入拼接。MCP/connector/GUI 必须声明 transport、权限、工具、deny-path、脱敏与回退；外部写单独审查。
- 新 Python 工具进 `tools.codex_assets`，shell 只转发；从非仓库 cwd 验证 help/dry-run。

## 4. 验证与运行资产
- 无新鲜证据不得声明完成、通过、可提交或可合并；共享/高风险逻辑升级回归。
- SSOT 是 `manifests/*.json` 与 `src/codex-home/`；build 禁止手改，第三方镜像必须从 exact 上游导入，不直接修改 `~/.codex`。
- source-to-live 依次执行 build、doctor、plan、apply dry-run、apply、check；receipt 必须绑定 source/build/target。最终运行 `runtime-control.sh gate --event final`。
- Runtime Control 的 `final/commit/apply/release` 仅代表 Codex Runtime 本地 conformance；不得推导 domain verification、产品 release-ready 或跨域 PASS。
- 不自动 commit/push/merge/rebase；提交格式 `<type>(scope): <中文动词摘要>`。

## 5. 资产与边界
- 仅 2–4 个边界独立任务并行；shared contract/schema/根配置/依赖/CI/lockfile 串行。
- ADK core 平台中立；`embedded-fullstack` 是 ADK Asset Profile，`token-lean/team-collab` 是 Codex Runtime Profile，身份必须分离。
- 新 ADK 导入必须绑定 canonical `jiying2007/agent-dev-kit`、exact provider commit 与 exact source/bundle identity；不得恢复旧 nested-repo、旧版本 alias 或历史 compatibility fallback。
- 归档只存脱敏、可复用结论和证据，不存 raw session/log/core/binary/credential。默认简体中文；先结论、动作、验证、阻塞。
