# ADK 7.12.4 到 Codex 的受控导入

- 目标：把已签名的 ADK `v7.12.4` exact main `35b5fb31810c654a295c25b89e04435d6a32f57c` 作为 Codex 声明式资产来源，完成来源、内容、构建、计划和安装证据的分层闭环。
- 用户现有 `~/codex` main 的 9 个 dirty 文件属于现场基线。本隔离候选已逐字节纳入这些改动，原主仓与 `~/.codex` 保持原状，后续提交和发布单独按门禁处理。
- ADK Skill 当前有 42 个启用项。来源审计对当前 exact ADK 报告 37 项内容未变、5 项 Skill 内容变更及 1 个新增参考文件；只按 exact 上游复制，保留 Codex 本地 profile、target 和包装元数据。
- Agent 正文与旧来源比较未变；Execution Policy 的 `contracts.py` 和 `decision.py` 已变化，必须按完整来源及 consumer 合同验证。
- 验收：provider lock、每项来源 blob/完整目录、Agent 与 Execution Policy 身份一致；Python 3.8/3.11/3.12 合同和现有回归通过；build、doctor、plan、dry-run、apply、check 绑定同一 source/build/target。真实模型行为与 Software M5 资格独立验收。
- 禁止：修改 ADK 上游镜像以适配 Codex、重标历史来源、覆盖未知 live 资产、清理用户 dirty、把 PR/source 验证说成产品放行。
