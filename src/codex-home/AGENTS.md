# 全局 Agent 规则

细节见 `docs/codex-operating-model.md`、`docs/codex-asset-management.md`。优先级：用户要求 > 深层规则/README > 本文件 > skill/workflow。

## 1. 路由与执行

- 默认 adk-first、`token-lean`；Superpowers 仅在点名、adk 无覆盖、迁移回归或平台缺能力时启用 `superpowers-compat`。
- 小任务直接实现验证；非平凡任务冻结目标、边界、风险、验收和阻塞；长任务用 `adk-planning-execution-loop`。
- 每场景仅一个 primary skill；需求/拆解/调试/review/完成验证用对应 `adk-*`，收尾用 `session-wrap`。
- catalog 未命中时运行 `rtk bash ~/codex/scripts/skill-search.sh --query "<任务>" --profile token-lean --limit 3 --summary-json`；只读选中项完整 `SKILL.md`。零命中可直接执行，延迟加载不扩权。

## 2. 上下文与知识

- 一个线程一个职责；范围/验收变化先更新目标，计划仅一个 `in_progress`。
- 先摘要后原文，不复述长日志/diff/JSON；按 stable/dynamic/evidence/excluded 管理，压缩保留目标、证据、fallback 和最多 3 个下一步。
- 项目事实、决策、runbook、release、debug 或长期结论先运行：

```bash
rtk bash ~/knowledge-hub/tools/knowledge-context.sh --cwd "$PWD" --query "<任务>" --task-type <type> --context-budget small --limit 3 --summary-json
```

- 已知项目加 `--project`；仅歧义/高风险回退 `--json` 与原文。耐久结论写 reviewing candidate，或声明无可归档结论；不得静默写 memory。
- final/apply/目标切换前运行 Runtime Control；按 `checkpoint`、`compact`、`replan`、`stop` 决策优先收口接力。automation 默认 disabled/report-only。

## 3. 命令与安全

- shell 必须经 `rtk`；手工源码、脚本、配置和文档修改用 `apply_patch`，禁用 heredoc、重定向、cat、tee、Python 写仓库文件。
- 修改前读局部规则；dirty 属于用户，不回退、覆盖或清理无关内容。
- 禁止破坏性命令、直接写 `.git`、硬编码密钥和不可信输入拼接。MCP/connector/GUI 先声明 transport、权限、工具、deny-path、脱敏与回退；外部写另审。
- 新 Python 工具进 `tools.codex_assets`，shell 只转发；从非仓库 cwd 验证 help/dry-run。

## 4. 验证与运行资产

- 无新鲜证据不得声明完成/通过/可提交/可合并；共享或高风险逻辑升级回归。
- SSOT 是 `manifests/*.json`、`src/codex-home/`；build 禁止手改，第三方镜像从上游导入，不手改 `~/.codex`。
- source-to-live 必须依次执行 build、`doctor --scope all`、plan、apply dry-run、apply、`check.sh --no-build --plan`；receipt 必须绑定 source/build/target，失败即重建或重规划。最终运行 `runtime-control.sh gate --event final`。
- 不自动 commit/push/merge/rebase；提交格式 `<type>(scope): <中文动词摘要>`，摘要不超过 50 字且无句号。

## 5. 并行与资产

- 仅 2–4 个边界独立任务并行；shared contract/schema/根配置/依赖/CI/lockfile 串行，主 Agent 整合。
- adk core 平台中立，`embedded-fullstack` 仅嵌入式链；routing 改 manifest，流程改 `SKILL.md`，长证据进 Hub。
- 归档仅存脱敏可复用结论和证据，不存 raw session/log/core/binary/credential。默认简体中文；先结论、动作、验证、阻塞。
