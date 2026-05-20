> 本次人工裁决：该报告只用于审计与回看，不采纳任何正向记忆候选；所有自动候选均需人工复核，低复用路径、临时组织方式和一次性过程噪音直接 drop。

# Memory Curation 2026-05-17 18:01:22 +0800

本报告用于周期性整理 Codex memories、项目 AGENTS、会话总结和决策记录。
默认只产出审计材料，不直接修改 `~/.codex/memories` 或 `AGENTS.md`。

- Repo: `/home/leiwenjun/codex`
- Memories: `/home/leiwenjun/.codex/memories`
- Window: `14` days hint

## 输入概览

- Memory files: `1`
- codex-agent-mem files: `0`
- AGENTS files: `2`
- Archive files: `57`
- Decision-like docs: `10`

## Memory 文件

- `llm-tools.md`

## codex-agent-mem 候选输入

- 无

## AGENTS 文件

- `AGENTS.md`
- `src/codex-home/AGENTS.md`

## 候选知识来源

- `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md`
- `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md.meta.json`
- `docs/archive/daily-summary/index.md`
- `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md`
- `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md.meta.json`
- `docs/archive/debug-notes/index.md`
- `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md`
- `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md.meta.json`
- `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md`
- `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md.meta.json`

## 可复用信号摘录

### `AGENTS.md`

- # 全局 Agent 规则
- 本文件用于约束自动化代理在本机工作区中的默认工作方式，并将 Superpowers 作为主工作流体系按需激活。
- ## 指令优先级
- 2. 仓库自身规则、文档与约定
- - 本文件保留个人硬门禁、环境约束、交付偏好与沟通方式。
- - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。
- ## 默认原则
- ### 最短路径与并行轻重分流
- - 能直接完成并验证的，不升级为更重流程。
- ### 轻量任务默认策略（Codex / Superpowers）
- - 默认可跳过完整 `brainstorming`、`writing-plans`、`using-git-worktrees` 与重 review 链，直接实现并做定向验证；仅在关键不确定且无法从当前对话、项目上下文、`AGENTS.md`、现有代码回答时才提问。
- - 提问：轻量任务首次最多问 1 个关键问题；中任务优先一次性给出 2 到 3 个方案与推荐；已有上下文可回答的信息不重复提问；若未获回复且风险可控，应说明假设后继续推进。

### `src/codex-home/AGENTS.md`

- # 全局 Agent 规则
- 本文件用于约束自动化代理在本机工作区中的默认工作方式，并将 Superpowers 作为主工作流体系按需激活。
- ## 指令优先级
- 2. 仓库自身规则、文档与约定
- - 本文件保留个人硬门禁、环境约束、交付偏好与沟通方式。
- - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。
- ## 默认原则
- ### 最短路径与并行轻重分流
- - 能直接完成并验证的，不升级为更重流程。
- ### 轻量任务默认策略（Codex / Superpowers）
- - 默认可跳过完整 `brainstorming`、`writing-plans`、`using-git-worktrees` 与重 review 链，直接实现并做定向验证；仅在关键不确定且无法从当前对话、项目上下文、`AGENTS.md`、现有代码回答时才提问。
- - 提问：轻量任务首次最多问 1 个关键问题；中任务优先一次性给出 2 到 3 个方案与推荐；已有上下文可回答的信息不重复提问；若未获回复且风险可控，应说明假设后继续推进。

### `/home/leiwenjun/.codex/memories/llm-tools.md`

- # llm_tools memory
- ## Project Facts
- ## Git Workflow
- ## Tool Governance
- ## Release Boundaries

### `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md`

- # 2026-05-10 Codex V2 日总结
- ## 摘要
- ## 已完成
- ## 今日提交
- ## 当前决策
- - `src/codex-home/` 不承载知识归档，只承载可注入、可构建、可验证的 Codex Home 资产。
- ## 验证
- - `archive-note` dry-run 已验证。
- - 敏感文件拒绝归档已验证。
- ## 后续建议
- - 当某类知识反复复用时，再提升为 docs 正文、AGENTS 规则或 skill。

### `docs/archive/daily-summary/index.md`

- # Daily Summary

### `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md`

- # Windows 构建机 Runbook
- 本 runbook 用于维护 `llm_tools` 的内网 Windows 构建机。权威目标是 Windows x64 发布。
- ## 目标边界
- - x86 不进入默认发布基线；如需验证，必须显式设置 `WIN_BUILD_X86=1` 并单独记录结果。
- ## 构建机要求
- ## SSH 接入注意事项
- - 若目标用户属于 Administrators 组，Windows OpenSSH 默认使用：
- - 授权文件必须是单行公钥，且 ACL 只保留目标用户、SYSTEM、Administrators。
- ## 远程发布约束
- ## 已验证发布命令
- ## 排障结论
- - PySide6/PyInstaller 32-bit 发布链不稳定：x86 不进入默认发布目标。

