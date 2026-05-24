# Session Continuity Coach 最佳实践

Session Continuity Coach 是一个轻量、常驻的会话连续性规则集。目标不是增加噪音，而是在关键边界提醒下一步最有价值的动作：压缩上下文、新开会话、归档、记忆整理、AGENT/SKILL/DOC/SCRIPT 同步、运行态 apply 和省 token。

## 常驻原则

- `AGENTS.md` 负责常驻提醒规则；它在会话中持续生效。
- `scripts/session-coach.sh` 负责低成本诊断，输出下一步建议。P2 版本会识别阶段、排序 Top action、对重复中低优先级提醒做冷却。
- `manifests/session_coach.json` 负责阈值、事件和敏感信息模式配置，避免在代码中硬编码策略。
- `.cache/session-coach-state.json` 保存提醒冷却状态，不纳入 Git；需要重新评估时使用 `--reset-state`。
- `.cache/session-coach-evidence.json` 保存 ready wrapper 写入的近期验证证据，不纳入 Git。
- `--fail-on critical|high|medium|info` 可把提醒升级为可选硬门禁；默认 `never`，避免长会话提醒阻断普通诊断。
- `usage-report.sh` / `usage-tail.sh` 负责 token 观测。
- `context-preflight.sh`、`session-wrap`、`archive-note`、`scripts/curate-memory.sh --dry-run` 负责会话收口。
- `build -> doctor -> plan/dry-run -> apply -> diff/drift -> check` 负责 Codex 资产变更闭环。
- `docs/codex-operating-model.md` 负责常驻线程、强目标、可审查产物、自动化边界和 MCP 治理的操作层约定。

## 推荐触发点

运行或主动提醒 `rtk bash scripts/session-coach.sh`：

- 会话开始、恢复、目标切换时。
- 长任务进入新阶段前。
- 目标从探索升级为强目标，或用户把指令改成等待型/周期性自动化时。
- 准备 final、commit、push、apply 前。
- 修改 `AGENTS.md`、skill、workflow、manifest、script 或 docs 后。
- `usage-tail` 进入 `HOT` / `CRITICAL`，或最近一次输入明显过大时。
- `~/.codex` 与 `~/codex` 可能发生 drift、stale 或 unmanaged 时。

需要更完整证据时运行：

```bash
rtk bash scripts/session-coach.sh --deep
rtk bash scripts/session-coach.sh --deep --json
rtk bash scripts/session-coach.sh --deep --top 5
rtk bash scripts/session-coach.sh --event final --deep
rtk bash scripts/session-coach.sh --event commit --deep
rtk bash scripts/session-coach.sh --event push --deep
rtk bash scripts/session-coach.sh --event apply --deep
rtk bash scripts/session-coach.sh --event commit --deep --fail-on high
rtk bash scripts/session-coach.sh --reset-state
rtk bash scripts/session-coach.sh --ack ARCHIVE_REVIEW
rtk bash scripts/session-coach.sh --clear-acks
```

ready wrapper：

```bash
rtk bash scripts/final-ready.sh
rtk bash scripts/commit-ready.sh
rtk bash scripts/apply-ready.sh
SESSION_COACH_FAIL_ON=high rtk bash scripts/commit-ready.sh
```


## 智能判断模型

P2 版本按以下顺序综合判断：

1. `phase`：优先识别 `apply`、`commit`、`asset-update`、`handoff`、`archive`、`steady`。
2. `signals`：融合 token 压力、Git 路径类型、暂存区、build/live drift、archive 积压。
3. `priority`：每条提醒带优先级，默认只输出 Top 3，避免 checklist 噪音。
4. `cooldown`：同一 fingerprint 的 `MEDIUM/INFO` 重复提醒会被抑制；`HIGH/CRITICAL` 保留但标记 repeated。
5. `commands`：每条高价值提醒给出可执行命令，便于直接进入下一步。
6. `event`：支持 `final`、`commit`、`push`、`apply`、`resume`、`target-switch`、`memory-curation`，用于在关键动作前提升判断准确性。
7. `evidence`：`final-ready`、`commit-ready`、`apply-ready` 会写入近期验证证据；事件模式下缺失或过期会提醒。
8. `ack`：对已确认的 `MEDIUM/INFO` 提醒可用 `--ack <CODE>` 降噪；`HIGH/CRITICAL` 不因 ack 静默。
9. `fail-on`：严格模式下任一提醒达到指定严重级别时返回非零退出码，供 CI 或提交前门禁使用。

