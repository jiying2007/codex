# Codex Session Bootstrap

`session-bootstrap` 是 Codex Runtime Binding 内的薄装配层，不是第五控制面。它只解析任务等级、检查必要身份并生成 session envelope；不拥有项目验收、digital-worker Domain Gate / Verification PASS，不写 Knowledge，不修改目标工作树。

## 小团队默认路径

日常开发直接使用 Codex CLI + 已安装的 ADK 资源。Digital Worker 不是 L0/L1 的安装前提，也不是普通项目验收的必经系统。任务、源码、构建/测试、审查与接受结论继续由项目的 Issue/PR、Git/CI、设备证据和责任人承接。`ready` 仅表示会话可装配，不表示上述检查已执行。

资源维护与日常研发分开：`llm_agent -> ADK -> Codex 资源发行 -> CLI` 是维护/分发链；Knowledge Hub 提供可追溯知识。没有 Digital Worker 时，不建立另一套 Work/Run 台账，不伪造 formal receipt，不将它的代码整包并入 ADK。详见 `docs/small-team-delivery.md`。

## 模式

- `L0 / quick-assist`：默认模式。允许 Knowledge Provider 不可用并显式标记 degraded；不要求 formal Work/Run 或 Digital Worker。
- `L1 / governed-engineering`：普通研发模式，需要当前 Knowledge Provider；不读取 Digital Worker checkout 或集成配置。项目验收与执行门禁不会因解耦而取消。
- `L2 / formal-evidence`：显式选择现有 Digital Worker 正式证据集成时使用。需要 full 40-hex base commit、携带 `package_id/work_item_id/run_id/repo_root/base_commit` 的 Engineering Task Package、exact Digital Worker governance identity 和 exact-pinned Knowledge Provider checkout。Formal ETP 的 `base_commit` 必须与请求的 `--base-commit` 完全一致，否则 fail closed。

L2 是一项可选集成，不是“所有发布任务必须使用的全局等级”。未选择该集成的项目仍必须执行自己的发布/设备验证与审批流程。L2 被显式选择后，缺少材料不得自动降成 L1 或 L0。

解析优先级固定为：`explicit_mode > formal_signal > engineering_task_package > governed_signal > default_l0`。显式冲突 fail closed。

Contract 1.3 中，L0/L1 的 runtime identity 从现有 ADK provider lock 派生，不读取 `manifests/integrations/digital-worker-runtime-binding.json`；只在 L2 校验该集成。L0/L1 输出 `digital_worker.required=false`、`root=null`、`governance_identity=null`，不宣称 Digital Worker 拥有本次任务的验证结论。ADK lock、Knowledge Adapter 与 Bootstrap contract 仍是必需资产。

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
  --knowledge-root ~/knowledge-hub \
  --summary-json
```

L1 的 Knowledge Provider 不可用仍返回 blocked；它不会把缓存或路径猜测当作知识事实。Bootstrap 只做装配预检，实际 context/query/action-check 仍通过 Knowledge Adapter 执行。目录存在不等于 Provider 已通过真实运行验证。

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

现有 Digital Worker 集成的执行证据继续使用 `schemas/runtime-execution-receipt.v2.schema.json`，本次解耦不改写其身份或历史含义。Receipt v2 要求：

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

## 身份与资格边界

L0/L1 装配项目位置、Codex runtime 与 ADK 资源引用，以及当前 Knowledge Provider 入口；不生成正式 Work/Run、Execution Source Set 或产品资格。

L2 额外装配 authoritative Work/Run、exact Digital Worker governance identity、exact-pinned Knowledge、ETP content digest、frozen Execution Source Set 和 escalation provenance。输出禁止包含或推导：

```text
verification_pass
domain_gate_pass
release_ready
```

Runtime-local readiness 只说明 Codex Runtime Binding 可装配执行，不代表项目测试通过、Digital Worker Verification、Product Qualification 或产品 Release Ready。