### `docs/archive/debug-notes/index.md`

- # llm_tools Windows 构建机发布链路排障与发布边界

### `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md`

- # 2026-05-15 会话收口：音频崩溃排查与 docs/tools 落地
- ## 一、目标与范围
- ## 二、关键结论
- 2. `api_audio_player` 流层存在可导致错误数据传播/误判的健壮性缺陷，已修复并完成编译验证。
- ## 三、代码改动（本仓）
- ### 1) 音频流层修复
- ### 2) WAV 入口防御日志
- ## 四、文档与工具资产落地
- ### 1) runbooks（新增/增强）
- ### 2) tools/debug 脚本（新增）
- - `core-env-snapshot.sh`
- ### 3) tools 级技能体系

### `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md`

- # Session Wrap - Core 排障与 BusyBox 工具增强
- ## 会话范围
- - 目标: 连续排查多份 core，完善离线 gdb 与 BusyBox 现场排障工具链
- ## 已完成
- ## 关键结论
- ## 验证证据
- ## 风险与未决
- - 目标机共享库与主机路径不全时，某些 core 仍有符号缺失，建议补齐 `/customer/lib`、`/lib`、`/usr/lib` 到本地 sysroot。
- ## 下一步（Top 3）
- ## 关键产物路径


## 自动结晶候选

