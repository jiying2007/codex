# Feishu Engineering Agent — 源码验证与集中现场验收

日期：2026-11-20。范围：个人和 2–8 人研发团队；复用现有飞书 Bot、Codex 原生运行时、ADK、Git/CI。**不使用产品版本标签。**

## 证据分级

- **SOURCE PASS**：精确提交 SHA 上的离线测试、Python 3.8/3.11/3.12 全量回归、安装/回滚门禁成功。只说明代码合同通过。
- **HOST PASS**：目标主机 `vstrong100` 的实际二进制、私有配置、单消费者、协议、权限和恢复过程可重复验证。
- **DELIVERY PASS**：真实需求与缺陷完成代码、PR/CI 和独立 QA；需要设备时另有真实 HIL 证据。
- **WORKITEM CLOSED**：仅当飞书项目或 TAPD 原业务负责人按照源系统流程关闭，才可声明。AgentRun 的 completed 不等于它。

本文件是**验收契约**，不是已执行的现场验收报告。具体绿色结论须绑定单一 HEAD 的工作流、环境、步骤退出码与证据引用；不可沿用其他 SHA 的绿灯。

## SDD 源码矩阵

| 阶段 | 已实现的代码合同 | 离线负向测试重点 | 现场门禁 |
|---|---|---|---|
| TASK-001 | 中文路由、项目与用户隔离、WorkItem 来源身份、原子事件收据、无 API `/wi add|list|status|handoff|attempt` | 重复事件、身份冲突、撤权、无模型调用、正文不进 DB | 已授权飞书消息或本地 CLI |
| TASK-002 | 可选 Card JSON 2.0、HMAC、事件身份和消息绑定、过期/重放保护、卡片请求持久化 | 同一回调的上下文冲突、他人点击、重复/迟到、发送结果 UNKNOWN | 飞书桌面/手机，SDK 和 3 秒响应 |
| TASK-003 | 精确 Codex host/repo/CODEX_HOME/thread、原生 initialize/resume/turn/interrupt、WorkItem→本机 MCP→既有 Bot 队列桥接、独立 Agent CODEX_HOME/API 凭据、持久 effect 收据 | scope/hash 错配、Unix UID 错配、个人 auth.json/共享计费、仓库策略漂移、孤儿任务、乱序通知、UNKNOWN 不重放 | vstrong100 专用 API 身份、同 UID、Bot worker、App Server 与恢复实测 |
| TASK-004 | TAPD/飞书项目可选只读读取；手工来源标记未核验；版本哈希不存正文 | 403/404、源身份与版本冲突、撤权后不得读取 | 真实一条需求、一条缺陷；无权限可走人工路径 |
| TASK-005 | 独立 Run、多仓版本化接口、GitHub PR/CI 可选适配、一次性发布、签名 QA、人工反馈 | 不同 PR/CI/QA SHA 不可拼接；CI 不等于 QA/HIL；外部写 UNKNOWN 不重放 | 真实 Feature 和 Bug PR/CI/QA；涉及设备时实际 HIL |
| TASK-006 | WAL 一致性备份、私有 spool/策略校验、哈希清单、隔离恢复演练、单消费者 cutover gate | 损坏备份、权限/符号链接、恢复不一致和重复消费者 | `vstrong100` 暂停旧服务、真实备份/恢复/回滚 |

源码关键测试入口：`tests/test_feishu_agent_mcp.py`、`tests/test_feishu_codex_bot.py`、`tests/test_feishu_engineering_agent.py`、`test_feishu_engineering_manual_items.py`、`test_feishu_engineering_manual_bot.py`、`test_feishu_engineering_workflow.py`、`test_feishu_engineering_workflows.py`、`test_feishu_engineering_native.py`、`test_feishu_engineering_cards_complete.py`、`test_feishu_engineering_channel.py`、`test_feishu_engineering_source_bridge.py`、`test_feishu_engineering_contracts.py`、`test_feishu_engineering_delivery.py`、`test_feishu_engineering_github_adapter.py`、`test_feishu_engineering_end_to_end.py`、`test_feishu_engineering_migration.py`。

### 一次性源码验收命令

```bash
python -m unittest discover -s tests -p 'test_feishu_engineering*.py' -v
python -m tools.codex_assets.feishu_engineering_agent --dry-run \
  --allow-repo robot-app --selected-repo robot-app --text '分析 sensor 初始化'
python -m tools.codex_assets.feishu_engineering_agent --probe-runtime
```

`--probe-runtime` 只执行 `codex --version` 与 `codex app-server --help`；运行在 CI 时不能代表 `vstrong100`。仓库完整门禁另见 `.github/workflows/full-regression.yml`、`runtime-binding-contract.yml`、`profile-context-contract.yml`，以最终提交的 9/9 job 结果为准。

