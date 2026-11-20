# Long Task Recovery Template

## Task State

- Task:
- Current stage:
- Last completed checkpoint:
- Current blocker:
- Changed scope:
- logical_task_open: true | false
- milestone_close: true | false
- session_handoff_required: true | false
- Retry budget:
- Staleness threshold:
- Heartbeat:

## Review Convergence

- Review round:
- Review mode:
- Finding classes:
- New finding class count:
- Consecutive clean reviews:
- Contract change decision:
- Replan reason:

## Checkpoints

| Stage | Status | Done Criteria | Verification | Evidence |
|---|---|---|---|---|
| S1 | pending |  |  |  |

## Goal Closure

- Goal statement:
- Completion claim:
- Claimant:
- Verifier:
- Required evidence:
- Open items:
- Stop condition: pass | replan | split | blocked | abort
- Decision: pass | needs-fix | blocked

## Validation Resource Matrix

| Validation | Output directory | Binary/cache/device | Parallel decision |
|---|---|---|---|
|  |  |  |  |

## Recovery Prompt

```md
Goal:
Completed:
Current state:
Do not repeat:
Next action:
Required verification:
Retry budget:
Staleness threshold:
Open items:
```

## On-demand execution branches

以下仅在对应条件触发时加载，不是每轮默认检查清单；适用原宿主/项目更严格合同仍优先。

- **受控生命周期或外部写入**：涉及 OTA、生产设备、权限、迁移或发布，冻结 owner × state × event × resource × termination × invariant；核对原审批、回滚锚点和写入结果。网络/工具回执未知时先对账，不盲目重放。
- **Task Package v2**：仅真实派工时使用 canonical JSON；scope_read/scope_write/must_not_touch、接口/全局约束进 `constraints`，owner/report/noise 进 `context` 或外层人类信封，不增顶层字段。保留 kind/question/evidence/permission/exit/handoff/retention；decision/research/prototype 不可获得 implementation 权限，缺依赖/原文审查先退回规划。
- **Evidence / attestation**：从原验收 criterion ID/注册 evidence digest 追溯验证；测试计数、流水号、heartbeat 不证明收敛。attestation 写后回读，未通过不得完成/归档。
- **风险与恢复**：设计/共享契约/重大 finding 变化时 replan；同失败两次无根因则更新假设。按范围、原验收分母、权限、依赖或验证路径的实质变化启动适用审查，不按固定偏差百分比。三次 blocker 仅作诊断，不自动升级组织层级。
- **最小充分验证／避免重复全量流程**：已批准的低风险阶段按 `change_snapshot / affected_interfaces / prior_verified_snapshot / evidence_freshness` 选最小受影响验证。同快照且结果有效可复用原回执，注明 `verification_reused / reason`，不重调模型/整个 Goal。输入、依赖、设备状态、权限或发布边界变化使旧证据失效；checkpoint 不替代最终的完整回归、独立 Review 和真实现场门禁。未运行且不可复用记 `not-tested`，失败为 needs-fix。
- **并行验证**：执行前核共享构建目录、缓存、端口、二进制或设备资源；相互冲突串行。阶段末收敛 orphan checkpoint，只保留通过/失败的可重放证据和真实恢复入口。
- **Goal Closure**：追溯原 goal_statement/completion_claim/claimant/独立 verifier/required_evidence/open_items/stop_condition (pass/replan/split/blocked/abort)。分报当前预算、历史预算合规、证据验真；milestone 不调用整体 final、不关闭父 Goal。
- **Runtime 限制**：仅宿主真实 stop 触发停止实施并依既有权限重规划，不设人民币日费用硬限制。Skill 不能读宿主私有 Goal、控制 scheduler 或自签审批；外部原证缺失为 UNKNOWN，压缩摘要不放行。

## Recovery handoff discipline

恢复只读最近可信 checkpoint、当前验收/阻塞、已核 source SHA 和最多三个 READY 动作；相同事件的成功动作不重放。仅用户指令、HEAD、失败、新证据或审核变化才更新派工。原始日志保留 raw_ref，高风险/语义冲突时回读。

## Interrupted effects and observable progress

中断点涉及发布、迁移、评论或设备写入时，用原 operation ID、目标身份和原验收对账：可信回执已证明完成则只补索引/checkpoint；已证明未开始且原授权仍有效，才可重试；结果仍未知则阻塞该依赖，继续其他已批准且无冲突的 READY 工作。进程退出、缺少本地文件或旧 checkpoint 的 `unknown` 不等于外部操作未发生，不得换一个 ID 重新发送。

继续时报告变化的验收项/产物身份/诊断证据；改计划、时间戳或重复查询不算进展。同输入/动作/失败两次且无新信息即停重放，证伪新假设或报具体 blocker。保留已完成子项产物/回执；阶段只关闭自身验收，父 Goal 未完成分母保留。
