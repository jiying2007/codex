# 生产运行与验收

## 日常目标操作
直接发送飞书项目需求/缺陷链接或 Wiki/Docx/Sheets，附“分析”“修复”“按方案开发”。只有引用时不付费。缺正文时补充描述/复现或授权文档。同一可信话题内“继续推进”“当前进度”“停止任务”。/help /status /cancel /repo /new 为最小快捷入口，内部 ID 仅诊断。不声称当前所有目标已实现。

## 主机
现有 目标 Ubuntu 主机、~/codex、feishu-codex-bot.service、Linger=yes。保留真实私有 policy/env 和 state/spool，不输出凭据；先核验 HEAD、dirty、pending、备份和恢复，再更新已验证 main，停止旧 Bot 与 MCP 写入，确保一消费者。保持 UMask=0077、NoNewPrivileges=yes、双层沙箱私有 procfs。非清洁工作树停止处理，不自动 reset/clean/stash。不得升级覆盖用户配置。

## 资格
管理员明确配置租户/用户/chat、repo/模块、mode/worktree、外部 API/gateway/self-hosted 计费和专用 private CODEX_HOME；不复制个人 auth.json，不扩大读写范围；未批准只提供无模型入口。现有现场仅 codex explain/review，未配置独立身份。工单 API 可选，Wiki 读取独立权限。实际项目库与映射由管理员确认。若用户无法提供权限，保留真实 blocked 状态，不绕过。

## 验收
G0：更新后 /help /status、错误命令、嵌套 probe（无模型）。
G1：真实 issue/story/wiki 引用、同话题补充上下文、重复与权限拒绝。
G2：独立身份隔离及 remote enqueue、真实批准只读 turn、连续、edit、cancel、restart；其他任务不允许消费共享额度。
G3/G4：私有备份及迁移恢复演练，真实 feature/bug、文档及跨仓验证，精确 Git/PR/CI 与独立人工验收，生成原工单反馈。无 API 不回写，不宣称关闭。回滚冻结消费者并核对新发生的任务/副作用，不能盲恢复旧 DB 丢失记录。

## 统一生产状态库（源码候选）
在单一服务与所有可信本机写入确实冻结、旧 queued/running/UNKNOWN 与待交付状态核对后，使用当前 migration_cli backup 与 rehearse 对真实 DB/spool/private policy/env 做一份新备份。使用 `unify --db <真实BotDB> --spool <真实spool> --private-policy <私有策略> --private-env <私有环境> --backup-dir <此次已验证备份> --lock-file <真实单实例锁> --consumer-paused`。策略需启用工程文本入口、关闭旧卡片；锁必须 owner-private。unify 获取真实单实例锁，核对 live 与 backup 的逻辑内容/配对，事务归档旧 fea_* 元数据、原消息去重和关联 Run，写入一次性迁移标记；不自动绑定旧原生线程，不删除旧 DB 或备份，不重启服务。新版看到 marker 后停止旧 /wi 与旧 WorkItem MCP 写路径，单一生产 DB；旧文件保留仅供离线恢复，后续备份不作为 live ledger。所有未确认外部效果须先人工核对，不可通过清空记录绕过。实际停服/恢复/迁移仍需真实主机回执。
