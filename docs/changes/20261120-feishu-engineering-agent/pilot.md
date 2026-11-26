# 主机迁移与现场验收指引

本文是待操作指引。源码修改、合并或离线测试不代表已经操作真实主机；本轮不执行生产停服、迁移、重启或真实模型调用。执行证据只记录在 [verification.md](verification.md)，未观察的项目保持 `NOT_RUN`。

所有示例路径、账号、仓库和域名均为合成数据，必须替换为实际部署值。保留已有唯一 `feishu-codex-bot.service`，不新增 Bot、MCP 后台 Worker 或第二个消费者。


从 Windows Terminal/PowerShell 使用既有 SSH 路径进入目标主机：

~~~powershell
ssh -tt leiwenjun@vstrong100
~~~

在主机中进入 ~/codex。先执行 rtk git status --short；若工作树不干净，停止并保留现状，不 stash/reset/clean。仅在干净时执行 rtk git fetch origin main 和 rtk git merge --ff-only origin/main，再用 GitHub main 当前完整 SHA 运行预检。不要使用旧脚本附件或脚本内置历史基线。


## 1. 先确认部署类型与边界


## 已知 vstrong100 历史现场快照（2026-11-24；必须重新核验）

最近一次用户提供的现场记录显示：

- 唯一服务 feishu-codex-bot.service 当时为 active/running，MainPID 1480533，NRestarts=0；systemd UMask=0002，Linger=yes；Codex CLI 0.171.0。以上均为历史快照，不是当前状态。
- 当时 Bot DB 为 /home/leiwenjun/codex/mcp/secrets/feishu-codex-current-state.sqlite3，权限 0644；spool 为同目录下 feishu-pending-jobs，权限 0700。锁文件在同一私有目录，精确名称必须从当前私有策略读取，不能根据 DB 文件名推断。
- 当时任务状态只有 completed:1；没有旧 AgentRun DB；WorkItem、agent-intake、cards 均关闭。
- 当时 billing_source 为 unapproved，专用 API key 与 Agent CODEX_HOME 均未配置。因此不能启动模型，不能回退个人登录或共享额度。
- 0644 的数据库权限不满足当前迁移备份要求。若当前复核仍为 0644，必须先停止唯一服务并冻结所有写入方，确认文件类型、属主及 WAL/SHM 后，再按 0600 修正；禁止对运行中的数据库 chmod。spool 若仍为 0700 可保留。
- 若当前再次确认旧 AgentRun DB 不存在且 Bot DB 的 agent_run_task_links 无记录，则不执行 unify；仍需配对备份、恢复演练、任务/外部效果核对和单服务切换。

当前版本要求的 unit 安全属性为 UMask=0077、NoNewPrivileges=true、PrivateTmp=true。必须从 systemd 有效属性重新观察，不沿用上述历史值。


无旧 `feishu-engineering-agent.sqlite3`、旧关联记录或相关 WAL/SHM 遗留的新部署，不需要 `unify`。按 [新配置](../../../mcp/feishu-codex-bot.example.json) 建立私有目录，先保持 `agent_intake_enabled=false`、`agent_allowed_modes=[]`，可开启 `engineering_enabled=true` 验证无模型话题入口。

已有旧 ledger 的部署必须离线迁移。新版 Bot、`check` 和 MCP 检测到未迁移历史会拒绝准入；删除旧 DB、改状态或重新命名文件都不能代替迁移。旧代码已删除，历史数据库及备份仍保留作审计和离线恢复。

开始前核对实际源提交、工作树改动、服务账号、Python/SDK、`rtk`、Codex CLI、Bubblewrap、unit/drop-in、state/spool、环境文件和锁路径。更新源码不覆盖用户私有配置，不对脏工作树自动 reset、clean 或 stash。已有生产服务状态须重新观察，不能继承历史的 active 或 Linger 结论。

先运行仓库内的只读预检脚本，核对精确部署提交及有效服务配置：

