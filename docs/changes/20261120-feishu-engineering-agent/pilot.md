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
