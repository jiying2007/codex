# Feishu Engineering Agent — SDD 代码落地清单
Date: 2026-11-20. Scope: personal/small team, one existing Feishu Bot consumer.

**状态语义：** [x] = 源码和离线测试已编写，尚需用最终精确 SHA 的 CI 核验；[ ] = 本轮不执行的真实主机/企业权限/设备/业务验收。源码完成绝不等价生产验收。

## TASK-000 — 头脑风暴与规格
[x] 取舍：薄业务核心 + 现有 Codex/ADK/Git/CI，不建设第二套 Runtime、PM、通用 Agent 图。
[x] WorkItem 与 AgentRun 分离；飞书项目/TAPD 是原业务权威，不自动关闭。
[x] 源码测试准入、远端 UNKNOWN 不重放、卡片及时 ACK 与单消费者的安全边界。

## TASK-001 — 确定性输入与来源身份
[x] `routing.py`：中文命令、项目偏好、repo 白名单、写操作提案。
[x] `models.py`/`store.py`：来源五元组、事务幂等、原输入不进 DB。
[x] `manual_items.py`：无需企业 API 的 `/wi add|list|status|handoff`，仅记录来源与摘要哈希。
[x] 本地 stdin CLI；`/wi attempt <sourceRun> <read|review|edit>` 创建独立待授权 Run。
[ ] 实际用户/项目聊天身份与权限验证。

## TASK-002 — 飞书卡片/文本交互
[x] `cards.py`：Card JSON 2.0 签名、事件两种字段布局、有效期、去重、消息/操作者/租户绑定。
[x] `actions.py`：卡片待处理请求归档、执行申请仅等待审批、启动前取消；运行中必须走精确 turn interrupt。
[x] `channel.py`：同一既有 Lark transport 的发送入口；先持久化再远程发送，UNKNOWN 不盲重试。
[x] 旧 Bot `engineering_cards_enabled=false`，无企业卡片权限时文本 `/wi` 正常使用；私有验证 Token/HMAC key 按需启用卡片。
[ ] 真实 SDK 1.7.1 回调、桌面/手机、3 秒应答、卡片更新有效期测试。

## TASK-003 — Codex 原生会话与有界执行
[x] `sessions.py`：actor/tenant/chat/repo/host/CODEX_HOME/thread 精确绑定、resume/interrupt/turn 请求。
[x] `appserver.py`：显式 host-qualified stdio initialize/initialized/thread resume/turn RPC；审批请求拒绝自动同意；不泄露 Feishu 凭据。
[x] `workflow.py`：一 WorkItem 多 Run；精确范围、SDD 和外部费用授权 HMAC 后才可 queued。
[x] `runtime_bridge.py`：turn/start 前存 effect receipt；ACK≠完成；turn/completed 关联验证；失败、重启/中断 UNKNOWN。
[x] `feishu_agent_mcp.py`：本机 stdio MCP 将精确 WorkItem AgentRun/scope hash 接入既有 Bot SQLite/spool/worker；一对一任务回执、幂等和 UNKNOWN 不重放。
[x] Agent 执行使用专用 0700 `CODEX_HOME` + 私有 API key / gateway base URL；拒绝个人 `auth.json`、共享计费标识，并在执行前复核仓库/工作区/验证策略指纹。
[x] 既有 Bot worker 同步 AgentRun 与 task 状态；仅凭持久终态和 commit evidence 修复窄恢复窗口，不把 CI/QA 当作已完成。
[x] 模型调用默认禁用；MCP 入口不直接启动模型，WorkItem 执行仅由明确启用的独立非共享计费身份交给既有 worker。
[ ] `vstrong100` 实测独立 API 凭据、专用 CODEX_HOME、MCP/Bot 同 UID、Codex CLI 实际 provider、资源/费用与故障恢复。
[x] 既有 worker 对关联 WorkItem 使用持久 `codex exec --json`；精确 thread/终态回执绑定到 AgentRun、host、实际工作目录和专用 CODEX_HOME，通过本机 MCP 查询。
[x] 飞书 `/wi cancel <attemptRunID>` 使用现有 Bot 精确取消排队任务，或仅请求终止其本机 CLI 进程；不以发送信号冒充已完成中断。
[x] `/wi continue <上一轮RunID> | 新范围` 创建独立待授权的后续回合；沿唯一前序绑定复用本机 Codex thread 和原 worktree，保留历史 commit；精确范围与当前策略重新授权。已有 PR/CI 证据的 edit 不允许复用原分支，已保留后续回合的旧 Run 不再发布或接收 PR/CI 证据。
[ ] 真实主机验证连续 `codex exec resume`、Git 工作树、会话持久化和进程终止；App Server turn/interrupt 尚未接线。

