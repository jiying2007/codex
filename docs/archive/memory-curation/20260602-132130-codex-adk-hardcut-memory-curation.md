# ADK Skill 命名硬切换记忆整理报告

- Captured at: 2026-06-02 13:18:31 Asia/Hong_Kong
- Source scope: 当前 Codex 会话、`agent-dev-kit@384610b`、`/home/leiwenjun/codex@d396628`、`/home/leiwenjun/.codex`
- Sanitization: 未包含 secrets、完整聊天记录、私有 token、原始 session 日志或 `.codex/sessions` 内容
- Mode: report-only with memory candidates

## Source Counts

- Repositories reviewed: 2
  - `agent-dev-kit`
  - `/home/leiwenjun/codex`
- Live runtime checked: 1
  - `/home/leiwenjun/.codex`
- Commits referenced: 2
  - `384610b refactor(skill): 规范化 Skill 命名边界`
  - `d396628 refactor(skill): 硬切换 ADK Skill 命名`
- Long-term memory writes performed: 0

## High Signal Findings

- ADK 资产 apply 的真实 source of truth 是 `/home/leiwenjun/codex`，不是 `agent-dev-kit` 或 `~/.codex`。
- skill 命名硬切换需要同时处理 manifest、registry、lock、vendor dirs、运行态 apply、旧 ID active scan。
- source 文件格式修复后，live 运行态可能重新出现可检测 DIFF；必须补 plan/apply/drift，而不是只跑单元测试。
- 旧 ID 残留扫描必须限定 active source/runtime 路径，否则历史聊天、session、cache 会产生假阳性。

## Duplicate/Stale Findings

- 旧 skill ID 已从 active source/runtime 清除；历史对话和 session 记录中可能仍有旧词，不属于 active 残留。
- `adk-repo-prompt-analysis` 与 `adk-skill-deep-analysis` 正文存在少量历史模板痕迹，建议回到 `agent-dev-kit` 上游修复后再同步。
- `THREAD_LONG` 已多次被 `final-ready` / `commit-ready` 标记，后续应新开线程继续。

## Memory Candidates

| Scope | Candidate | Evidence | Risk | Confidence | Write Route |
|---|---|---|---|---|---|
| codex asset governance | ADK asset apply 前必须确认 `/home/leiwenjun/codex` 已吸收目标 `agent-dev-kit` commit；如果 source stale，先同步 source，再 build/doctor/plan/dry-run/apply/check | 直接 apply 前发现 `/home/leiwenjun/codex` 仍含旧 skill ID；同步后才完成 hard-cut | medium | high | `manifests/memory_candidates.json` -> project rule or archive |
| codex live drift | managed source 文件在 live apply 后又被格式修复时，必须重新 plan/apply 并跑 drift；否则 `check.sh` 会在 live drift 阶段报告 DIFF | EOF 修复后出现 `overwrite=10`，正式 apply 后 `changed=0 stale=0 unmanaged=0` | low | high | `manifests/memory_candidates.json` -> project rule |
| codex residual scan | 旧 ID / 残留扫描结论只应基于 active source/runtime 路径；不要把 session logs、history 或 cache 中的历史文本当作 active 残留 | broad `~/.codex` scan 会命中历史消息；active-only scan 对 `AGENTS.md`、`skills`、`vendor/skills`、`manifests` 无匹配 | low | high | `manifests/memory_candidates.json` -> archive or project rule |

## Archive-only Items

- apply summary、测试细节和提交日志适合保留在归档，不适合写入长期 memory。
- 本轮具体旧 ID 列表已经写入归档，可作为审计证据，不需要重复提升为全局记忆。

## Drop/Review Items

- 不保存完整聊天记录。
- 不保存 `.codex/sessions`、cache、运行态日志原文。
- 不把本轮一次性命令输出作为 memory。

## Gate Result

pass: 仅生成候选和归档，不直接写入长期 memory。高信号候选需要人工确认后再提升到 `AGENTS.md` 或 `~/.codex/memories`。
