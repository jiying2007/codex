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

源码测试不等于模型行为 eval 或实际 token 收益。后续按每关闭子项的 tokens、恢复至首个有效动作耗时、重复无变化验证和整体 final 调用次数衡量。安装技能不会自动解除旧 Goal 的 `usage_limited`。