```bash
rtk python3 -B ~/codex/scripts/feishu-cutover-preflight.py \
  --root ~/codex --expected-sha <GitHub-main-40位SHA>
```

`--expected-sha` 必须使用本次实际准备部署的 GitHub main 完整 SHA，不使用脚本内置旧基线。脚本只观察 systemd、进程参数、Git 状态、私有配置文件权限及路径；不打开 SQLite、不读取任务正文、不启动模型、不修改服务。默认 JSON 只输出密钥字段是否存在，不输出密钥、域名或私有路径；不要使用 `--show-paths` 分享回执。服务停止、无法识别唯一消费者、环境文件与运行参数不一致或工作树不干净时，结果会保留阻塞项，不代表可以迁移。

`check-budget` 在 #91 合并后可在保持 `agent_intake_enabled=false` 时单独验证专用网关元数据和空 session 日志读取；它不证明请求级硬预算或最终结算。两个预检均成功也不替代后续冻结、备份、恢复演练与现场验收。

## 2. 迁移前冻结与未决任务

1. 禁止新任务入队，停止全部本机 MCP 写入进程及其调用方；Bot 的单实例锁不能证明这些写入方已经停止。
2. 记录旧任务、spool 和外部效果，核对 queued/running/unknown 以及旧 waiting_ci/waiting_qa。只进行已授权的完成、精确取消或人工核对；不得为清空门禁新增模型调用，也不得把未知结果改成成功。
3. 在主机操作获准后停止已有唯一 Bot。确认进程及实际服务锁均已释放，全部写入方持续保持冻结，直至迁移和配置切换结束。

待操作的服务命令示例：

```bash
rtk systemctl --user stop feishu-codex-bot.service
rtk systemctl --user status feishu-codex-bot.service
```

停止命令成功不等于所有 MCP、模型子进程或外部效果已消失，仍须核对实际进程和任务。锁被占用、数据库变化或存在未决状态时，迁移拒绝继续。

## 3. 冻结配置与配对备份

迁移读取原私有 policy/env，不依赖新 Bot 配置解析。旧 `manual_workitems_enabled=true` 可以用于离线 `unify`；`engineering_cards_enabled` 必须为 false。也可使用明确开启 `engineering_enabled` 的已冻结配置。

在备份前确认原私有策略显式记录实际绝对路径 `state_db` 与 `lock_file`。原环境文件和当前命令环境中的 `FEISHU_STATE_DB`、`FEISHU_LOCK_FILE` 若存在，必须与这两个路径一致。不得用新建的无关锁文件冒充真实服务锁。若原配置依赖隐含默认值，须先在服务冻结状态下核实、固定这些有效路径，再备份。

原 DB、WAL/SHM、spool 和配置必须属于服务账号；私有文件 0600、目录 0700。先在冻结状态核对权限，不对运行中的数据库自动改权限。备份包含 SQLite 一致快照、对应旧 ledger、spool 及所提供的私有 policy/env；SQLite backup API 将已提交的 WAL 数据纳入快照，不靠只复制主 DB 文件。

以下命令从任意工作目录运行，使用同一源码与实际 Python 环境。备份父目录须已存在并为 0700；本次目标目录须尚不存在且不在 spool 内，由 backup 创建：

```bash
rtk env PYTHONPATH=/home/service/codex python3 -m tools.codex_assets.feishu_engineering_agent.migration_cli inspect \
  --db /srv/feishu-agent/private/feishu-codex-state.sqlite3 \
  --spool /srv/feishu-agent/private/feishu-pending-jobs \
  --private-policy /srv/feishu-agent/private/policy.json \
  --private-env /srv/feishu-agent/private/feishu.env

rtk env PYTHONPATH=/home/service/codex python3 -m tools.codex_assets.feishu_engineering_agent.migration_cli backup \
  --db /srv/feishu-agent/private/feishu-codex-state.sqlite3 \
  --spool /srv/feishu-agent/private/feishu-pending-jobs \
  --private-policy /srv/feishu-agent/private/policy.json \
  --private-env /srv/feishu-agent/private/feishu.env \
  --backup-dir /srv/feishu-agent/backups/example-cutover \
  --consumer-paused

rtk env PYTHONPATH=/home/service/codex python3 -m tools.codex_assets.feishu_engineering_agent.migration_cli rehearse \
  --backup-dir /srv/feishu-agent/backups/example-cutover
```

