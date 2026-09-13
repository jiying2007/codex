# Codex Session Bootstrap

`session-bootstrap` 是 Codex Runtime Binding 内的薄装配层，不是第五控制面。它只解析任务等级、检查必要身份并生成 session envelope；不拥有 digital-worker Domain Gate / Verification PASS，不写 Knowledge，不修改目标工作树。

## 模式

- `L0 / quick-assist`：默认模式。允许 Knowledge Provider 不可用并显式标记 degraded；不要求 formal Work/Run。
- `L1 / governed-engineering`：需要 digital-worker 根目录和当前已审核 Knowledge Provider；用于普通正式研发任务。
- `L2 / formal-evidence`：需要 full 40-hex base commit、Engineering Task Package、digital-worker 根目录和 exact-pinned Knowledge Provider checkout；会按 digital-worker `cross-repo-lock.json` 核对 Knowledge checkout HEAD 与 canonical contract SHA-256。

解析优先级固定为：`explicit_mode > formal_signal > engineering_task_package > governed_signal > default_l0`。显式冲突 fail closed。

## 使用

### L0

```bash
rtk bash ~/codex/scripts/session-bootstrap.sh \
  --cwd "$PWD" \
  --task "解释这段 SPI NAND ECC 代码" \
  --summary-json
```

### L1

```bash
rtk bash ~/codex/scripts/session-bootstrap.sh \
  --cwd "$PWD" \
  --task "排查 UBIFS 并发写后只读" \
  --governed \
  --digital-worker-root ~/digital-worker \
  --knowledge-root ~/knowledge-hub \
  --summary-json
```

### L2

Formal 模式必须使用 digital-worker 已锁定的 Knowledge Hub exact checkout，而不是任意最新 checkout：

```bash
rtk bash ~/codex/scripts/session-bootstrap.sh \
  --cwd "$PWD" \
  --task "执行 Embedded Debug real Pilot" \
  --formal \
  --base-commit <FULL_40_HEX_SHA> \
  --engineering-task-package <engineering-task-package.json> \
  --digital-worker-root ~/digital-worker \
  --knowledge-root <EXACT_PINNED_KNOWLEDGE_HUB_ROOT> \
  --summary-json
```

## 身份边界

Bootstrap 输出只携带引用/身份：

- target repository root / HEAD / requested base commit；
- ADK immutable release identity 与 `exact-source-set` delivery mode；
- Codex Runtime Binding commit / target / Runtime Profile；
- Knowledge current-provider 或 exact-pinned-provider identity；
- Engineering Task Package ref。

输出禁止包含或推导：

```text
verification_pass
domain_gate_pass
release_ready
```

Runtime-local readiness 只说明 Codex Runtime Binding 可装配执行，不代表 digital-worker Verification 或产品 Release Ready。
