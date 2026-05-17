# Session Continuity Coach 最佳实践

Session Continuity Coach 是一个轻量、常驻的会话连续性规则集。目标不是增加噪音，而是在关键边界提醒下一步最有价值的动作：压缩上下文、新开会话、归档、记忆整理、AGENT/SKILL/DOC/SCRIPT 同步、运行态 apply 和省 token。

## 常驻原则

- `AGENTS.md` 负责常驻提醒规则；它在会话中持续生效。
- `scripts/session-coach.sh` 负责低成本诊断，输出下一步建议。
- `usage-report.sh` / `usage-tail.sh` 负责 token 观测。
- `context-preflight.sh`、`session-wrap`、`archive-note`、`scripts/curate-memory.sh --dry-run` 负责会话收口。
- `build -> doctor -> plan/dry-run -> apply -> diff/drift -> check` 负责 Codex 资产变更闭环。

## 推荐触发点

运行或主动提醒 `rtk bash scripts/session-coach.sh`：

- 会话开始、恢复、目标切换时。
- 长任务进入新阶段前。
- 准备 final、commit、push、apply 前。
- 修改 `AGENTS.md`、skill、workflow、manifest、script 或 docs 后。
- `usage-tail` 进入 `HOT` / `CRITICAL`，或最近一次输入明显过大时。
- `~/.codex` 与 `~/codex` 可能发生 drift、stale 或 unmanaged 时。

需要更完整证据时运行：

```bash
rtk bash scripts/session-coach.sh --deep
rtk bash scripts/session-coach.sh --deep --json
```

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