`--consumer-paused` 是操作者对真实冻结状态的声明，不会停止进程。`rehearse` 在新临时目录恢复并核对完整性、摘要和双库关联，不覆盖生产路径，也不证明实际服务已切换。失败时保留源数据与备份供检查；不要自动覆盖或删除。

## 4. 统一状态，随后转换新配置

备份后不修改 policy/env、state 或 spool；有任何变化必须重新核对并制作新配对备份。全部写入方仍冻结时执行：

```bash
rtk env PYTHONPATH=/home/service/codex python3 -m tools.codex_assets.feishu_engineering_agent.migration_cli unify \
  --db /srv/feishu-agent/private/feishu-codex-state.sqlite3 \
  --spool /srv/feishu-agent/private/feishu-pending-jobs \
  --private-policy /srv/feishu-agent/private/policy.json \
  --private-env /srv/feishu-agent/private/feishu.env \
  --backup-dir /srv/feishu-agent/backups/example-cutover \
  --lock-file /srv/feishu-agent/private/feishu-codex-bot.lock \
  --consumer-paused
```

`unify` 再做恢复演练，核对当前数据与配对备份、配置和真实锁，事务归档旧 `fea_*` 历史、消息去重及任务关联，最后写入一次性迁移标记。它不创建原生 thread、不恢复旧模型执行、不删除旧数据库，也不启动服务。重复导入拒绝，任何失败回滚当前事务。

取得成功回执后，才转换运行配置：

- 删除退役的 `manual_workitems_enabled`、`engineering_cards_enabled` 及卡片、旧 QA/工作流专用凭据配置。即使值为 false 也不能保留旧开关。
- 使用显式 `FEISHU_BOT_CONFIG` 私有策略；把旧 `FEISHU_CODEX_WORKDIR`、`FEISHU_ALLOWED_OPEN_IDS` 中核对后的仓库与白名单写入该策略并删除旧环境字段，不保留隐含单仓回退。
- 使用 `engineering_enabled=true`。先保持 `agent_intake_enabled=false`、各仓 `agent_allowed_modes=[]`，完成无模型现场验证。
- 保持同一 state、spool、锁及服务账号；私有路径与实际 unit 一致。若采用本文的独立 env 路径，unit 的 ExecStart 必须向脚本传同一个 `--env-file`，不能让预检和服务分别读取两份配置。
- 不复制个人 `auth.json`；`isolation_write_paths` 不指向个人 HOME。专用执行目录、仓库与各 worktree 互不重叠。

旧数据库保留为离线历史；新版不再执行它，后续正常备份只包含一个活动 Bot DB。不得删除真实历史或私自把旧线程绑定为新会话。

## 5. 无模型现场验证

先对新私有配置运行 `check`；它可能初始化状态结构，但不启动模型。再在已获准的窗口更新并启动原唯一服务：

```bash
rtk bash /home/service/codex/scripts/feishu-codex-bot.sh check \
  --env-file /srv/feishu-agent/private/feishu.env

rtk systemctl --user daemon-reload
rtk systemctl --user start feishu-codex-bot.service
rtk systemctl --user status feishu-codex-bot.service
```

这些是待操作示例，本轮未执行。实际核验包括：

