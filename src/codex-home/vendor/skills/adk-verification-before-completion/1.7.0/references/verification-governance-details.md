# Verification Governance Details

按 progressive disclosure 使用：日常完成前核验先读 `../SKILL.md`；只有命中对应风险面、证据字段需要解释、或 gate 失败需要追溯规则时再读本文件。

## Applicability Matrix

| 变更类型 | 必补证据 |
|---|---|
| 主观/用户可见功能 | Subjective Feature Proof，独立 verifier，expected/observed/verdict |
| 状态、异步完成、共享资源 | owner/state/event/resource/termination/invariant，取消/超时/恢复/迟到完成，generation 隔离，真实环境边界 |
| 运行时目录 | 显式 tool target 适配证据 + 运行目录健康验证 |
| 运行时配置 | 声明配置 vs 运行态加载 |
| prompt/policy/guidance/routing/completion gate | before/after 行为证据 + Trace Eval Regression Evidence 或 not_applicable_reason |
| runner/CLI/adapter/noninteractive/source-to-live | Runner Smoke Contract |
| UI / 浏览器可见行为 | UI/Appshots Evidence Boundary + browser/runtime evidence |
| slash command/MCP/tool server/hook/permission/approval/sandbox | Runtime Control Plane Audit + deny path + rollback |
| 模型/上下文/工具能力 | 本地回归 + approval/deny 未放宽证据 |
| 中高风险交付 | Replayable Evidence Bundle + Tool/Skill Evidence Plan + Completion Guard Payload |
| 跨模块/协议/数据/发布/存储/资源/UI | standards impact + architecture review + ship disclosure + canonical resolution parity 或明确 not-applicable |
| breaking change | breaking decision + migration + rollback |

## Detailed 25-Step Verification Flow

1. 收敛改动范围，明确影响面与非目标。
2. 分离 claimant 的完成声明与 verifier 的独立核验，不采信结论文本本身。
3. 核对 lint/test/build/smoke、执行环境；主观/用户可见行为需独立 Subjective Feature Proof。
4. 按 blocker/major/minor 检查评审闭环。
5. 若涉及生命周期操作，检查 owner/state/event/resource/termination/invariant、取消/超时/恢复/迟到完成、generation 隔离与真实环境边界。
6. 检查 review mode、finding class、reopen、clean-review、independence 与 replan；targeted finding 修复不能冒充整体生命周期通过。
7. 运行时目录补 tool target 适配和健康验证。
8. 运行时配置补声明配置与实际加载对比。
9. prompt/policy 文本补 before/after 行为对比与失败样例。
10. 关键命令进入 Evidence Index，记录命令、退出码、摘要、证据路径、层级和关联工件。
11. 中高风险交付补 Replayable Evidence Bundle：input/environment snapshot、tool transcript digest、artifact hashes、expected assertions、sensitive-data review、不可回放原因。
12. UI/用户可见行为补 Appshots/UI Evidence Boundary：可见窗口/文本、permission scope、sensitive-content review；源码检查不能替代 runtime UI 证据。
13. runner/CLI/adapter/noninteractive/运行资产链路补 Runner Smoke Contract：schema/JSONL、sandbox、approval、cwd、thread/turn、resume/reply、失败/取消路径。
14. 核对 Tool / Skill Evidence Plan：primary/supporting skills、required artifacts、skipped skills、tool fallback、fallback evidence、evidence paths。
15. 跨模块/协议/数据/发布/存储/资源/UI 变更补 standards impact、architecture review、ship disclosure、canonical resolution parity、browser evidence 或 not-applicable。
16. 显式判断 breaking change，并给 migration/rollback。
17. 模型切换、上下文扩容、工具能力提升补本地回归和权限/approval 未放宽证据。
18. Runtime Control Plane Audit：slash command、MCP/tool server、hook、permission profile、approval policy、sandbox 变更记录 `slash_command_runtime_audit`、`mcp_runtime_contract`、`permission_profile_decision`、`loaded_tools`、`approval_boundary`、`deny_path_test`、`runtime_config_diff`、`rollback_path`。
19. Trace Eval Regression Evidence：prompt/policy/routing/completion gate/guidance 变更记录 `trace_eval_regression_case` 或 `not_applicable_reason`；候选包括 dataset_id、case_id、source_trace_id、prompt_version、candidate_prompt_version、expected_regression_signal、grader、score_threshold、regression_link、retention_policy、redaction_status、owner_approval。
20. 反向核验每个结论是否真的被证据支持，禁止先结论后补证据。
21. 长任务核 retry budget、heartbeat、staleness threshold、plan completeness、attestation readback、失败路径、已排除方案与 open items。
22. 使用 `templates/governance/codify-decision.md` 完成 Codify Decision：delivery_goal、reusable_pattern、affected_asset、promotion_candidate、next_task_friction_reduced、reduced_by、reduction_evidence、do_not_promote_reason、owner_review、rollback_path、verification_evidence。
23. 只有 verification_evidence、owner_review、rollback_path 和摩擦下降证据完整时才允许 `promotion_candidate: true`；否则写 do_not_promote_reason。
24. 中高风险任务生成 Completion Guard Payload；对 build/lint/test/smoke/security/release 中适用项记录 status、exit_code、command、evidence_path、verified_at、verifier。
25. 输出 pass/needs-fix、剩余风险、下一步和责任人。

