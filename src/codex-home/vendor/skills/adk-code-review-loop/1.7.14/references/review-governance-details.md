# Code Review Governance Details

按 progressive disclosure 使用：只有在严重级别存在争议、生命周期语义复杂、review 多轮不收敛、或需要向 CI/PR 发布结构化 finding 时读取本文件。日常审查先使用 `../SKILL.md` 的核心流程。

## Finding Classification

| 级别 | 定义 | 处理 |
|---|---|---|
| blocker | 会导致错误、安全问题、数据损坏或发布阻断 | 必须修复或明确接受风险 |
| major | 明显质量风险、边界遗漏、可复现回归 | 默认修复 |
| minor | 可读性、命名、局部风格或后续优化 | 可延期但需记录 |
| question | 信息不足或假设不明 | 先澄清，不直接改 |
| cannot-verify-from-diff | 需求依赖未改动代码、外部行为或运行态证据，仅凭 diff 无法判定 | 由主 Agent 或 owner 补查，不得默认为通过 |

真实性核验至少回答：问题能否由代码/运行证据支持、是否属于本次变更范围、是否需要外部 owner/运行态证据。误报必须记录反证；out-of-scope 建议不能混成 blocker/major。

## Detailed Review Workflow

1. **冻结对象与 Review Context**：按 `review-evidence-template.md` 记录目标/HEAD/index/diff/overlay、需求包、领域模型、非目标、验收/验证基线、范围及适用生命周期契约；缺失标 `question`/`cannot-verify-from-diff`，无新快照不声称复审最新修复。
2. **区分证据**：build/test/format/`diff --check` 是机械结果；需求、并发、生命周期、安全与边界需语义审查，两者互不替代。
3. **追踪行为**：从 diff 追公开入口、真实调用者及数据/状态；查正常、边界、错误、清理和取消/恢复。以代码事实为准，不以 implementer rationale 代替，不扫描无关模块凑项。
4. **核对断言**：测试须断言需求行为；遗漏给最小输入或控制流及 expected/observed。finding 含位置、条件、影响、证据、最小修复与验证；风格偏好、猜测不算缺陷。按上表核真实性与级别。
5. **双裁决**：同轮输出 spec-compliance verdict 与 quality verdict，不重复派多个局部 reviewer。
6. **设计变更**：owner、状态转换、可见性、取消、超时、恢复或迟到语义改变，标 `design-change`，停止局部补丁并回契约设计。
7. **修复交接**：每个 blocker/major 对应最小动作和验证命令，不带入无关重构。staged 修复由实施者重新 stage 后再生成快照，旧结论不覆盖新 index。
8. **整体复核**：局部通过后仍核 whole-diff/whole-branch；共享状态、异步或资源生命周期追加 whole-lifecycle-review。优先 fresh independent review，自审标 `author-self-review`；高风险交 owner 或独立 reviewer。
9. **交付**：机械/语义结论交 `adk-commit-pr-quality-gate` 或 `adk-verification-before-completion`；SCM comment 仍按下节及 `manifests/pr_review_governance_contracts.json` 校验。重复模式仅作 trace-feedback-eval-handoff/AAR 候选，不直接改 durable guidance。

## 首轮整批审查

本节的新增步骤适用于已登记试点启用组的高风险完整首轮审查。对照组、未启用试点及低风险审查沿用现行流程。大范围/高风险的现行覆盖账本规则继续适用。