路径级规则：

- 只改一侧 `AGENTS.md` 时提示同步根规则与 `src/codex-home/AGENTS.md`。
- 改 skill 或 `manifests/skills.json` 时提示运行 `check-skills.sh`。
- 改 agent 资产或 `manifests/agents.json` 时提示检查 agent manifest、openai.yaml 与 profile link。
- 改 MCP 资产或 `manifests/mcp_servers.json` 时提示检查声明、readiness、权限边界和运行态配置，避免提交 secrets。
- 改 `manifests/workflow_recipes.json` 或 `manifests/automations.json` 时提示检查 workflow 引用、审批策略、停止条件和 report-only 边界。
- 改 `manifests/subagent_contracts.json` 或 `manifests/memory_candidates.json` 时提示检查 agent 引用、读写边界、人工审查和 secret scan 门禁。
- 改 `scripts/` 或 `tools/` 时提示从非仓库 cwd 验证 help/dry-run。
- 改 workflow、schema 或 manifest 时提示 governance 检查。
- 改声明式交付资产时提示完整 `build -> doctor -> plan/dry-run -> apply -> diff/drift -> check`。
- 准备 `commit` 时检查是否已有暂存文件。
- 准备 `push` 时检查本地 ahead/behind、冲突状态和 dirty worktree。
- 准备 `final` 时提示尚未收口的工作区变更，避免最终答复遗漏交付状态。
- 改 `docs/archive/` 时检查 meta JSON、疑似敏感信息、超大归档和缺失 meta。

## 配置项

配置文件：`manifests/session_coach.json`。

- `top`：默认输出提醒数量。
- `warn_thread_tokens`：长线程阈值。
- `context_pressure_ratio`：最近一次输入占 context window 的压力阈值。
- `large_delta_tokens`：单次 token delta 过大阈值。
- `evidence_fresh_minutes`：ready wrapper 验证证据有效时间。
- `archive_max_bytes`：归档文件大小提醒阈值。
- `events`：事件到 phase 与 required evidence 的映射。
- `protected_archive_patterns`：归档敏感信息扫描模式。

## 提醒强度

- `CRITICAL`：优先收口并新开会话；不要继续堆上下文。
- `HIGH`：先处理交付边界、运行态漂移、声明式资产同步或 context 压力。
- `MEDIUM`：建议在本轮结束前整理归档、缩小读取范围或补验证。
- `INFO`：提示可选优化，不阻塞当前任务。

## 资产变更闭环

如果本轮改了：

- `AGENTS.md`：同步根仓与 `src/codex-home/AGENTS.md`，构建并 apply。
- skill：同步 `src/codex-home/vendor/skills/`、`manifests/skills.json`、`check-skills.sh`。
- workflow：同步 `manifests/workflows.json` 并运行 governance 检查。
- script / tool：保持 `scripts/*.sh -> tools.codex_assets` 包入口规范，从非仓库 cwd 验证帮助或 dry-run。
- docs：长期知识进 `docs/archive/`；交付规则进 `docs/` 正文；不要写入 `src/codex-home/`。

## 收口序列

长会话或高 token 压力时，优先执行：

```text
context-preflight -> session-wrap -> archive-note -> rtk bash scripts/curate-memory.sh --dry-run -> new session
```

只有用户明确要求写入候选 memory 时，才生成 `~/.codex/memories/.codex/curation-inbox/` 候选；默认不直接写长期 memory。
