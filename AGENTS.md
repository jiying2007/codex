# 全局 Agent 规则

本文件只保留 Codex 每轮必须立即遵守的路由与硬边界。详细操作模型、manifest 分工和 runbook 见 docs/codex-operating-model.md、docs/codex-asset-management.md 与 docs/context-layout.md。

## 1. 优先级与默认模式

1. 当前会话用户明确要求
2. 当前仓库及更深层 AGENTS.md、README 和约定
3. 本文件
4. 已触发的 skill / workflow

- 默认 adk-first；已有 adk-* 等价能力时优先使用。Superpowers 仅在用户点名、adk 无覆盖、迁移回归或平台缺能力时，用 superpowers-compat 显式启用。
- 默认 profile 为 token-lean；保留 team-collab 作为完整 catalog 兼容 profile，不默认激活。
- 能直接实现并定向验证的小任务，不升级重流程；中大型任务先明确目标、边界、风险和验证，长任务用 adk-planning-execution-loop。
- 只读分析不进入实现流程；执行请求应持续到验收通过或出现真实阻塞。continue nonstop 不扩大权限边界。

## 2. 任务与 skill 路由

- 需求收敛：adk-requirements-triage；拆解：adk-task-breakdown。
- 根因未明、测试失败或异常行为：adk-systematic-debugging，先证据后修复。
- 测试策略：adk-test-strategy；review：adk-code-review-loop；提交/PR：adk-commit-pr-quality-gate。
- 完成前：adk-verification-before-completion；分支收尾：adk-branch-closeout。
- 并行与 worktree：adk-parallel-agent-governance、adk-worktree-governance；仅明确多 Agent/CSV TODO 场景用 codex-parallel-collab。
- 会话收尾优先 session-wrap；知识归档、memory、上下文接力分别路由到 adk-knowledge-archive、adk-memory-curator、adk-context-compress-handoff。
- 单次已完成任务的复盘或 memory candidate 生成以 adk-after-action-review 为 primary；跨 memories/AGENTS/归档的整理、审计、提升以 adk-memory-curator 为 primary。
- 嵌入式通用 core/log 取证优先 adk-offline-core-dump-triage 与 adk-embedded-remote-debug-log-triage；embedded-core-dump-triage 仅用于 PCR02/SigmaStar，embedded-log-triage 仅用于离线或粘贴日志文本。

每个场景只能有一个 primary skill；其他只能 supporting。常驻 catalog 未命中时先查受信 inventory：

~~~bash
rtk bash ~/codex/scripts/skill-search.sh --query "<任务>" --profile token-lean --limit 5 --summary-json
~~~

根据 why_selected 排除相邻候选后，只读取选中项 load_path 的完整 SKILL.md；references、scripts、assets 继续按需读取。延迟加载不授予写入、网络、凭证或审批权限。只有显式兼容请求才加 --include-fallback。若必须切换 team-collab，apply 后从新线程生效，当前线程不假设 catalog 已刷新。

本次使用专用 skill 时在回复中简短说明；未命中时说明未使用。skill 的详细触发、fallback 和组合关系以 manifests/skills.json、manifests/workflows.json 及路由门禁为准，不在本文件复制长清单。

## 3. 目标、上下文与产物

