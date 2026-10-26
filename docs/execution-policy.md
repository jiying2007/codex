# Execution Policy

Smoke 恢复主构建时同时使用 `--reuse-context-input --reuse-machine-inputs`，以哈希及 profile 校验保留已批准的本机 context 与执行规则输入。变化的输入拒绝复用；显式规则输入与复用模式不能混用。

Codex 的唯一任务执行策略面绑定 ADK 8.1.1 canonical Execution Policy v2。

- 配置：`manifests/execution_policy.json`
- exact decision：`tools/codex_assets/execution_policy/decision.py`
- exact reducer：`tools/codex_assets/execution_policy/reducer.py`
- exact public namespace：`tools/codex_assets/execution_policy/__init__.py`
- exact contracts：`tools/codex_assets/execution_policy/contracts.py`
- Codex host adapter：`tools/codex_assets/execution_policy_adapter.py`
- CLI：`python3 -m tools.codex_assets execution-policy`

旧 `runtime-control` Python/CLI/config surface 已 hard-cut，不提供 alias、fallback、双读或双写。保留的 `runtime_control.*` 字符串仅是 ADK 冻结 wire schema 名称，不表示旧执行面仍存在。

所有 action 和 goal start 都在与 intake 相同的线程锁内先用 canonical reducer 校验，再追加并同步 journal。非法或重复 progress 被拒绝时不改变 journal；新 goal 保留已终结历史。

若旧 host adapter 曾将被拒绝的非递增 progress 写入 journal，可先运行 `execution-policy journal` 得到只读计划，再以计划的 `before_sha256` 执行 `execution-policy journal --apply --expected-sha256 <sha256>`。恢复仅允许 canonical reducer 明确拒绝的非递增 progress；其他错误继续阻断。原字节完整备份，恢复记录保存被隔离事件的 hash、原因、前后 journal hash，成功后回读。该操作不 complete goal、不补证据、不产生 PASS；恢复后按真实目标继续或显式 abort/replan。

Execution Policy v2 要求每个 goal 在 `goal.started` 时携带可验证 intake：task mode、request/routing digests、authority id 与 routing provenance。缺失 intake、使用 v1 policy、source-set blob 漂移或 behavior baseline 漂移均 fail closed。

Codex 资产工具的日常 CLI 支持 Python 3.8 及以上。宿主包保留历史上游源码使用
`datetime.UTC` 时的 `timezone.utc` 兼容别名；当前 8.1.1 Execution Policy 源码
本身不依赖该别名。此桥接不改变上游文件、来源哈希、策略条件或缺失 intake 时的 FATAL 结果。

`readonly`/debug/review 若没有受管 mode-authority verifier，不会自动获得较弱 artifact gate；canonical engine 会按 fail-closed 规则提升到 implementation artifact boundary。

## 日常 CLI 与线程身份

Digital Worker 不是日常 CLI 的安装依赖。下方 `authority-id/source-id=digital-worker` 仅是显式采用该集成时的来源示例，不得照抄成实际未发生的授权或路由证据。普通项目记录实际采用的项目/资源治理来源，验证、审查和发布仍由项目规则决定；不能为了通过门禁伪造 intake。

在项目目录中执行门禁时，模块从资源仓加载，检查绑定当前准确线程，而不是按“最近更新”猜测其它会话：

```bash
(cd ~/codex && rtk python3 -m tools.codex_assets execution-policy \
  --thread-id "${CODEX_THREAD_ID:?current thread id required}" gate --event final)
```

没有当前线程 ID 时先核实实际会话，不能借用别的线程状态。`gate_allowed` 只表示该线程的本地执行策略结论，不等于项目测试、独立审查、设备验证或产品放行已经完成。CI 的外部 cwd `gate --help` 仅验证命令可解析，不是一次真实门禁通过。

入口示例（在 Codex 资源仓中、显式采用 Digital Worker 来源时）：

```bash
python3 -m tools.codex_assets execution-policy goal start \
  --goal-id example \
  --token-budget 200000 \
  --time-budget-seconds 14400 \
  --success-criterion tests-pass \
  --required-evidence tests-pass \
  --open-items 1 \
  --task-mode implementation \
  --request-sha256 <sha256> \
  --routing-decision-sha256 <sha256> \
  --authority-id digital-worker \
  --decision-id <decision-id> \
  --source-id digital-worker \
  --source-version <version>
```

Journal 仅保存结构化事件和哈希，不保存 prompt/messages/content/raw cwd。当前 journal 位于 `~/.codex/execution-policy/`。