| 项目 | 所需真实证据 |
|---|---|
| 唯一服务 | 正确提交与 unit、同一状态/锁、单消费者；UMask=0077、NoNewPrivileges、私有 procfs 与嵌套沙箱实际探针 |
| 无模型话题 | 白名单用户的 issue/story/TAPD/文档链接、同话题补充、重复消息、错误命令和拒绝越权 |
| 退役入口 | `/wi`、旧卡片、旧 MCP 和 `run-once` 不恢复旧执行；缺独立授权不回退共享额度 |
| 文档权限 | 独立 `read-source --dry-run`，以及获准后的实际 API 读取；正文不进入公共日志 |
| 恢复 | 新状态的备份与恢复演练，排队输入及去重，运行中未知状态不自动重试 |

CLI version/help 成功只说明命令存在，不证明主机沙箱、模型兼容性或费用资格。不得把 `check`、测试全绿或模拟对象当作现场完成。

## 6. 真实费用与工程验收仍需单独完成

实际模型适配器仅支持 LiteLLM 外部网关。专用 `FEISHU_AGENT_*` 字段、`key/alias/models/blocked/budget_duration` 和金额规则见 [使用指南](../../feishu-codex-bot-usage.md#5-独立模型身份与预算)。当前真实独占身份、模型映射、网关请求级拒绝/在途预留、异步费用及最终账单验证均为 `NOT_RUN`。累计 key spend 不代表原子硬 cap 或单任务最终结算。当前源码会持久化每次任务的账务 session，并观察同 key 下精确请求的费用；异步日志为空时金额为 null，所有观察保持 settlement=pending。需现场核验实际 CLI 的 provider header 能力、网关 session 归属、普通专用 key 的自查日志权限和真实模型路由，不能用升级到某个版本的声明代替测试。

在保持模型入口关闭的新版私有配置下，先执行 `rtk bash ~/codex/scripts/feishu-codex-bot.sh check-budget --env-file <实际私有环境文件>`，确认专用 key 的元数据及空 session 日志可查询。它不执行模型、不创建 SQLite 状态，也不认证硬限额或最终结算。失败时保持关闭；即使通过仍须完成实际网关资格核验。

只有取得实际调用授权并核验费用通道后，才由操作者开启执行和必要仓库模式，验证低风险需求、缺陷、文档驱动任务及跨仓多轮研发。记录精确 native thread、工作区/提交、取消、重启、PR/全部必需 CI 以及真正的项目测试/QA。配置 CI 通过不自动完成跨仓联调或关闭原工单。

若需要回滚，先重新冻结所有写入方并保存切换后状态，核对新发生的任务、提交、模型费用和远端效果，再选择匹配版本及配对状态。不能盲覆盖旧 DB 丢失新记录，更不能靠重放未知任务“恢复成功”。

## 7. 显式发布的现场验收

先保持各仓 `github_delivery.publish_enabled=false`。核对已完成编辑任务的完整 SHA、
原始隔离 worktree、GitHub 仓库和基线后，才按实际发布授权逐仓开启，并将最小范围的
独立 `FEISHU_AGENT_GITHUB_WRITE_TOKEN` 写入私有环境文件；不在飞书或公共日志传递令牌。

可信话题所有者发送 `/publish <完整40位SHA>` 后，实际观察唯一意图、条件创建的分支、
草稿 PR 的精确 head/base，以及原 worktree 已封存。随后通过“检查交付”核验全部必需 CI。
同一请求或网络超时后的再次命令只能 GET 对账；不能通过新消息 ID 重推来代替核对。
部分成功应由操作者核对已有远端对象后完成缺失步骤，不删除本地意图重试。
验收还包括错误用户、错误 SHA、错仓、已有不同分支头、dirty worktree、过期/缺失写权限、
中断恢复和发布后继续编辑的拒绝。

这个步骤需要真实主机与仓库写权限。合成 Git 测试和当前项目自身的 PR 合并不代表
Bot 已完成真实业务发布，也不自动授予合并、发布产品或关闭工单的权限。
