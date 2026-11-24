# 终态架构设计

## 单一生产通道
现有 feishu-codex-bot.service -> 可信 SDK event -> 统一入口/来源/话题 -> 统一 policy -> SQLite + 私有 spool/queue -> CodexRunner exec --json / exec resume exact UUID -> 实际 Git/CI/QA evidence -> 飞书文本。可信本机 MCP 只调用同一业务/入队接口，不另起执行器。默认一个 worker；有限并行仅独立 workspace/session。现有系统的其他 CLI/ADK 资产不重写。

## 数据
逻辑 Conversation(tenant, chat, trusted thread/root, owner/access), WorkContext(目标、来源、仓库、范围), CodexSession(host, repo, cwd, home, thread, mode), Task(queued/running/succeeded/failed/canceled/unknown), EventReceipt(event+digest+决策/授权/副作用回执), Evidence(commit/PR/CI/QA)。源身份与执行身份分离，文档独立或辅助；去重按 tenant/provider/canonical space+type+id，不能仅按数字。空间别名/API canonical key 需核验后合并，禁止猜测。多个不同主工单不隐式合并。控制消息不付费。

话题绑定优先 SDK thread_id/root_id，根消息使用自身 message_id；无可靠话题字段时必须显式选择，禁止群聊全局 last task。按授权用户及租户隔离，维护 reply 根绑定及重启持久化。项目配置将 space/module 映射到允许仓库；显式 repo > 已有话题绑定 > 确认模块映射 > 唯一授权候选，否则澄清；绝不把 codex 默认仓库冒充 example-space 业务仓库。

## 来源
严格 HTTPS host/path parser，去掉仅追踪参数，拒绝 userinfo、异常端口、伪域名、编码路径/不支持类型。仅解析可不联网；正文可选官方 scoped provider reader，复用 feishu_documents。禁止任意 URL fetch/重定向、绕过登录或未授权 Cookie。链接单独输入只关联并提示缺失；明确分析/开发指令才走授权。按来源标记 unverified/user_supplied/verified/denied，记录版本/摘要，来源文本永远是数据，不是授权。当前无 API 可用受控文字+文档完成最小上下文；按需补充，私有 spool/原生 transcript，不在 SQLite/log 复制全文。

## 授权与执行
一次性私有管理员配置允许租户/chat/actor/repo/modes/工作目录/模型及计费身份、回合/超时/预算、Git 权限。新任务精确范围与现时策略绑定；明确普通动作在预授权范围内直接入队，scope 改变或高风险动作须独立授权。未知控制命令拒绝，模糊任务澄清，不向模型回退。飞书与 MCP 均在 enqueue、worker claim/model start 核验。独立外部身份及 private home，禁止个人 auth.json、个人 ~/.codex、SSH/其他凭据访问；独立 HOME 并非完整隔离，须测试文件系统。预算以真实 provider/gateway 计量，不用回合数冒充金额。保留 #82 --unshare-pid --proc /proc 和原有双层沙箱；read 不写 repo，edit 隔离 worktree。所有 remote writes 按授权，禁止自动 merge/release/flash/delete。

只复用 CLI 执行和精确 thread/resume，不接管个人线程、不用 --last。工作区/模式切换不能冒充原生恢复；创建关联新会话并交接审核摘要。仓库规范、ADK 与 Knowledge Provider 负责研发方法；任务复杂度决定是否 SDD。

## 交付与恢复
精确 Git head/PR/required CI 关联，独立测试/QA；完成执行≠交付≠原工单关闭。反馈为可复制文本，当前 GitHub 适配器仅 GET，不负责发布或回写。排队持久化、防重复，running interrupted UNKNOWN，取消精确进程及队列身份。任何已启动 CLI 的非零退出、执行后计费/完成回执缺失均为 UNKNOWN，不自动重放。交付封存与编辑续接在同一入队事务再次核验，避免并发改写已核验版本。

迁移先冻结旧 Bot 及全部本机写入方，再做私有备份、恢复演练与统一归档。锁和 DB 路径必须与冻结 policy/env 一致，主 DB/WAL/SHM 均核验身份与权限。历史仅通过原生 SQLite 归档；新程序发现旧 ledger/关联记录而无完整迁移标记时拒绝启动。旧 DB/备份保留供离线恢复，新部署无旧记录无需迁移。持有 Bot 锁不等于已经证明全部外部写入方停止。

## 模块
保留 Bot transport/worker/StateStore/spool、文档读取及最小 MCP；工程包保留 sources/service/executor/delivery、只读 GitHub 证据、预算、精确 CLI 回执、策略摘要与离线迁移。AppServer/runtime_bridge/card/actions、旧 offline router/RunStore/manual_items、HMAC 授权工作流和独立跨仓契约执行模块已删除。旧结构仅以固定历史 SQLite fixture 验证迁移，不以可运行旧模块维持兼容。

## 当前配置与执行边界

`engineering_enabled` 控制远程话题入口，`agent_intake_enabled` 控制独立模型执行。本机 MCP 仅保留 submit/get/cancel queued。所有模型执行均使用同 UID Agent 身份、持久请求和策略摘要；旧普通聊天、`/wi`、卡片和 `run-once` 不再提供模型回退。MCP 与远程任务共用同一队列，策略、专用凭据或预算配置变化使既有排队任务失效。编辑必须使用可提交的独立 worktree。

当前金额适配器只支持 LiteLLM external_gateway。专用环境命名空间配置 key、网关、模型、key alias 和批准金额；key info 必须证明 bearer、模型白名单、未阻止且无自动重置，并提供有效额度和累计消费。所有本地准备完成后、启动进程前保存 before 观察，正常返回后保存 after；这些是累计消费观察，不是单任务最终账单或原子硬限额。真实网关请求预留、故障拒绝和结算是现场资格，不由本地 fixture 代替。

模型改过的测试/构建脚本按非可信代码处理；验证复用现有 Bubblewrap，默认无网络、无服务或模型密钥，专用 Agent 历史也被屏蔽，只允许工作区和临时空间写入。沙箱不可用时拒绝，不降级到主机执行。依赖和工具链预先安装，`.git` 指针只读，受控提交由控制器执行。