## 日常任务自动 intake

非平凡任务在实施前使用幂等入口，避免只在结束时才发现缺 intake：

```bash
(cd ~/codex && rtk python3 -m tools.codex_assets execution-policy \
  --thread-id "${CODEX_THREAD_ID:?current thread id required}" ensure \
  --request-file /tmp/task-request.md --task-mode implementation \
  --success-criterion repo-and-tests --required-evidence repo-and-tests \
  --open-items 1)
```

临时文件保存本次真实用户请求，不进入知识库或 journal；ensure 读取一次并计算 request 摘要，结合实际 runtime/project AGENTS 文件摘要、显式任务模式与验收项产生本地 `codex-project-routing/v1` 决策。authority/source 使用真实本地 adapter 身份，不冒充人审或 Digital Worker。它不获得 managed readonly authority 的特权，也不降低 canonical artifact gate。

`--dry-run` 不创建 journal；首次执行返回 `REGISTERED`，相同请求和路由重试返回 `ALREADY_REGISTERED`。已有目标与请求或路由不符时退出 2，保留原 journal，必须显式 replan 或开始新的逻辑任务。ensure 不自动补造 evidence，不自动 complete，也不代表 final gate 通过。有效 intake 只是前置条件；目标、验收证据、工件与 checkpoint 仍由实际执行登记。

本入口是 Agent 自动执行约定，不是 app-server 的隐式启动 hook；只有执行它后才会产生任务记录。

该要求由 `src/codex-home/AGENTS.md` 分发到全局运行规则，适用于 Hub、其他项目、无 Git 和无 remote 的目录；不依赖项目自己的 AGENTS 再次声明。非平凡只读分析也应在取证前按实际模式登记，不能等到 final 才首次调用策略面。`ensure` 成功后继续登记真实证据、工件、进展和 checkpoint，再完成目标及运行 final gate；不能将登记成功当成任务通过。

其他线程缺 intake 时，诊断者可以读取该线程的原始收据，但不得借用自己的 PASS、代写它的 journal 或追补一份历史完成证明。原线程继续工作时应使用自己的真实请求与准确线程执行 `ensure` 并重新核验证据。已经启动的会话可能保留旧规则快照，应核对实际收到的 AGENTS；文件更新不证明旧线程已执行 intake。

回执将现存状态和本次写入分开表示：已登记任务的 dry-run 返回 `persisted=true`、`read_only=true`、`write_performed=false`；新任务 dry-run 返回 `persisted=false`，不创建 journal。

长任务应按真实上下文量与预计轮数显式传入 `--token-budget`；默认 300000 仅是初始预算，累计输入计量包含重复加载的上下文。steady/apply 出现 stop 时先停止实施并 replan，不能用终态 final 通过推导未超预算。证据、任务预算和产品验收分别报告。

## 安装前检查与同源校验

### 长任务收敛能力适配

Host CLI预留`progress --revision <n> --criterion-id <original-id> --change-kind <kind> --evidence-id <registered-id>`及只读`milestone --criterion-id <original-id>`。执行前要求已受管导入的exact ADK源码声明`execution_policy.convergence/v1`；缺少能力明确拒绝，不手改冻结镜像、不伪造provider身份，也不把help成功当运行已采用。

能力可用后，progress必须绑定原验收及新证据digest，关键假设/阻塞变化可算进度。旧revision-only保留历史可读性，但在新引擎中不能持续清除无进展计数。默认8次有效进展而无关闭项触发replan，可由provider支持的`progress.non_closing_limit`显式配置；只提高预算不清零。replan还需`--plan-before-sha256`、`--plan-after-sha256`及`--adjustment scope|dependency|acceptance|verification`，前后计划已登记且不同，审查仍须确认实际执行变化。

milestone只核当前evidence-bound checkpoint和steady状态，不完成父goal、不要求无关全目标证据、不授予commit/apply/release；产品验收及独立审查仍由项目负责。完整目标完成时才用final。新引擎`budget_status`单列当前快照预算，final PASS不能推导历史预算合规或继续执行授权。

当前状态只维护一个入口，默认8 KiB/最多3个下一动作，历史用指针；项目确需更大原文时显式说明并按需读取。源仓ADK可运行`devkit.sh goal state-check`检查JSON入口，该文档卫生检查不替代内容真实性或完成验收。

