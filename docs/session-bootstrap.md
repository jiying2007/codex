# Codex Session Bootstrap

`session-bootstrap` 是 Codex Runtime Binding 内的薄装配层，不是第五控制面。它只解析任务等级、检查必要身份并生成 session envelope；不拥有 digital-worker Domain Gate / Verification PASS，不写 Knowledge，不修改目标工作树。

## 模式

- `L0 / quick-assist`：默认模式。允许 Knowledge Provider 不可用并显式标记 degraded；不要求 formal Work/Run。
- `L1 / governed-engineering`：需要 digital-worker 根目录和当前已审核 Knowledge Provider；用于普通正式研发任务。
- `L2 / formal-evidence`：需要 full 40-hex base commit、携带 `package_id/work_item_id/run_id/repo_root/base_commit` 的 Engineering Task Package、exact Digital Worker governance identity 和 exact-pinned Knowledge Provider checkout。Formal ETP 的 `base_commit` 必须与请求的 `--base-commit` 完全一致，否则 fail closed。

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

Formal 模式必须使用 Digital Worker 授权的 Engineering Task Package 与锁定的 provider checkout，而不是临时输入任意 Work/Run 标识：

```bash
rtk bash ~/codex/scripts/session-bootstrap.sh \
  --cwd "$PWD" \
  --task "执行 Embedded Debug real Pilot" \
  --formal \
  --base-commit <FULL_40_HEX_SHA> \
  --engineering-task-package <engineering-task-package.json> \
  --digital-worker-root ~/digital-worker \
  --digital-worker-domain-ref <DOMAIN_REF> \
  --digital-worker-routing-ref <ROUTING_REF> \
  --knowledge-root <EXACT_PINNED_KNOWLEDGE_HUB_ROOT> \
  --summary-json
```

L2 会从 ETP 读取并冻结：

```text
package_id
work_item_id
run_id
repo_root
base_commit
Engineering Task Package SHA256
```

这些字段进入 `execution_source_set.materials.engineering`，因此 Work/Run 或 ETP 内容发生变化都会产生新的 Execution Source Set identity。`work_identity` 只是同一冻结事实的便捷投影，不是第二个 Source of Truth。

## Runtime Execution Receipt v2 handoff

当前 Runtime Binding 的执行证据使用 `schemas/runtime-execution-receipt.v2.schema.json`。Receipt v2 已要求：

```text
work_item_id
run_id
execution_source_set_identity
digital_worker_governance_identity
```

这些身份必须复用本次 L2 bootstrap 已冻结的值：

```text
receipt.work_item_id                     <- bootstrap.work_identity.work_item_id
receipt.run_id                           <- bootstrap.work_identity.run_id
receipt.execution_source_set_identity    <- bootstrap.execution_source_set.identity
receipt.digital_worker_governance_identity <- bootstrap.digital_worker.governance_identity.identity_digest
```

Runtime 不得自行生成另一组 Work/Run 身份，也不得把 receipt local gate 解释成 Domain Verification PASS。

## L1 → L2

从 Governed Engineering 升级到 Formal Evidence 时，使用 `--escalate-from-l1 --prior-session-bootstrap <L1_JSON>`。旧 L1 context 仅保留为 provisional historical context；L2 必须重新冻结 Execution Source Set 和 Session Bootstrap identity，不允许自动提升旧上下文为正式证据。

## 身份边界

Bootstrap 输出只携带引用/身份：

- authoritative `work_item_id / run_id / engineering_package_id`；
- target repository root / HEAD / requested base commit；
- exact Digital Worker governance identity；
- ADK immutable release identity 与 `exact-source-set` delivery mode；
- Codex Runtime Binding commit / target / Runtime Profile；
- Knowledge current-provider 或 exact-pinned-provider identity；
- Engineering Task Package ref + content SHA256；
- frozen Execution Source Set identity；
- Session Bootstrap identity。

输出禁止包含或推导：

```text
verification_pass
domain_gate_pass
release_ready
```

Runtime-local readiness 只说明 Codex Runtime Binding 可装配执行，不代表 Digital Worker Verification、Product Qualification 或产品 Release Ready。
