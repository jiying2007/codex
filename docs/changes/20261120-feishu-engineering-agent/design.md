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
精确 Git head/PR/required CI 关联，独立测试/QA；完成执行≠交付≠原工单关闭。可复制反馈默认，授权 comment 可选。排队持久化、防重复，running interrupted UNKNOWN，取消精确进程及队列身份。状态库迁移须离线冻结、私有备份、restore rehearsal、验证 source ids/evidence/receipt/queue/spool、回滚；不能清理用户文件或盲回放。旧入口替代并迁移验证后删除，不长期双轨。

## 模块
保留 Bot transport/worker/spool、文档读取及最小 MCP。收敛 models/config/channel/sources/service/policy/store/executor/delivery 职责；精简或删除重复 offline router/store、local-only workflow、AppServer/runtime_bridge、card/actions、独立跨仓 contract。先保留生产中不可替代的安全/历史数据关系；按引用与验证删除，而非按文件数量。