- 逐仓冻结实际审查目标、HEAD、相应 index 或 diff、分支适用的 base/merge-base、影响候选的工作树叠加改动及未跟踪输入，并绑定配套版本。按目标仓的原始等级裁决，跨仓汇总前记录分级映射。深查前，从已冻结的需求与影响范围预列必查场景，在覆盖账本中登记入口或状态、预期结果和取证方式。覆盖完整差异、真实入口、直接调用方和适用的依赖、配置、正常与异常路径。优先核严重后果与关键场景，再查约定的中低等级路径。同一契约出现新线索时补查相关路径，记录范围变化。
- 首个可证实的阻断或重大问题立即在请求方可见的状态标记暂缓提交。若提交、合并临近或有人依赖旧通过结论，按已有授权及时通知。保持原候选继续检查。按计划结束、设计变更需重新规划、安全停止、预算到期、候选漂移或关键输入不可用时，冻结并交付已确认问题、已查范围及缺口，记录结束原因。
- 一次性交付范围内各级已确认发现，按严重度降序并保留项目原始等级，包括拟延期项。每条记录触发、预期、实际、影响、证据和处置。同根因取最高已证实等级并共用 finding ID，各反例保留自身场景 ID、等级和证据。零发现、待核实项、未查和范围外建议分别记录。
- 批次结束、必查覆盖和提交判断分别裁决。所有必查项有检查证据才能称必查覆盖完成。开放的阻断或重大项与关键证据待核验可并存，分别保留暂缓提交和 needs-review 的依据。有权 owner 的风险裁决只影响现行规则授权的准入范围，未查状态及其他门禁独立保留。旧结论绑定原快照，新候选逐项核对可沿用证据并做适用复审。

### 修复后发现的归因

对同一断言优先核对冻结的首轮候选与新候选、可比输入和适用要求。状态和来源分开记录，已经关闭的同一问题再次失败时记录重开。

| 观察 | 记录 |
|---|---|
| 首轮候选存在同一违约，且失败签名相符或有等价因果证据。该场景在首轮范围内，具备当时材料和权限，首轮未报告 | 首轮漏报。即使该问题后来被顺带修复，仍可用原候选的独立证据判断 |
| 首轮已披露待核实，后来拿到同一问题的确证 | 首轮已提示、后续确证 |
| 依赖后来才有的输入、需求或权限 | 首轮不可判定或范围变化 |
| 原候选对同一断言有通过证据，新候选失败 | 先定位变化区间。最小差分隔离、单变更对照或等价证据支持归因后，记录修复回归、并行变更或共同作用 |
| 快照、输入或因果证据不可比，或无法隔离变化 | 来源未定 |

在可比环境中于修复前后运行同一断言，复跑相邻异常与正常路径。后验归因逐等级和发现轮次留痕。重开和来源可以同时记录，汇总按已登记的去重口径计数。旧候选可重现的首次漏报和新回归单报。配对评测中，后验发现单列并保留冻结的首轮分母。

## Convergence Protocol

每轮至少记录：
- `review_round`
- `review_mode`
- `finding_classes`
- `new_finding_class_count`
- `reopened_finding_count`
- `consecutive_clean_reviews`
- `reviewer_independence`
- `contract_change_decision`
- `replan_reason`

Review mode 边界：
- `targeted-finding-review`：只验证已知 finding 的修复。
- `whole-diff-review`：检查完整 diff 和跨文件影响。
- `whole-lifecycle-review`：对 owner × state × event × resource × termination × invariant 做生命周期审查。

强制 `replan`：
- 连续两轮出现新的 blocker 或 major finding class。
- 任一 finding 被判定为 `design-change`。
- 同一逻辑任务的 `author-self-review` 超过两轮；此时至少执行 whole-lifecycle review，并交 owner 或 fresh independent reviewer。

`locally-clean` 只表示自审快照内无 blocker/major，不是 independent final pass。生命周期最终 pass 还要求最后快照未变化、`new_finding_class_count=0`、至少一轮适用的整体审查以及 owner/独立审查证据。

## CI and PR Publication Boundary

AI/CI review 默认只是风险扫描，写入 SCM 属于独立的发布动作：
- 自由文本不能直接转换成 comment payload；先产出 schema-backed findings。
- fork/public PR 默认不得暴露 protected secrets；缺 trusted-trigger 决策时只允许只读分析。
- inline comment 必须能验证到目标 commit/diff 的合法位置；无法锚定时降级为 summary finding。
- 发布前记录 `trusted_trigger`、`protected_secret_exposure`、`structured_output_valid`、`inline_anchor_valid`。
- 机器 comment 本身不提供最终裁决。Owner 显式委派自动审核时，独立 AI 可在授权范围内根据真实来源与证据作出最终 Spec/Quality 裁决；审核记录必须标识 AI、委派来源、独立性、实际时间和输入摘要，不能写成真人审批。

