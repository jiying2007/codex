# 终态验证记录

## 状态口径

源码候选、离线 CI、实际主机、实际模型/账单、业务 QA 分别记账。未观察的现场项保持 `NOT_RUN`；不把模型 mock、帮助探针或 CI 成功当作生产验收。当前批次为 [PR #89](https://github.com/jiying2007/codex/pull/89)，精确 head、合并提交和 Actions 链接以该 PR 的实际回执为准；此前 PR 的成功不自动继承。

## 已核对的历史基线

- #88 精确候选 `6a7b86ceb81946c859403bbaf8012f507522fc0e`：
  [Full Regression](https://github.com/jiying2007/codex/actions/runs/45593769578)、
  [Runtime Binding Contract](https://github.com/jiying2007/codex/actions/runs/45593769477)、
  [Profile Context Contract](https://github.com/jiying2007/codex/actions/runs/45593769489)
  在 Python 3.8/3.11/3.12 全部成功。独立源码审查核对原子取消/完成、输出回滚和迟到通知失败边界。
  合并为 `002ac9d160149a6fb8b9be408ec7aee022bfd4ed`，合并后的同九项检查也成功。
  这些结果不继承给本批后续源码。

- #81 合并 `a72071fb674c5126226e4732a30ed061ce95673f`；#82 合并 `76305a78fc3483cc23054c2387b274f4b238a4bf`。
- #82 候选 `19c14f23b851875a7b4ff1f15c6ae8009100673a`：Full Regression 45319808217、Runtime Binding Contract 45319808143、Profile Context Contract 45319808287 成功。历史现场 no-new-privileges 嵌套沙箱探针成功，不等于新版服务部署。
- 本轮启动时已核对上一候选 `d89ae769992967d541b6ed64d62319c1d816bac4` 的 [Full Regression](https://github.com/jiying2007/codex/actions/runs/45325338003)、[Profile Context Contract](https://github.com/jiying2007/codex/actions/runs/45325338015)、[Runtime Binding Contract](https://github.com/jiying2007/codex/actions/runs/45325338020) 全部成功。此结果不继承给后续提交。

## 本批修复及验证范围

| 范围 | 验证的实际行为 | 未覆盖的现场事实 |
|---|---|---|
| 入口与授权 | 旧 /wi、卡片、普通共享执行与 run-once 不调用模型；链接去重、话题恢复和权限拒绝；MCP 仅 submit/get/cancel queued | 飞书租户实际权限与生产消息 |
| 队列与执行 | 本机/远程请求和策略摘要复核；凭据/预算/输入漂移拒绝；精确 native UUID、多仓独立工作区；中断与完成回执缺失保持 UNKNOWN | 真实模型产出及主机隔离资格 |
| 验证隔离 | 验证命令强制 Bubblewrap、无网络和模型/服务凭据、临时 HOME、`.git` 指针只读；失败不在主机重试；Git/worktree/commit 使用实际合成仓库验证 | 历史验证环境的真实 bwrap 探针曾被 `NETLINK_ROUTE socket: Operation not permitted` 拒绝；目标主机越界写测试仍需执行 |
| 预算 | 本地 HTTP fixture 核验 self key info、身份/模型/金额；禁止重定向和环境代理；本地准备失败不占 before 回执；执行后存储失败和 CLI 非零退出为 UNKNOWN；同一任务不重复启动 | 实际独占 key、网关预留、故障拒绝、定价和最终账单 |
| 交付 | 固定本地提交、PR/branch/base、所有必需工作流的最新实际结果；禁止旧绿回退；联合版本集合；事务阻止续接修改已封存版本 | 真实多仓联调、项目 QA、原工单关闭 |
| 迁移 | 原始历史 SQLite fixture；配对备份、恢复演练、一次归档、去重保留；拒绝错锁、持有锁、环境漂移、宽松 WAL/SHM 权限和未决发布；无完整迁移标记不能启动旧状态 | 真实 writers 冻结、实际 DB 备份/恢复/切换 |
| 精简 | 13 个旧模块删除；旧模块专用测试删除，有效断言迁入现役测试；无旧模块运行依赖 | 生产已安装源码版本 |

历史验证环境曾执行无模型 CLI 版本/帮助探针：`codex-cli 0.172.0-alpha.2` 的 `--version`、`exec --help`、`exec resume --help` 可用，`qualified_for_model_calls=false`。这只描述当时的验证环境，不证明本候选当前执行环境或目标主机 0.171.0 的运行资格。

最终完整回归和精确提交结果随 PR 更新；任何失败必须修复后重新核对相应候选。测试使用合成数据，不读取真实业务正文、生产凭据或计费网关。

## 外部阻塞

当前没有目标主机操作通道，也没有批准的真实模型/网关调用。本轮不停止或重启生产服务。实际迁移、部署、费用和业务验收均为 `NOT_RUN`。

本地 Knowledge Provider 查询返回 `SOURCE_DRIFT`，Execution Policy `ensure` 返回 `Codex state database is unavailable`；未改写配置、伪造线程状态或补造成功回执。因此没有声称完成 Knowledge Provider 归档或本地 Runtime conformance；Git/CI 代码证据另行核验。

## 2026-11-25 深审整改验证范围

本批新增断言覆盖：同一事务中断后原消息可再次登记、已接受上下文不依赖历史消息 API、摘要不符拒绝、文档 URL 显式授权、精确取消启动窗口、结果重取与 UNKNOWN 人工终止、跨仓共享上下文、宿主 Git 外部程序拒绝及沙箱正向挂载。候选执行结果以对应 GitHub PR/CI 实际回执为准。真实目标主机嵌套沙箱、网关费用、授权 Git 远端写入及真实项目验收仍为 NOT_RUN。

## 2026-11-25 发布与费用观察候选

环境断开前，历史写入口清理六模块 93 项、execution-policy 83 项、预算/MCP/Bot
83 项定向测试曾分别通过；这些集合有交叉，不能相加作为全量测试数。FIFO 的有界子进程
回归和旧库保留另经独立复核。发布新模块与后续集成是在执行环境不可用后通过精确 Git blob
保全并整合，不能继承此前的本地通过结论。最终以对应 PR 精确 SHA 的既有全量回归及
Runtime/Profile 合同 CI 为准。

受控发布新增回归针对真实合成 Git 仓库的条件创建、远端竞争失败、隔离对象快照，
以及显式命令/权限/来源/脏工作区/错误仓库拒绝、唯一发布意图、丢失响应后的只读对账。
HTTP 和模型均为 fixture；没有对真实业务仓库执行 Bot 发布。

请求费用观察依据已核验的上游契约：
[Codex provider headers](https://github.com/openai/codex/blob/cec14d27b5aa1a79e9de2e21a6281d308ae1fac3/codex-rs/model-provider-info/src/lib.rs)、
[LiteLLM session header](https://github.com/BerriAI/litellm/blob/9add785f1a9c13d8ae60980610868253c86cc0df/litellm/proxy/litellm_pre_call_utils.py)、
[LiteLLM spend API](https://github.com/BerriAI/litellm/blob/9add785f1a9c13d8ae60980610868253c86cc0df/litellm/proxy/spend_tracking/spend_management_endpoints.py)。
这证明适配器的源码依据，不证明目标主机安装版本。真实网关是否具备
[请求预留与故障拒绝](https://docs.litellm.ai/docs/proxy/users#budget-reservation)、
实际模型估价和最终账单仍需现场核验；所有请求小计保持 `settlement=pending`。

## PR #89 已执行的候选验证

源码候选 `8e7190bafe562c915f009f34cddd8c874dcec405` 的检查全部成功：

| 工作流 | Python 3.8 / 3.11 / 3.12 的实际结果 |
|---|---|
| [Full Regression](https://github.com/jiying2007/codex/actions/runs/45604663762) | 各 809 项，0 failure / 0 error / 0 skip / 0 expected failure；全部成功 |
| [Runtime Binding Contract](https://github.com/jiying2007/codex/actions/runs/45604663317) | 三项成功 |
| [Profile Context Contract](https://github.com/jiying2007/codex/actions/runs/45604663285) | 三项成功 |

三份 Full Regression 日志确认实际 checkout 为合并预览
`2a9711f8535c6e870413af135e767ec8efc4e909`，父提交是上述候选和
`002ac9d160149a6fb8b9be408ec7aee022bfd4ed`。其 tree 与候选均为
`344221ca4d6a6368b659719693ecd968c27e5d8a`，因此受测源码没有偏离候选。
三个环境均完成源码 pre-apply gate、真实隔离 apply / post-apply check / no-op / rollback；
所有命令退出码为 0，no-op 内容变更为 0、原文件与链接集合恢复、保护文件不变。
这是 disposable HOME 生命周期，`live_member_installation=false`、`real_feishu_connection=false`。

首个候选 `85cd5609fb8e414fe0192c3e9b4d74969aefbc2d` 的全量回归失败，已实际修正：
发布 fixture 的 worktree 路径隔离、owner discovery 完整 JSON 断言，以及 Git replace 被
更早资格检查拒绝的异常断言。最后一项继续断言无发布意图、无远端读写，生产门禁未放宽。
独立审查发现的 SDK 同步回调阻塞和 PR 对账竞态也已修正，加入有界控制线程、失败释放
及 PR 身份漂移的回归断言。

本节记录的是上述精确候选。后续即使只改文档，也以 PR 当前 head 的新检查为合并门禁，
合并后再次核对主线工作流。主机服务切换、真实网关预算/账单与业务验收仍保持 `NOT_RUN`。