## Gate Details

### Completion claim
完成声明至少区分 claimant、verifier、证据、缺失证据、open items。主观或用户可见行为还要区分 expected、observed、verdict。claimant 自述、源码推断或“看起来没问题”均不能替代独立验证。

### Evidence freshness and replay
关键命令必须可追溯；过期证据不能复用。Evidence Index 至少保留一条负结果或被证伪路径，避免只收集支持结论的样本。中高风险任务应可回放；不可回放必须写明原因和替代证据。

### Lifecycle and review convergence
受控生命周期操作必须有契约、owner 结论、终止路径和所需真实环境边界。生命周期变更必须有适用的 whole-lifecycle review。出现 `design-change`、新增 blocker/major finding class、或超过自审轮次预算时必须 replan。

### Tool and skill evidence
required artifact 缺失、skipped skill 无原因、tool fallback 无 fallback evidence，均固定 `needs-fix`。工具不可用时应记录 fallback，而不是把“未执行”写成通过。

### Runtime control
权限、approval 或 sandbox 变更必须同时证明 allow/deny 边界；缺 `deny_path_test`、`loaded_tools`、`rollback_path` 时不得完成。不得因为本地 happy path 成功就推断生产权限边界安全。

### Codify
可复用模式提升为 durable guidance 前必须证明后续摩擦确实下降，并保留 owner review、rollback 和 verification evidence。一次性 workaround、只在当前环境成立的技巧、或没有回退面的做法不应 promotion。

## Rationalization Intercepts

| 借口 | 风险 | 正确做法 |
|---|---|---|
| “我验证过了” | 口头验证不可复现、不可审计 | 写 Evidence Index，保留命令/退出码/结果摘要/证据路径 |
| “跑了一遍应该没问题” | “应该”不是证据；一次 happy path 不等于门禁闭环 | 可复跑验证，并保留至少一条负结果/被证伪路径 |
| “改动很小不用全量看” | 改动大小与影响面不等价 | 按 applicability matrix 只跑相关但足够的验证，不跳过必需证据 |
| “源码看起来 UI 会这样” | source-only inspection 不是用户可见 runtime evidence | 补 Appshots/UI/浏览器或真实运行证据 |
| “AI reviewer 没报错” | reviewer 不是 verifier，且可能缺运行态上下文 | 独立执行完成门禁并记录证据 |
| “测试绿了就能发” | 测试无法自动覆盖 migration、rollback、权限、运行态配置和发布披露 | 同时核兼容性、控制面和 ship disclosure |

## Failure Triage

- 关键命令无法执行：记录原因、fallback 和降低后的完成度，不伪造 pass。
- 证据过期：重新验证，而不是复用旧绿灯。
- blocker 未闭环：固定 `needs-fix`。
- heartbeat/staleness/retry budget 失败：先恢复长任务一致性，再讨论完成。
- 运行态证据不可获取：明确 not_applicable 或 owner 接受的替代证据边界；不得默认为通过。