### 本机 MCP WorkItem 纵向合同

关联 WorkItem 的 worker 使用原生持久 `codex exec --json`。离线测试覆盖实际 worker 调用边界（假 subprocess）、无效或不完整终态拒绝、只回传 agent_message、精确 thread/host/cwd/专用 CODEX_HOME 回执。原生 transcript 留在专用私有目录，不写入任务账本。查询回执不等于授权继续执行；真实主机持久化、恢复与同线程后续回合仍待验证。

离线回归必须覆盖以下完整链路：`/wi add` → `/wi attempt`（精确 scope SHA-256）→ `submit_workitem_task` → 既有 Bot spool/worker → `get_workitem_task`。MCP 进程不启动 Codex；worker 只使用独立专用 `CODEX_HOME` 与私有 API 凭据。负向测试必须证明：共享计费、个人 `auth.json`、Unix UID/仓库/模式/范围不匹配、策略指纹变化、孤儿任务和 spool 丢失均拒绝或进入 UNKNOWN，绝不重绑或自动重放。Edit 只到 `waiting_ci` + 未验证 commit evidence；不伪称 PR/CI/QA 已通过。

目标主机 `vstrong100` 必须另外核验：私有环境文件 0600、Agent CODEX_HOME 目录 0700 且无 `auth.json`、Bot 与本机 MCP 同 UID、实际 Codex provider 只读取该专用 API key/base URL、没有回退到个人 ChatGPT 登录目录。仅仅设置 `FEISHU_AGENT_BILLING_SOURCE` 文本值不是计费身份凭证。

## 集中现场验证顺序

1. **主机基线与回滚锚点**：查看实际 Bot systemd/锁/队列/WAL/spool/私有配置，记录权限与脱敏哈希，先做独立备份和临时恢复演练。严禁启动第二个消费者。
2. **最低权限文本交互**：如现有 Bot 已获消息权限，在同一 Bot 测 `/wi help → add → handoff → attempt → status`；没有消息权限则先用本地 stdin CLI。两条路径均不需要飞书项目企业 API。
3. **可选卡片**：仅在应用授权后开启测试开关。核查 Card 2.0 在手机和桌面端的实际签名、事件字段、幂等、过期与快速 ACK。不可据此授予写代码或模型权限。
4. **真实 Codex 能力**：核对目标主机的版本与 `codex app-server generate-json-schema`（无模型），对照请求字段与沙箱权限；测试 exact thread resume/turn 事件/interrupt。模型回合须先取得独立额度与身份授权，不消耗被禁用的共享额度。
5. **外部工作项**：有 TAPD/飞书项目 API 权限才做只读拉取和身份版本核验；无权限仅记录 `user_supplied_unverified`，不使用网页 cookie/模拟权限，也不阻塞内部代码开发。
6. **真实研发交付**：一条低风险需求、一条低风险 Bug，通过 SDD、独立允许的 Codex 实现、草稿 PR、精确 SHA 的 CI 和独立产品/测试 QA。跨仓协议逐仓同版本验证，实际板卡联调单独提供 HIL 证据。
7. **唯一生产消费者切换**：前述回滚、权限与现场门禁通过后，人工执行服务切换并证明唯一监听者、任务恢复及故障回退。源工作项的最终关闭仍由其业务负责人操作。

## 不可越过的边界

- 不自动使用 Codex/ChatGPT Work 共享模型额度，不创建定时巡检或第二套 Agent Runtime。
- 数据库、卡片和聊天不作为飞书项目/TAPD 的业务权威；GitHub Issue 不是需求/缺陷主入口。
- 外部 PR、评论、模型执行、部署/烧录、合并分别验证作用域和授权。远端结果不明时先核对，不盲重试。
- **没有 SOURCE PASS 不进入集中现场验证；SOURCE PASS 不等于 HOST/DELIVERY/WORKITEM PASS。**

## WorkItem queue publication and text status
Offline regression covers simultaneous same-scope submissions, spool failure with retained UNKNOWN, reserved idempotency namespace, bounded source status, replay of queued attempts and current actor/repository scope. These are source-level tests, not a production host result.

Offline exact WorkItem cancellation tests cover authorized chat queue cancellation, foreign actor and revoked repo denial, repeated cancellation, unrelated queue preservation, exact local process signaling, and no successful terminal status inferred from a signal. The real process tree, sandbox and provider cancellation remain host-qualified checks.

## Continuation path
Offline worker fixture: one prior successful edit, one exact successor with new scope approval, same thread and root worktree, separate new local commit receipt, duplicate proposal/queue idempotency, fork rejection, and old Run delivery rejection. Mock native subprocess verifies exact `exec resume` UUID and rejects a different thread before Git commit. Worktree identity and clean HEAD are checked on the real worker path; actual installed CLI/provider/session and host Git tests remain required.
