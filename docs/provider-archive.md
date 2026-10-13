# Provider 自动候选归档

非平凡任务启动时，Agent 自动按 [Execution Policy 自动 intake](execution-policy.md) 执行 `execution-policy ensure`，绑定真实请求临时文件、准确当前线程、实际任务模式与验收项，回读后实施；无需重复请求授权。归档操作在产生有证据的耐久结论后执行，不代替 intake 或项目验收。

日常低风险、脱敏、可复用结论已获得本地 candidate-only 登记授权，Agent 自动执行，无需逐条人工确认：

```bash
rtk bash ~/codex/scripts/knowledge-provider.sh archive \
  --subject project:knowledge-hub --source /tmp/reusable-conclusion.md \
  --kind validation --sanitized --apply
```

先通过 Provider context 的 `--execution-project` 或 `--workspace` 核定执行主体，跨项目查询用 `--retrieval-project`。归档始终显式传 `--subject`。正文只能是结论、证据、风险和下一步，不保存原始会话、日志、秘密或设备标识。`--sanitized` 是内容边界声明，服务端仍执行安全扫描。

不传 `--apply` 或传 `--dry-run` 时只规划，返回 operation 和预测内容 hash；受治理执行器用 `--expected-content-sha256` 冻结计划。Provider 按 candidate-only 策略核对类型、主体与 registered owner；正文、registry、追加操作账本及派生索引在同一事务写入。当前回执为 `knowledge-provider.operation-receipt/v4`，公开 `reconcile` 使用调用方批准的内容 hash 验证持久化。

- `PLANNED`：未持久化，不可声明归档成功。
- `ARCHIVED` 且 `persisted=true`：已写入 reviewing 候选，回执绑定 item、operation、source/content hash。
- `ALREADY_ARCHIVED` 且 `persisted=true`：相同输入已存在并通过回读，重复执行不写入。
- `BLOCKED`、退出码 2：提交前阻断；`UNKNOWN` 表示调用后持久化状态未确定，禁止盲目重试。`CONFLICT` 表示正文或治理账本漂移，需要审查。对账没有批准的 hash 时只返回 `PRESENT_UNVERIFIED`。

允许 validation、debug-record、runbook、audit、codex-session、project-archive 和 external-source-note；decision、standard、专利和授权记录继续人工审查。候选保持 reviewing、AI 标记和待复核状态，不自动 active，不产生人工或 owner 签名。

原 proposal-route 策略仍为 disabled/shadow/report-only。新 archive 操作有独立 candidate-only 权限，不靠打开 shadow 开关获取写入能力。活动采集不替代知识归档回执。关闭 Hub policy 的 `enabled` 可暂停自动归档；已写入事务提供 before 备份与恢复日志，不能回退无关用户改动。

`knowledge-provider.sh status` 返回逐操作 capability。入口存在不授予写权限，失败使用脱敏 `reason_codes`。Native 在调用前后核验发布锁绑定的完整执行文件清单；漂移在提交前返回 `BLOCKED`，写调用后无法确定则返回 `UNKNOWN`。Hub 使用独立 `local/provider-principal.json`，不依赖日报开关，不从 Git、目录或聊天身份推断主体。

没有 Git、没有 commit 或没有 remote 的目录可使用显式主体、逻辑 workspace 或经授权的本地绑定。源文件观测由 `capture-source` 的显式 allowlist 完成；observed hash 不认证历史验证。跨项目归档和主体转移必须有精确 grant；assign 必须给出 `--from-subject` 和批准的非空内容 hash。历史操作不可改写，metadata 工作流在同一事务追加新的验证记录。当前运行时不保留旧版本分发、旧归档接口或迁移工具。

自动化是 Agent 任务执行约定，未安装后台定时任务。个人主体不从 owner、Git、路径或聊天身份推断。
