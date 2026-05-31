# adk-plan-lite

轻量只读计划生成 skill。用于用户明确要求先给计划、暂不执行代码修改的编码任务。

## Scope
- 输出范围、行动项、验证项、风险和未决问题。
- 默认只读，不创建、不修改、不删除文件。
- 若任务需要执行、并行拆解或长任务检查点，转交更重的 ADK 流程。

## Provenance
- Owner: `agent-dev-kit`
- Source: ADK 原生实现，吸收 `ComposioHQ/awesome-codex-skills:create-plan` 的只读计划方法，不复制第三方运行时语义。