| Source | Insight | Promote Target |
| --- | --- | --- |
| `AGENTS.md` | # 全局 Agent 规则 | `archive/memory-review` |
| `AGENTS.md` | 2. 仓库自身规则、文档与约定 | `archive/memory-review` |
| `src/codex-home/AGENTS.md` | # 全局 Agent 规则 | `archive/memory-review` |
| `src/codex-home/AGENTS.md` | 2. 仓库自身规则、文档与约定 | `archive/memory-review` |
| `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | ## 当前决策 | `archive/memory-review` |
| `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | - `src/codex-home/` 不承载知识归档，只承载可注入、可构建、可验证的 Codex Home 资产。 | `archive/memory-review` |
| `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | - x86 不进入默认发布基线；如需验证，必须显式设置 `WIN_BUILD_X86=1` 并单独记录结果。 | `AGENTS` |
| `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | 2. `api_audio_player` 流层存在可导致错误数据传播/误判的健壮性缺陷，已修复并完成编译验证。 | `archive/memory-review` |
| `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | ## 验证证据 | `archive/memory-review` |

## 未决张力候选

| Source | Tension | Suggested Follow-up |
| --- | --- | --- |
| `AGENTS.md` | - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。 | 先补验证、补上下文或保持 archive-only |
| `src/codex-home/AGENTS.md` | - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。 | 先补验证、补上下文或保持 archive-only |

## 候选整理动作

- `promote-to-agents`：跨会话行为规则、硬约束、反复验证的工作方式
- `manual-review-only`：仅表示需要人工复核，不代表允许自动写入长期 memory
- `archive-only`：长文章、日报、调研证据、排障叙事、历史背景
- `drop-or-review`：一次性过程噪音、过期 TODO、机器私有状态、需要人工判断的信息

## 阶段模型

- Phase 1 报告归档：默认阶段，只生成 `docs/archive/` 归档和本审计报告
- Phase 2 手动写入：人工确认后才写入 `~/.codex/memories` 或 codex-agent-mem note/snapshot
- Phase 3 任务闭环：会话开始读取 context，会话结束执行 `knowledge-archive + memory-curator`

## 动作建议矩阵

| Action | Source | Signal |
| --- | --- | --- |
| `archive-only` | `AGENTS.md` | # 全局 Agent 规则 |
| `archive-only` | `AGENTS.md` | 本文件用于约束自动化代理在本机工作区中的默认工作方式，并将 Superpowers 作为主工作流体系按需激活。 |
| `archive-only` | `AGENTS.md` | ## 指令优先级 |
| `archive-only` | `AGENTS.md` | 2. 仓库自身规则、文档与约定 |
| `archive-only` | `AGENTS.md` | - 本文件保留个人硬门禁、环境约束、交付偏好与沟通方式。 |
| `manual-review-only` | `AGENTS.md` | - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。 |
| `archive-only` | `src/codex-home/AGENTS.md` | # 全局 Agent 规则 |
| `archive-only` | `src/codex-home/AGENTS.md` | 本文件用于约束自动化代理在本机工作区中的默认工作方式，并将 Superpowers 作为主工作流体系按需激活。 |
| `archive-only` | `src/codex-home/AGENTS.md` | ## 指令优先级 |
| `archive-only` | `src/codex-home/AGENTS.md` | 2. 仓库自身规则、文档与约定 |
| `archive-only` | `src/codex-home/AGENTS.md` | - 本文件保留个人硬门禁、环境约束、交付偏好与沟通方式。 |
| `manual-review-only` | `src/codex-home/AGENTS.md` | - 若用户明确要求 `continue nonstop`，默认持续推进，直到满足验收标准或出现真实阻塞。 |
| `archive-only` | `/home/leiwenjun/.codex/memories/llm-tools.md` | # llm_tools memory |
| `archive-only` | `/home/leiwenjun/.codex/memories/llm-tools.md` | ## Project Facts |
| `archive-only` | `/home/leiwenjun/.codex/memories/llm-tools.md` | ## Git Workflow |
| `archive-only` | `/home/leiwenjun/.codex/memories/llm-tools.md` | ## Tool Governance |
| `archive-only` | `/home/leiwenjun/.codex/memories/llm-tools.md` | ## Release Boundaries |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | # 2026-05-10 Codex V2 日总结 |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | ## 摘要 |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | ## 已完成 |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | ## 今日提交 |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | ## 当前决策 |
| `archive-only` | `docs/archive/daily-summary/20260510-094820-codex-v2-knowledge-archive-summary.md` | - `src/codex-home/` 不承载知识归档，只承载可注入、可构建、可验证的 Codex Home 资产。 |
| `archive-only` | `docs/archive/daily-summary/index.md` | # Daily Summary |
| `archive-only` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | # Windows 构建机 Runbook |
| `manual-review-only` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | 本 runbook 用于维护 `llm_tools` 的内网 Windows 构建机。权威目标是 Windows x64 发布。 |
| `manual-review-only` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | ## 目标边界 |
| `promote-to-agents` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | - x86 不进入默认发布基线；如需验证，必须显式设置 `WIN_BUILD_X86=1` 并单独记录结果。 |
| `archive-only` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | ## 构建机要求 |
| `archive-only` | `docs/archive/debug-notes/20260516-222503-windows-builder-runbook.md` | ## SSH 接入注意事项 |
| `archive-only` | `docs/archive/debug-notes/index.md` | # llm_tools Windows 构建机发布链路排障与发布边界 |
| `archive-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | # 2026-05-15 会话收口：音频崩溃排查与 docs/tools 落地 |
| `manual-review-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | ## 一、目标与范围 |
| `archive-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | ## 二、关键结论 |
| `archive-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | 2. `api_audio_player` 流层存在可导致错误数据传播/误判的健壮性缺陷，已修复并完成编译验证。 |
| `archive-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | ## 三、代码改动（本仓） |
| `archive-only` | `docs/archive/session-wrap/20260515-142200-session-wrap-crash-debug-tools.md` | ### 1) 音频流层修复 |
| `archive-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | # Session Wrap - Core 排障与 BusyBox 工具增强 |
| `archive-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | ## 会话范围 |
| `manual-review-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | - 目标: 连续排查多份 core，完善离线 gdb 与 BusyBox 现场排障工具链 |
| `archive-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | ## 已完成 |
| `archive-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | ## 关键结论 |
| `archive-only` | `docs/archive/session-wrap/20260515-154658-session-wrap-core-debug-and-busybox-tools.md` | ## 验证证据 |

## 人工审核清单

- 是否存在敏感信息需要删除
- 是否有过期规则需要废弃
- 是否有高频经验应提升为 AGENTS 规则
- 是否有稳定 insight 应沉淀为 crystallized insight
- 是否有未决 tension 需要在下次会话恢复时优先展开
- 是否有短小结构化状态应手动写入 codex-agent-mem note/snapshot
- 是否有长材料应只保留在 `docs/archive/`
- 不要自动双写到 `~/.codex/memories` 与 codex-agent-mem

## 本次人工过滤结论

本报告只作为审计材料，不触发任何自动记忆写入。

明确排除进入长期 memory 或 memory candidate 的内容：

- 个人工作区绝对路径
- 临时阶段性仓库组织方式
- 一次性迁移过程细节
- 低复用环境状态或偶发现象
- 仅对本次会话有效、后续会造成干扰的信息

可保留为长期规则的只有抽象后的工作方式：

- 会话归档与记忆整理默认 report-only
- 只有跨会话反复复用、可验证、低噪音的规则才允许进入 memory candidate
- 技术知识库治理应优先沉淀结构边界、质量门禁、验证入口和维护约束
- 明确被用户标记为低质量或有干扰的信息必须 drop，不得正向记忆

本次未执行 `--write-memory-candidate`，未修改 `~/.codex/memories`。
