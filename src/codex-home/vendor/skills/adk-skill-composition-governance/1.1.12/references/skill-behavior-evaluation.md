# Skill 行为回归：基线—候选—压力测试

此方法不规定某个模型供应商，也不自动调用 Codex/Work/付费 API。

本页评测证据 E0/E1（静态）、E2（行为）、E3（原生宿主）、E4（端到端）与执行投入 `execution_effort` E0–E3 不同，不能按编号互相晋级或授权。真实层未执行仍为 `not-measured`。

1. **比较对象**：常规改版使用现行 Skill（champion/baseline）与 candidate；首次证明价值或调查负收益时另加 no-skill。冻结 `baseline_sha / candidate_sha / model_runtime / tool_permissions / budget / grader_id / dataset_sha`，不能每轮用无 Skill 取代现行版本。
2. **开发、选型、验收**：预注册开发 `train_case_ids`、选型用例和独立 `holdout_case_ids`，最终留出集不与前两者重叠。只用开发/验证结果选候选，冻结后按预注册重复次数验收；不得根据 holdout 调参。作者已看过的案例只作开发用途。样本按影响与适用 campaign 门槛确定，2–3 个探索例不能证明资格；不为小改自动运行全资产 campaign。
3. **RED → GREEN**：保存真实失败的脱敏 trace；可信旧失败可复用，假设例标 `design-case`。只修改一个机制，其余条件不变，验证失败是否修正、旧成功是否退化；缺运行渠道或记录时标 `not-measured`，不编造 RED。交互任务保留每轮回复与决策 frontier。
4. **压力边界**：按能力覆盖 positive、near-miss、相邻 Skill 冲突、用户否定/退出、已批准任务快路径、诱导跳过验证、失败恢复。
5. **盲评**：关键用户可见效果仍由两位不共用生成上下文的审查者按冻结 rubric 评价；权限越界为 hard fail，不能被平均分抵消。
6. **成本与停止**：先判质量/安全不退化，再比较实际输入/输出/缓存 Token、工具调用、耗时与返工；静态字节不代表节省。预算耗尽或重复尝试没有新证据时停止，保留负结果和恢复条件，不用巡检代替实验。

汇报最小字段：`candidate_sha / baseline_sha / model_runtime / scenario_id / raw_trace_ref / judge / behavior_verdict / permission_verdict / tokens / tool_calls / unresolved`。
方法结论按“问题与证据、方法机制、适用与不适用条件、资产归属、来源与取舍、验证与效果、维护与退出”写入已有 change/effect 记录；引用固定来源版本/文件或文档摘要与日期，不新增 schema、状态台账或必填空模板。

## Case isolation / observation boundary（需要真实评测时）

- 复用已有 `effect_trials`，按固定案例在 baseline/candidate 间恢复**相同初始 workspace、输入、工具权限和缓存条件**；工作树输出只能证明最终状态，不足以证明中途未越权读写或未外传。
- 记录 `initial_workspace_ref / observed_tool_calls / final_artifact_ref / forbidden_side_effects / missing_observability`，真实 trace 可验证时才判实际行为；模拟 CLI/静态回放/离线 matcher 只给 E0/E1，不能伪造 native load、独立评价或任务完成率。
- 真实宿主不可用时保留预注册和用例，明确 `not-measured`，**不因未测而运行收费模型、触发新定时任务或削弱安全 guardrail**。

## Skill Value / Harm Gate（首次价值或负收益调查）

- 只对确有真实运行证据的任务比较 `no-skill vs selected-skill`，固定 `target_repo@commit`、需求与可执行 verifier、model/runtime、工具授权、时间窗和初始 workspace。区分正确性、实际 Skill 调用、耗时/Token、越权或负面副作用；不能用通用问答或纯模板得分代表真实工程成功。
- 特别检验三类负收益：`wrong-version`（Skill 的 API/框架版本落后于目标仓）、`explicit-instruction-conflict`（模板覆盖用户的明确非目标/验收）、`irrelevant-trigger`（无关任务仍加载）。记录原有成功任务的退化而不仅是新任务绿灯。
- 分类 `beneficial / neutral / harmful / inconclusive` 必须有任务级成对结果与原始 verifier/trace；样本不足、未成对、审查不独立或环境漂移时为 `inconclusive / not-measured`。单次成功不批准长期默认启用；确认有害或冗余后进入既有 owner 退役审查，保留替代、消费者影响和回滚证据，不自动删除。
- 这项检查沿用 ADK `effect_trials`，不导入 SWE-Skills-Bench 任务/模型执行器，不用 Skill 自己评价自己。没有明确性能增益也不能因此跳过安全/权限门禁。