## Snapshot and Evidence Details

完整字段与取证命令只维护在 `review-evidence-template.md`，反馈/误报/out-of-scope/re-review 样例见 `review-feedback-fixtures.md`。staged 的 `MM` 必须列 unstaged overlay；重新 stage 和更新 Snapshot ID 前，结论不覆盖最新修复。

## Review Coverage Ledger（大范围/高风险按需加载）
- 在 `whole-diff-review` 或 `whole-lifecycle-review` 中从 frozen diff/requirement/impact graph 定义可审查单元（文件、接口、受影响调用者、资源生命周期、外部证据）。避免仅按文件数宣称覆盖，也不因未知范围自动猜全。
- 每个单元记录 `scope_id / source_snapshot / status=inspected|uninspected|unavailable / evidence_ref / reason / risk_owner_decision`。可复用已核验证据引用，不能把 `not found` 直接当无漏洞。
- `coverage=inspected` 只表示此单元有实际审查证据；它不是“无问题”的证明。高风险/关键依赖为 uninspected/unavailable 时必须补查或交 owner 风险决策；不得声称全覆盖。
- 低风险、单条 `feedback-triage` 用 `not-applicable`，不强行制作覆盖账本；新代码或修复导致影响范围变化需更新快照与账本。

## Security / High-Risk Patch Variant Validation（有补丁时才适用）
- 锁定 vulnerable base 与 patched HEAD，先重跑已知原始失败/利用路径，在有授权且隔离的环境中确认 baseline failed → patched fixed；没有真实运行权限时只做 source 证据并标 `not-tested`。
- 查验**相同根因**的相邻入口、解析路径、异常分支、权限/竞争状态及环境差异，保存检验过和未检验的变体，不因原 PoC 消失就认为漏洞完全消除。
- 验证合法输入与兼容性未退化、原保护边界没有被放宽、是否引入新的安全失败；最小可复现负例关联 `scope_id`，不为凑数量生成无关变体。
- 目标受控仓库代码、测试、脚本仅在明确授权和隔离条件下运行；不能执行不可信补丁脚本、远端/生产设备验证来代替审批。
- 输出 `vulnerable_ref / patched_ref / original_repro / related_variants / legitimate_behavior / new_risks / runtime_evidence_or_not-tested / owner`。

## Spec-to-Code 双向一致性（完整范围且有需求/规格变更时）
- 先冻结当前生效规格、原需求 ID、目标实现 SHA、真实调用者与模块/协议边界。只选实际受影响范围；单条 `feedback-triage` 不启动全量规格审计。
- **spec → code**：逐条将要求映射到代码路径/符号、验证用例和观察证据；基础状态 `verified / contradicted / absent / not-checked`；细分 `implemented / partial / stronger-than-spec / undecidable`，其中 partial 需列失效路径、stronger-than-spec 需找未声明约束、undecidable 是规格不能测试。若声称 absent，必须有 `searched_scope`、符号/别名/调用链及排除记录；搜索不足只能 not-checked。README、grep 命中或覆盖率不能代替语义证明。
- **code → spec**：检查本次变更引入的可观察状态/错误码/权限/超时/副作用；标 `documented / undocumented / not-checked`，其中 undocumented 不一定是漏洞，但需判断意图、风险、兼容与需求变更授权。
- 账本必须显式保留 `required_scope / inspected_scope / omitted_scope / evidence_ref / risk_owner_decision`，无界/不可获取范围标 `not-checked`，不可推断“已审查 100% = 缺陷发现 100%”。
- 高风险关键要求 contradicted/absent/not-checked，或未经授权的未声明副作用，不得给 spec-compliance pass；先补证据、回设计/owner 决策。完整验证与缺陷发现率/误报率须分开呈现。