`doctor --scope repo`、`doctor --scope governance`、完整 governance report 与运行时
共用 `execution_policy_adapter.load_runtime_config`，不再维护旧 wheel/v1 配置校验器。
加载器只读取当前 manifest、provider lock 和四份固定 package/contracts/decision/reducer 源文件；
核对字段、策略下限、sources 结构、provider 身份和 Git blob 后才返回配置。
它不访问 state database、session、journal 或 Digital Worker checkout。
缺失/混入退役 manifest、错误来源、v1 策略、放宽 artifact gate 或保存 raw content 均失败。

完整 `governance-report --json` 使用 schema_version=2 和 `execution_policy` 字段，
不提供旧字段 alias；有界 count-only `--summary-json` 投影仍为 v1。
仓库检查通过不代表 live 已更新，也不替代 Skill 来源补齐、真实任务或产品验收。
安装验证使用原有 build/plan/dry-run/apply/doctor/rollback，测试只在隔离副本运行，
不写成员认证和会话目录。

## 7.0.31 来源迁移

manifest schema 由 3 升至 4：`engine.module` 指向 canonical package，
`behavior_baseline.source_blobs` 精确记录四份上游源文件；旧 engine.py 物理退役，
不提供 alias/facade，也不静默接受旧自定义配置。自定义 config 需按当前 manifest
结构迁移并重新验证，不能只改变版本数字。

本次四份上游文件逐字节复制，9 个 Agent 在该来源中正文与旧版相同但来源归属已
重新核验。既有 host-owned ManifestError/privacy adapter 保持不变，不冒充上游源码。
Policy v2、event/state v1、decision v2、intake v1 及日志位置不变；已有日志不重写。
基线生成的 19 个合成回放样本验证状态/决策指纹与失败语义，不能代替真实任务资格。
来源完整不等于成员已升级、权限已批准或运行时/产品已通过资格认证。

### 上下文维护与恢复

`compact` + `context-pressure` 表示需要维护上下文。它不证明项目存在业务阻塞。
先保留真实 checkpoint 与恢复入口，再由宿主原生自动压缩或可用的 `/compact`
完成维护，之后复核最新 usage 和同一任务的门禁。模型未暴露压缩工具不等于宿主
没有压缩能力。没有新 usage 或宿主结果时，不连续轮询、不把同一提示计为三轮
业务阻塞；不伪造进展、heartbeat、压缩成功或外部等待来复位计数。
若宿主确认压缩失败或不支持，才请求人工压缩或新会话接力，并说明具体限制。
预算 stop、stale/retry replan、缺失工件及完成验收仍按 canonical decision 执行。

宿主适配层输出 `host_context_maintenance`，只提供维护诊断，既不改写上游 decision
字段，也不放宽 gate。配置文件中存在阈值不证明当前会话已经加载或已经压缩。
`threshold_alignment` 用实际观测窗口对比配置文件阈值；窗口未知、配置缺失或
非 total scope 时返回 unknown。命令行、profile 和宿主覆盖仍需独立核验。

受管默认阈值为 100000 tokens、total scope；模型窗口仍由宿主识别。
在观测窗口 258400 时早于本地 129200 门禁，不保证适合所有模型。
支持 `build --context-config-from ~/.codex/config.toml`：只合并两个压缩 root key，
其余配置必须保持 TOML 语义相同；无法安全合并则拒绝构建。输入路径与 hash 写入
本机 build receipt，完整输入只存在本机受管 build，不进入源码或知识库。
Python 3.8–3.10 需要 `requirements-codex-assets.txt` 中固定版本的 tomli；3.11 起用
标准库 tomllib。无解析器时合并拒绝，诊断标明不可读取，不猜测配置生效状态。
`build --reuse-context-input` 仅复用 receipt 中路径且 hash 未变的显式输入。
smoke 恢复主 build 使用这个入口；输入变化时拒绝重建，不能悄悄退回模板配置。
按 build、doctor、plan、dry-run、apply、check 同步；使用 `check --no-build`
保留这个已核验 build。默认 plan 会保留本机 config；显式覆盖前必须检查配置差异、
备份和准确当前线程 apply gate。未注册旁支不可借用主线程身份安装。
回滚使用原 apply plan 的备份，不手改 live。生效范围由宿主配置加载决定，已有
blocked 原生 goal 不会因配置文件更新而自动被恢复。

官方来源：
[Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)、
[CLI 命令](https://learn.chatgpt.com/docs/developer-commands?surface=cli)。
2026-10-11 核验，reviewed；2026-11-10 后重新核验再提升指导规则。
本机配置和合成测试不能替代宿主真实压缩与目标续跑证据。
