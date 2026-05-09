# Workflows 流程总览

本目录定义 feature / bugfix / refactor 三类协作流程，用于统一执行节奏和交付门禁。

## 流程选型

| 场景 | 优先流程 | 关注重点 |
| --- | --- | --- |
| 新增功能、行为扩展 | `feature-flow.md` | 先边界后实现，收口统一 |
| 故障修复、测试失败 | `bugfix-flow.md` | 先根因证据再最小修复 |
| 结构优化、复杂度治理 | `refactor-flow.md` | 行为不变边界与回滚方案 |

## 统一执行框架

1. `commander`：明确目标、范围、验收标准、风险阈值。
2. `architect`：拆边界、识别冲突面、给出依赖顺序。
3. `implementer`：按 ownership 改动并提交定向验证。
4. `reviewer`：输出 findings（按严重级别排序）。
5. `tester`：覆盖关键路径、边界与错误路径验证。
6. `integrator`：收口整合、最终验证、交付摘要与回滚建议。

## 并行协作约束

1. 同一文件同一时段只允许一个 owner 写入。
2. `package.json`、lockfile、根配置、schema/shared contract 默认串行处理。
3. 子任务跨边界修改时必须阻塞并上报，不允许静默越界。

## 交付门禁

1. 必须报告已执行的验证命令与结果。
2. 必须说明残余风险与影响范围。
3. 关键验证无法执行时，必须明确原因与降级结论。
