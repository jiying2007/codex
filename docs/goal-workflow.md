# Goal 合同与恢复

目标合同能力归属 ADK core 的 `adk-goal-authoring`，由受信的 exact ADK source 导入。Codex 仅声明技能路由和宿主适配，不维护重复的合同校验器。已有目标执行继续使用 `adk-planning-execution-loop`；单点修复无需生成合同。

技能只产出草案，不启动或重建原生 Goal，不清零累计，不设置预算或授予完成权限。预算提案、宿主预算和 Runtime Execution Policy 分开核实。

合同保留原验收 ID 分母及父子映射；批次选择 1–4 个相关交付，选中项的依赖必须关闭，具有文件范围、退出标准、定向/里程碑/最终验证与停止条件。重规划说明实际路径变化并在下一批核效果。结构通过不证明证据真实、验收语义完整或任务完成。

恢复从项目唯一当前状态开始。合同默认最多 64 KiB，恢复状态/输出最多 8 KiB，证据引用最多 8、历史入口和下一动作最多 3。历史按索引读取，不复制全量正文。

解析实际 ADK 源安装位置后，从任意项目 cwd 使用其绝对入口：

```bash
rtk bash <actual-adk-root>/scripts/devkit.sh goal plan-check --plan <goal.json> --state <current.json>
rtk bash <actual-adk-root>/scripts/devkit.sh goal resume --plan <goal.json> --state <current.json>
```

以上命令只读。缺少 ADK typed CLI 时先解析来源并记录缺项，不复制私人路径或另建执行策略面。

`scripts/codex-policy.sh` 通过绝对包入口固定 import root，同时保留调用项目 cwd；项目同名 `tools` 包不能遮蔽宿主实现。仍须使用当前真实线程的 intake。

## Goal / Loop 事件驱动、最小上下文

- 非平凡任务**已有 Goal 合同则不重新生成**；阶段内只读当前状态、准确 Git HEAD、待关闭验收、最近新增证据和最多3个下一步。旧 Issue/整场会话/完整日志按引用检索，不重新复制进每轮上下文。
- CI pending / heartbeat / 状态不变时，不经模型重复轮询；由事件通知或一次性确定性 GitHub 查询发现结论变化。新失败、原验收/用户指令变化、需要审查的 diff 才触发模型判断；批量查询工具状态、合并同 SHA 文件与重复日志。
- 开发/排障优先定向验证，同一纵向里程碑闭合后再跑受影响回归，最终验收保持原有完整门禁；不为每次微小更动重复最终 review/final。
- Host 如具有受信的 Goal/Phase、源 SHA、Event SHA 和原始证据索引，可在 **llm_agent 工作仓自身** 使用 Root 的 `tools.codex_assets.goal_loop_event_context preflight` 离线辅助；不得把该工具作为所有 Codex 项目的安装依赖，也不能从任意项目 cwd 猜 Root 路径。未接入真实 Host 时只报告候选判断，不声称模型已被自动拦截。
- 只有实际模型/工具执行完成、证据可回读后，才能推进事件 cursor；预检刚生成就写 cursor 可能漏执行。高风险重复/未知/证据溢出固定需复核，不把“无变化”当成已完成。
- 单次模型选择只给业务层级建议：确定性工具=无需模型、普通增量判断=适度推理、未知根因/安全/发布=高能力审查。模型、effort、缓存断点必须由 Host/Provider 兼容与质量回归决定；不使用未经验证的模型专属字段，不设置人民币每日上限。
- 真正的效果用同任务、同验收分母（至少10例）的 Token/已验证里程碑、完成率、重复输入、无进展调用及首次有效动作耗时衡量，不用更少 Token 代替通过验收。

源码测试不等于模型行为 eval 或实际 token 收益。后续按每关闭子项的 tokens、恢复至首个有效动作耗时、重复无变化验证和整体 final 调用次数衡量。安装技能不会自动解除旧 Goal 的 `usage_limited`。
