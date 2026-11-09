# codex-parallel-collab

面向 Codex CLI 的并行编排技能：先拆任务，再并行执行，最后统一收口验证。

## 适用场景

- 任务可拆成 2 到 4 个边界清晰的子任务
- 多文件独立改动、信息收集与实现可并行
- 需要明确 `owner / write_scope / verify` 的协作约束

## 快速开始

```bash
rtk echo '$codex-parallel-collab
目标: 完成 API 与服务层改造
范围: backend/api, backend/service
验收: 列出验证命令并执行
约束: 不改 CI 与依赖
先输出 CSV TODO，再按依赖批次并行执行。' \
| rtk codex exec --skip-git-repo-check --sandbox workspace-write --full-auto -C /path/to/repo
```

只做拆解（不改代码）：

```bash
rtk echo '$codex-parallel-collab
仅输出 CSV TODO 与任务包，不做文件修改。' \
| rtk codex exec --skip-git-repo-check --sandbox read-only -C /path/to/repo
```

## 产物

- 任务包：`.codex/<timestamp>-<slug>/`
- 任务清单：`issues/<timestamp>-<slug>.csv`
- 状态证据：`status/`、`notes/`、`evidence/`

CSV 最小字段：`id, task, owner, write_scope, read_scope, depends_on, verify, status, evidence`。

## 约束

- 默认单写者：主 agent 串行落盘，子 agent 以建议与证据回报为主
- 并行阶段必须使用 `spawn_agent` / `wait_agent` / `close_agent`
- 涉及 shared contract、schema、根配置时降级为串行处理
