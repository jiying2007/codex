# Provider 自动候选归档

非平凡任务启动时，Agent 自动按 [Execution Policy 自动 intake](execution-policy.md) 执行 `execution-policy ensure`，绑定真实请求临时文件、准确当前线程、实际任务模式与验收项，回读后实施；无需重复请求授权。归档操作在产生有证据的耐久结论后执行，不代替 intake 或项目验收。

日常低风险、脱敏、可复用结论已获得本地 candidate-only 登记授权，Agent 自动执行，无需逐条人工确认：

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh archive \
  --project knowledge-hub --source /tmp/reusable-conclusion.md \
  --kind validation --sanitized --apply
```

先通过 Provider context 显式项目获得 selected route。正文只能是结论、证据、风险和下一步，不保存原始会话、日志、秘密或设备标识。`--sanitized` 是调用者对内容边界的声明，仍运行服务端秘密、路径和地址扫描；扫描不是对所有敏感信息的完备识别。

不传 `--apply` 或传 `--dry-run` 时只规划。Provider 按本机 Hub 的 `registry/provider-archive-policy.json` 配置核对类型和 registered owner，按 registry 项目路由选择目标。事务同步正文、registry、lifecycle 与派生索引；回读成功后输出 `knowledge-provider.archive-receipt/v1`。

- `PLANNED`：未持久化，不可声明归档成功。
- `ARCHIVED` 且 `persisted=true`：已写入 reviewing 候选，回执绑定 item、operation、source/content hash。
- `ALREADY_ARCHIVED` 且 `persisted=true`：相同输入已存在并通过回读，重复执行不写入。
- `BLOCKED`、退出码 2：校验或持久化失败，不回退内部写入入口。若写入后回读失败，先对账再重试。

允许 validation、debug-record、runbook、audit、codex-session、project-archive 和 external-source-note；decision、standard、专利和授权记录继续人工审查。候选保持 reviewing、AI 标记和待复核状态，不自动 active，不产生人工或 owner 签名。

原 proposal-route 策略仍为 disabled/shadow/report-only。新 archive 操作有独立 candidate-only 权限，不靠打开 shadow 开关获取写入能力。活动采集不替代知识归档回执。关闭 Hub policy 的 `enabled` 可暂停自动归档；已写入事务提供 before 备份与恢复日志，不能回退无关用户改动。

自动化是 Agent 任务执行约定，未安装后台定时任务。个人主体不从 owner、Git、路径或聊天身份推断。