## TASK-004 — 真实来源读取可选增强
[x] `workitems.py`：TAPD Story/Bug + 飞书项目 Meegle 只读适配器，验证来源/空间/类型/版本。
[x] `source_bridge.py`：权限不足返回用户提供未核验；权限具备才使用注入式 reader，保存版本哈希而非正文。
[x] 无企业 API 时不阻断人工登记和研发交接。
[ ] 一条真实飞书项目需求和一条 TAPD 缺陷的实际权限/数据核验。
[ ] 真实企业 webhook 的官方身份与事件订阅联调（无权限则不启用）。

## TASK-005 — 需求/Bug 交付与跨仓联调
[x] `delivery.py`：一次性 PR 发布收据、可信只读 Git PR/CI 校验、独立签名 QA、AgentRun 完成≠原工单关闭。
[x] `feedback.py`：无 API 时人工可复制回写；具备授权时仅一次性追加评论、不改工作项状态。
[x] `contracts.py`：SoC/MCU 等跨仓版本化接口，逐仓 CI/协议哈希证据；不将 CI 冒充设备 HIL。
[x] `test_feishu_engineering_end_to_end.py`：低风险 Feature + Bug 的 mock Codex/Git/QA 纵向合同验证。
[ ] 一条真实 Feature、一个真实 Bug 的改代码/PR/CI/产品或 QA 验收。
[ ] 如涉及设备：实际板卡、固件、联调/HIL；不由假数据替代。

## TASK-006 — 主机迁移/故障回滚
[x] `migration.py`：原 Bot SQLite WAL 一致性备份、spool/私有策略文件校验、SHA-256 清单、隔离恢复演练。
[x] `migration_cli.py`：只读 inspect、显式 paused-consumer backup、独立 rehearse；不自动修改线上服务。
[x] cutover_gate 必须有旧消费者停止、独占锁、回调/运行时资格、备份恢复证据；默认不能通过。
[x] 不新建定时巡检、第二消费者或未经确认的常驻服务。
[ ] `vstrong100` 原 Bot 系统服务/真实回滚操作、验收、单消费者切换与故障演练。

## 项目资源边界
- 不使用 Codex/Work 共享模型额度，不创建新定时任务。
- CI 单元测试为离线假传输；真实企业 API、Git 写、设备操作在本轮保持关闭。
- 下一阶段集中进行 TASK-002/003/004/005/006 的现场验证；基线的 TASK-001 必须与最新 HEAD 同步校验。

## 完整 GitHub PR/CI 适配（源码）
[x] `github_adapter.py`：固定 `api.github.com` 和仓库白名单的只读 PR/Actions 观察；经独立签名授权后为已存在的精确远端分支创建草稿 PR，不负责 Git push、merge 或 GitHub Issue。
[x] PR 发布与原工作项评论分别验证私有签名授权；无签名/失效凭据/写权限默认关闭。
[ ] 现场 GitHub/GitLab/Git Forge 具体权限及真实 PR/CI 读取和发布必须集中实证。

## 最后一次源码深审发现并补齐的契约
[x] PR/CI/独立 QA 必须匹配同一 canonical 精确提交，不能串接不同固件/代码版本作为交付证据。
[x] read/review 正常结束不强制构建 PR；edit 仍保留 PR/CI/QA 独立门禁。
[x] NativeTurnCoordinator 实际执行前再次核实 WorkItem 已持久化签名审批，非仅依赖内存 grant。
[x] turn/completed 可能先于 turn/start ACK，原生事件缓冲并在有界溢出时 fail closed。
[x] WorkItem 关联重放不能改绑来源，企业 API 可用时也重新检查当前仓库访问权限。
[ ] 以上源码补丁仍需本次新 HEAD 全量 CI 才可标记为已验证；生产主机与真实模型/设备现场试验统一后移。

[x] 模型执行授权收据保存签名时精确到期时间；真实分发不能通过手工扩大 RuntimeGrant 有效期，CI 负向测试无模型副作用。

[x] WorkItem 文本状态列出最近五个同权限研发尝试，精确 Run 查询可见已记录 thread ID；重复 attempt 返回真实状态而不重复执行。
[x] 本机 MCP 发布在既有 Bot SQLite writer 事务中创建 task/link 并写入私有 spool，防止并发观察半发布状态；失败保留 UNKNOWN，启动清理与发布串行；仍需精确 HEAD CI 核验。