- 一个线程默认服务一个长期职责；目标或职责切换前先 context-preflight，必要时收口并新开线程。
- 强目标写清范围、非目标、成功标准、验证命令、可审查产物和阻塞条件；无验证机制的目标只能标为探索。
- 用户补充指令先判定 steer、queue 或 scope-change；改变范围或验收时先更新目标再继续。
- 优先输出 Markdown、diff、测试报告、CSV、截图等可审查产物，不只汇报过程。
- workflow、automation、subagent、eval、目标、prompt 与上下文状态的声明式入口见对应 manifests/*.json；等待型自动化默认 enabled=false 或 report-only，不自动发送、提交、发布、删除或覆盖。

## 4. 命令与文件硬规则

- 所有 shell 命令必须通过 rtk：允许 rtk <command> 或 rtk bash -lc "<command>"，不得裸跑 bash/git/rg/python 等。
- 手工创建或修改源码、脚本、配置和文档必须用 apply_patch；禁止 heredoc、重定向、cat、tee 或 Python 写仓库文件。
- 修改前先读局部规则和相关实现。已有 dirty 变更默认属于用户；不得回退、覆盖、清理无关内容。
- 不运行破坏性命令，不直接操作 .git，不硬编码密钥，不把不可信输入拼进 shell、SQL 或外部写操作。
- 新增 Python 工具优先进入 tools.codex_assets，scripts/*.sh 只定位 ROOT、注入 PYTHONPATH 并转发；从非仓库 cwd 至少验证一次 help/dry-run。
- MCP、connector、GUI 或登录态流程必须先声明 transport、权限/凭证边界、工具清单、deny-path、日志脱敏和回退；未经审查不得启用外部写操作。

## 5. 验证、交付与 Git

- 没有验证证据不得声称完成、通过、可提交或可合并。小改动至少定向验证；共享逻辑、高风险行为和新功能按风险升级回归。
- 验证无法执行时说明原因、影响和剩余风险。最终回复前优先运行 rtk bash ~/codex/scripts/final-ready.sh。
- 修改 ~/codex 的 AGENTS、skill、workflow、manifest、script 或 docs 后，走完整 source-to-live 链路：

~~~bash
rtk bash ~/codex/scripts/build.sh
rtk bash ~/codex/scripts/doctor.sh --scope all
rtk bash ~/codex/scripts/plan.sh --target ~/.codex --prune-stale --output ~/codex/build/apply-plan.json
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json --dry-run
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json
rtk bash ~/codex/scripts/check-routing-precedence.sh
rtk bash ~/codex/scripts/check.sh
~~~

- 不直接手改 ~/.codex。不自动 commit、push、merge 或 rebase。提交格式为 <type>(scope): <中文动词摘要>，摘要不超过 50 字且不加句号。

## 6. Token、Knowledge Hub 与连续性

- Token 是受限资源：先读目录、摘要、关键字段和局部窗口；不复述长日志、diff 或 JSON。
- 上下文分为 stable、dynamic、evidence、excluded；压缩必须保留最新目标、失效目标、原始证据路径、fallback 条件和最多 3 个下一步。
- 涉及项目事实、历史决策、runbook、发布、日志/core 排障或长期结论时，先做低 token Hub 预检：

~~~bash
rtk bash ~/knowledge-hub/tools/knowledge-context.sh --cwd "$PWD" --query "<任务>" --task-type <debug|archive|release|decision|runbook|source|validation|general> --context-budget small --limit 3 --summary-json
~~~

- 路由歧义、排序解释不足或高风险结论时，去掉 --summary-json 改用 --json，再按候选路径读取原文。Hub 当前事实高于 memory、raw session 和旧 archive provenance。
- 会产生长期结论的 debug、release、validation、decision 或 session 任务，完成或中断时写 Hub candidate，或明确“本次无可归档结论”。未经用户要求不得静默写 ~/.codex/memories。
- final/apply/目标切换前运行 session coach；出现 THREAD_LONG、CTX_PRESSURE、HOT 或 CRITICAL 时优先收口并新开线程。

## 7. 并行与领域边界

- 仅当任务能拆成 2–4 个边界清晰、写入互不冲突、可独立验证的子任务时并行；先声明 scope_read、scope_write、must_not_touch、阻塞条件和输出契约。
- shared contract、schema、根配置、依赖、CI 和 lockfile 默认串行。子任务完成不等于项目完成，主 Agent 必须整合并跑最终验证。
- adk core 平台中立；embedded-fullstack 是业务 profile，不把通用 Web/云原生任务误归为嵌入式。设备配套上位机可按嵌入式交付链处理。

## 8. Skill 与知识资产治理

- Codex skill 的 SSOT 是 manifests/skills.json，源码在 src/codex-home/vendor/skills/<name>/<version>/；build 为生成物，禁止手改。
- 本地/Chronicle 派生 skill 可持续迭代；adk-*、Superpowers 和第三方资产必须从上游新版本重新导入，不静默修改镜像。
- routing 问题优先改 description/manifest，流程问题改 SKILL.md，长证据进 Knowledge Hub。批量变更后运行 rtk bash ~/codex/scripts/check-skills.sh。
- 归档只保存脱敏、可复用的背景、约束、决策和验证；一次性日志、raw session、cache、二进制和凭证不进入长期知识。

## 9. 输出风格

- 默认简体中文，技术标识保留英文。
- 先给结论、动作、验证和阻塞；分析说明依据与权衡，执行说明证据与剩余风险。
- 复杂任务用计划维护高层进度，任一时刻仅一个 in_progress。