## Outcome-first and overhead attribution（真实轨迹适用）

- **先判最终结果**：按原用户需求、目标仓版本、可执行验收与真实工件状态判 correctness/completion；工具序列可以有多个合法路径，不强迫与参考轨迹逐步一致。随后再判 tool selection、arguments、必要性和时间/Token；权限越界、伪造证据及违反硬合同仍是独立 hard fail。
- **防止不公平 grader**：no-skill 基线不可能读取候选 Skill 的 `SKILL.md`，不得以“必须阅读目标 Skill”作为两组共同成功条件。用可行的 reference solution 和 negative control 先核验评测设定。真实任务没有明确路径约束时，换用同样安全且得到正确结果的命令不应被误判失败。
- **归因而非猜因**：仅对同任务、同模型/工具权限、相同初始仓快照的成对原始轨迹做 `functional / efficiency / instrumentation` 分类。遗漏需求、错误版本是假设性的功能归因候选；额外全量验证、沉重实施流程、重复工具调用是效率归因候选。需在轨迹和最终产物中找到可证差异；仅凭长 Skill 文件、失败结果或单次分数不能认定 Skill 导致。
- **有效任务失败（task-timeout）**：agent 在预注册的任务时间/执行预算内未完成，包括慢执行、挂死或重试耗尽，计为有效 task failure 并保留在任务分母中；不得因为候选较慢而删除失败样本或只重试候选。保留截止时产物、工具轨迹和已消耗用量。
- **评测不完整（infrastructure-timeout）**：仅基础设施/采集链路超时、缺一侧、环境漂移或 grader 自身不公平时标 `invalid-eval / INCOMPLETE`，保留全组与原始失败记录并修复评测条件；按预注册规则成对重跑，不选择性重试或事后剔除不利样本。不把缺失分数填成 0，也不将部分结果平均为 Skill Lift。无法区分超时来源时保持原因未明，不直接认定为基础设施失败。守住必须的安全/合规/发布验证，但低风险阶段不强制执行不相关的完整 Goal 流程。

## Targeted ablations（仅在真实 Skill Lift 难以归因时）

- 需要消融时保持 `no-skill / champion / challenger` 试验身份分离；固定任务输入、初始 workspace、Skill 曝露和 grader，不把“Skill 命中”计作成功。外部方法来源用已有采纳记录的确切版本/文件，不以移动主页充当试验身份。
- 当结果反常或 Token 开销明显增加、需要判断是**内容误导**还是**上下文长度干扰**时，可附加一个相同长度、同信任边界、与任务无关的**中性文本控制组**；它不得包含操作指令、真实凭证或扩大的工具权限。该条件单独预注册、隔离、统计，不混入原成对试验的样本/显著性结论；记录 `length_control_status: measured | not-measured`。
- **小步改动 / 拒绝变更记录**：每次只修改一个可证伪失败模式，保留旧正确路径、否决理由与回滚点；候选通过独立未曝光验收且安全不退化才建议晋级。采纳某方法不代表运行了其上游工具或取得真实效果。

## Evidence Contract
- 真实 source/宿主权限缺失则中止并记 `not-measured`；未报告的用量记 unavailable，不填零。
- 优化与 holdout 的 ID 重叠或环境漂移时标 `invalid-eval`，冻结原始 trace，不以静态 router pass 代替行为结论。
- 复用既有 `agent_dev_kit.effect_trials.compare_effect_trial_file`、Run Evidence、Trace Summary；不自动运行付费模型，不创建平行评测引擎。
