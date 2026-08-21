---
name: adk-task-breakdown
description: 将需求拆解为可并行执行的任务包
version: 1.4.0
last_updated: 2026-07-19
triggers:
  - "拆解任务"
  - "任务拆分"
  - "任务太大"
non_triggers:
  - 单点微调任务
  - 单文件小修且无共享依赖变更
inputs:
  - 需求范围、里程碑、模块边界与依赖关系
outputs:
  - 任务清单、依赖图、优先级、ownership 与冲突矩阵
constraints:
  - 每个任务必须可独立验证
  - 默认禁止两个任务并行修改同一 shared contract/schema
  - 机器消费的任务包必须声明 structured_output_schema 和 strict_schema_decision
  - 任务包只接受 adk-task-package-schema-v2，work_item_kind 与 implementation_permission 必须满足跨字段规则
---

# adk-task-breakdown

## Goal
- 把复杂需求拆成边界清晰、可独立验收的任务包。

## Prerequisites
- 已有需求包和至少一个可执行验收标准。
- 明确共享文件、共享 contract 和根配置触点。

## 任务拆分原则

1. **单一职责**：每个任务只解决一个问题，并标为 decision/research/prototype/implementation。
2. **可独立验证**：每个任务有独立的验收命令，不依赖其他任务的产出。
3. **粒度适中**：单任务 2-8 小时，超 8 小时必须再拆，低于 0.5 小时合并。
4. **依赖最小化**：任务间依赖越少越好，优先串行再考虑并行。
5. **共享写独占**：同一文件/contract 的写操作只能在一个任务中。
6. **全局约束下沉**：版本下限、依赖禁用、命名、协议字段、文案口径、精确数值等跨任务规则必须进入 `global_constraints`，不能只留在总计划正文。
7. **接口显式化**：每个任务必须声明 `interfaces`，说明它消费什么、产出什么、与相邻任务的契约是什么。

## 估时方法

| 方法 | 适用场景 | 操作方式 |
|------|---------|---------|
| 类比估时 | 有类似历史任务 | 参考历史任务实际耗时 |
| 三点估时 | 不确定性高 | (乐观 + 4×最可能 + 悲观) / 6 |
| T-shirt | 快速粗估 | S(0.5h)/M(2h)/L(4h)/XL(8h) |
| 专家判断 | 领域专精 | 由 owner 直接给出 |

## Workflow
1. **计划预检**：先检查需求/计划是否存在内部矛盾、不可验证条目、会被 reviewer 判为缺陷的要求，以及缺失的全局约束。
2. **定义拆分边界**：明确 scope_write/read、work_item_kind、question_to_resolve、evidence_required、implementation_permission、exit_gate、handoff_target、retention_decision、interfaces 与完成标准。
3. **并行准入判断**：检查是否存在同文件写冲突、共享 contract、根配置冲突。
4. **绘制依赖图**：
   ```bash
   # 列出文件依赖关系
   rg -n "import|require|include|#include" <target_path> | head -30
   # 查看模块间调用
   rg -n "call|invoke|dispatch|emit|publish" <target_path> | head -20
   ```
   依赖图格式：`T1 → T2 → T3`（箭头表示"被依赖"）
5. **生成任务包**：decision/research/prototype 固定 `implementation_permission=forbidden`；只有已批准 implementation 可为 `approved`，并给出 owner、依赖、验证、阻塞和 handoff。
6. **右尺寸校准**：任务必须足够小以支持独立测试和 review；setup/config/docs 应并入真正消费它们的任务，避免独立“准备任务”丢失验收上下文。
7. **估时与排期**：用三点估时法计算每个任务工时，标注关键路径。
8. **定义交接令牌**：每个任务声明 `ready_to_handoff` 条件与接收方。
9. **结构化输出门禁**：机器消费或并行调度的任务包必须映射到 `adk-task-package-schema-v2`，拒绝 v1、自由 JSON、隐式字段、未声明 enum 和 kind/permission 冲突。
10. **规划整合顺序**：列出 merge order、联调点与最终统一验证步骤。
11. **大仓触点梳理**：若涉及大型多模块仓，补关键触点清单。
12. **输出执行建议**：适合并行则给 2-4 个任务包，不适合则给单线程方案。

## Commands
```bash
# 扫描共享依赖和 contract
rg -n "contract|schema|shared|entry|router|package.json" <repo_root>

# 查看变更范围
git diff --name-only <base>...HEAD

# 查看模块间依赖
rg -n "import|require|include" <target_path> | head -20

# 统计文件复杂度（辅助估时）
wc -l <target_files>
cloc <target_path> 2>/dev/null || echo "cloc not installed"
```

## Evidence Template
```md
- Parallel Suitability: yes/no + 理由
- Plan Preflight: conflicts / unverifiable requirements / reviewer-defect risks
- Global Constraints: version floors / dependency limits / naming / protocol fields / exact values
- 任务包列表:
  | ID | 描述 | Owner | 依赖 | Interfaces | 估时 | 验证命令 |
  |----|------|-------|------|------------|------|---------|
  | T1 | ... | ... | 无 | consumes/produces | 2h | ... |
  | T2 | ... | ... | T1 | consumes/produces | 4h | ... |
- 关键路径: T1 → T2 → T4（总工期 Xh）
- 估时方法: 三点估时 / 类比 / T-shirt
- Work Mode (diagnosis/repro/planning/execution):
- Structured Output Schema: adk-task-package-schema-v2 / strict_schema_decision / refusal_handling
- Work Item Contract: work_item_kind / question_to_resolve / evidence_required / implementation_permission / exit_gate / handoff_target / retention_decision
- Handoff Token (ready_to_handoff + receiver):
- Large-Repo Touchpoints (scripts/entry/command-registry/shared-contract):
- Conflict Matrix:
- Merge Order:
- Final Integration Verification:
```

## Failure Handling
- 若拆分后冲突面扩大，降级为单线程执行方案。
- 若出现未识别共享依赖，暂停并重新划分 scope。
- 非 implementation 工作项请求写产品代码时，固定 blocked/replan，不得静默改类型。
- 估时偏差超过 50% 时，重新评估并更新任务包。
- 依赖图出现环时，必须打破循环依赖再继续。

## Quality Gate
- 每个任务必须具备独立验证命令与可交付产物。
- 机器消费的任务包必须有 structured_output_schema、strict_schema_decision 和 refusal_handling。
- 四种 work_item_kind 必须满足 v2 permission/exit gate 规则；prototype 必须引用 prototype_evidence。
- 每个任务必须继承适用的 global_constraints，并声明 interfaces。
- 计划预检发现的内部矛盾、不可验证要求或 reviewer-defect 风险必须先处理或记录 owner 决策。
- 必须显式标记共享文件/共享 contract 冲突面。
- 每个任务必须声明 handoff 条件，避免"完成定义"不一致。
- 必须给出"适合并行/不适合并行"的明确结论与理由。
- 必须给出当前推进模式与收敛条件，避免持续空转分析。
- 任务粒度必须在 0.5h-8h 范围内。
- 依赖图必须无环。

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "拆太细浪费时间" | 粗粒度任务导致并行冲突和集成地狱 | 按 SKILL.md 流程拆到可独立验证的粒度 |
| "我一个人做不需要拆任务" | 单人也会遗忘依赖和边界，任务拆解是思维工具 | 即使单人也按流程输出任务包和 handoff 条件 |
| "反正做着做着会调整" | 无计划的调整是失控的委婉说法 | 先完成任务拆解再执行，调整需记录变更原因 |
