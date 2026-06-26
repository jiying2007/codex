# Codex Context Layout

本文件定义上下文压缩、会话接力和强目标恢复时的上下文分层。目标是让下一轮 Codex 能快速区分稳定事实和短期状态，避免把临时日志提升成长期规则。

## 分层

| 层级 | 内容 | 默认去向 | 更新频率 |
| --- | --- | --- | --- |
| Stable context | 用户稳定偏好、仓库硬规则、架构决策、长期边界、已验证工作流 | `AGENTS.md`、`~/knowledge-hub/domains/codex/archive/codex-archive/`、manifest | 低频，必须人工审查 |
| Dynamic context | 当前目标、分支状态、dirty worktree、最近验证、未闭环 blocker、下一步命令 | `context-preflight`、session summary | 高频，随线程变化 |
| Evidence context | 命令、退出码、报告路径、可复查产物、负结果 | final/commit evidence、archive note | 每次交付前更新 |
| Excluded context | 密钥、session 原文、长日志、缓存、一次性网页 dump、未经审查 memory | 不沉淀 | 永不提升 |

## Stable Context

稳定上下文必须满足至少一个条件：

- 多次任务重复出现，且已验证能减少错误。
- 属于仓库级硬约束，如命令必须通过 `rtk`。
- 属于长期接口或治理契约，如 manifest schema、workflow recipe、subagent contract。
- 属于人工确认后的偏好或决策。

稳定上下文不能直接从一次会话自动写入 memory。推荐路径是：

```text
conversation -> context-preflight -> ~/knowledge-hub/domains/codex/archive/codex-archive or manifest candidate -> review -> AGENTS / skill / memory
```

## Dynamic Context

动态上下文用于恢复当前工作，不应长期污染规则层。它必须包含：

- 当前目标和目标强度。
- 范围、非目标和停止条件。
- dirty worktree 摘要。
- 最近验证命令与结果。
- 下一条可执行命令。
- 未决问题和阻塞条件。

动态上下文过期后应由新的 `context-preflight` 替换，而不是持续追加。

## Evidence Context

交付声明必须绑定证据。推荐记录：

- 命令：完整可复跑命令。
- 结果：退出码和摘要。
- 工件：测试报告、governance report、apply plan、截图或 diff。
- 负结果：至少记录一个被排除的失败路径或防回归样例。

## Promotion Gate

将上下文提升为长期规则前，必须满足：

- 来源可追溯。
- 已脱敏并完成 secret scan。
- 有验证命令或可复查产物。
- 有回退方式。
- `manifests/guidance_promotions.json` 中存在匹配的提升策略。
- `manifests/context_state_contracts.json` 中存在匹配的上下文状态契约，且没有把 dynamic 或 excluded context 误提升为 stable context。

## Preflight 输出

`scripts/context-preflight.sh` 必须显式输出 Stable、Dynamic、Evidence 和 Excluded 四段。恢复线程时优先读取 Dynamic；修改规则或记忆时优先读取 Stable 和 Promotion Gate。
