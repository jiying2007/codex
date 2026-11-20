# Verification Governance Details

按需细读；权限与阶段边界见 `../SKILL.md`，填写模板不授予权限。

## Applicability Matrix

| 影响面 | 对应下方步骤 |
|---|---|
| 主观/UI | 3、12 |
| 状态/异步/共享资源 | 5、6 |
| 目录/配置/runner/CLI/adapter/noninteractive/source-to-live | 7、8、13 |
| prompt/policy/guidance/routing/completion gate/model/context | 9、17、19，或真实不适用原因 |
| slash/MCP/hook/permission/approval/sandbox | 18 |
| medium/high、协议/数据/安全/发布 | 11、14、24及适用迁移/回退、运行环境 |
| 跨模块/协议/数据/发布/存储/资源/UI | 15 |
| breaking change | 16 |
| 新建/修改/可疑 checker | 下方条件性校准 |

## Detailed 25-Step Verification Flow

1. 冻结 scope/mode/risk、快照、原验收、影响面和非目标。
2. claimant 自述/源码推断不替代独立 verifier 的实际证据。
3. 核 lint/test/build/smoke 环境；主观功能补 Subjective Feature Proof。
4. 核 blocker/major/minor 闭环，不带重大问题通过。
5. 生命周期核入口列出的契约、取消/超时/恢复/迟到及 generation，明确真实边界。
6. 核 review mode、finding class、reopen、clean-review、independence；局部修复不等于整体。
7. 运行目录核 tool target 适配和健康。
8. 配置声明对照实际加载。
9. prompt/policy 补前后行为及失败样例，未测量明确说明。
10. Evidence Index 记命令、退出码、时间/版本、原始路径/层级/工件；过期重验，至少一条负结果/被证伪路径。
11. 按矩阵补回放输入/环境/hash/敏感信息复核；不能回放须说明替代证据。
12. UI 核可见状态、权限与敏感内容；源码不能代替运行。
13. runner 核 JSONL、执行身份、续接、失败/取消；字段见模板。
14. 核 required artifacts、primary/supporting/skipped skills 与 fallback evidence。
15. 跨界核 standards/architecture/ship disclosure/canonical resolution parity，或明确不适用。
16. 显式 breaking decision、migration、rollback。
17. 能力扩展核本地回归和权限未放宽。
18. 控制面核允许/拒绝、实际加载/配置和回退。
19. Trace Eval 可回溯，字段见模板；source-only 不当模型效果。
20. 反查每个结论的证据，不先定结论。
21. 长任务核 retry/heartbeat/staleness、plan completeness、attestation readback、失败/排除项；失配先恢复。
22. 仅适用的 goal-final/晋级填 Codify；checkpoint 可延期。
23. 后续摩擦下降、owner、回退及验证齐全才允许 `promotion_candidate: true`；一次性/仅当前环境 workaround 不晋升。
24. 按矩阵对适用 build/lint/test/smoke/security/release 记录 status/exit_code/command/evidence_path/verified_at/verifier。
25. 给 pass/needs-fix、未查范围、open items、风险/下一步/owner；必需项失败/过期/无有效跳过理由均 needs-fix。

## Checker 校准：区分执行成功与业务通过

仅新建/修改/结果矛盾时固定版本、命令链、schema/阈值/范围和输入身份，运行下表对照并记 expected/observed/raw pointer。同配置的有效证据可复用，变化后重校准。exit 0 仅可能表示生成报告；未知/缺失/执行或覆盖错误不得通过，一律拒绝也不正确。

将三段分别存为临时 `checker.py`、`scanner.py`、`report.json`，运行 `python3 checker.py error python3 scanner.py report.json 0`。scanner 仅回显受控报告，不能证明真实扫描能力；这不是生产 Gate。下表逐例修改报告，直接运行 scanner 均可 exit 0，包装器须拒绝违规/错误；阈值改 `warning` 后 warning 也须拒绝。

<!-- adk-example: checker-calibration -->
```python
import json
import subprocess
import sys

levels = {"info": 0, "warning": 1, "error": 2}
threshold, command = sys.argv[1], sys.argv[2:]
verdict, scanner_exit = 2, None
try:
    run = subprocess.run(command, capture_output=True, text=True)
    scanner_exit = run.returncode
    report = json.loads(run.stdout)
    valid = (
        run.returncode == 0 and threshold in levels
        and isinstance(report, dict) and type(report.get("schema")) is int and report["schema"] == 1
        and report.get("complete") is True and report.get("errors") == []
        and isinstance(report.get("scanned"), list)
        and all(isinstance(path, str) for path in report["scanned"])
        and set(report["scanned"]) == {"a.py", "b.py"}
        and isinstance(report.get("findings"), list)
        and all(isinstance(level, str) and level in levels for level in report["findings"])
    )
    if valid:
        verdict = int(any(levels[level] >= levels[threshold] for level in report["findings"]))
except (OSError, ValueError, TypeError):
    pass
print(json.dumps({"scanner_exit": scanner_exit, "verdict": verdict}))
raise SystemExit(verdict)
```

<!-- adk-example: checker-scanner -->
```python
from pathlib import Path
import sys
print(Path(sys.argv[1]).read_text())
raise SystemExit(int(sys.argv[2]))
```

<!-- adk-example: checker-clean-report -->
```json
{"schema":1,"complete":true,"errors":[],"scanned":["a.py","b.py"],"findings":[]}
```

| 从正常报告改一项 | error 阈值预期 |
|---|---|
| 不改 / findings=["warning"] | 0 / 0，保留合法通过 |
| findings=["error"] | 1，达到阈值 |
| errors 非空 / scanner 最后参数改 3 | 2，报告错误/进程失败 |
| complete=false / 删除 findings / scanned=[] 或仅 a.py | 2，覆盖或 schema 不完整 |
| findings=["unknown"] / 非 JSON | 2，不猜未知结果 |

findings 在此仅存级别。真实工具按实际 schema、范围和超时/取消合同适配，保存原报告后再判定，不能据此认证现场覆盖。

## Claim、证据与权限

按新增/修改/删除/重命名追溯原需求和当前行为；删除核旧行为消失，重命名不重造功能。未运行标 skipped/not-tested，不计通过；缺现场证据须说明 fallback 和 owner 接受的替代边界。not_applicable 不能掩盖缺口。design-change、新 blocker/major finding class 或超自审预算须 replan。

### Completion Guard 静态覆盖审计

源仓 `python3 -m agent_dev_kit.completion_coverage --input <completion-coverage.json> --summary-json` 核封闭字段、同源快照、退出码/新鲜度；输入见 `tests/fixtures/completion_coverage_valid.json`。必需项缺失/跳过/失败/过期 → needs-fix；畸形 → invalid。`status=pass` 仅自报结构和集合覆盖，`completion_allowed=false` 始终成立；命令、证据 ref、verifier、目标环境仍需独立核对。

## Full Evidence Template (goal-final or medium/high only)

```md
- Scope Summary / Completion Claim Audit / Verification Command Results:
- Runtime Config Audit / Prompt Regression Evidence / Model / Context Regression Evidence:
- Runtime Control Plane Audit: slash_command_runtime_audit / mcp_runtime_contract / permission_profile_decision / loaded_tools / approval_boundary / deny_path_test / runtime_config_diff / rollback_path
- Trace Eval Regression Evidence: trace_eval_regression_case / dataset_id / case_id / source_trace_id / prompt_version / candidate_prompt_version / expected_regression_signal / grader / score_threshold / regression_link / retention_policy / redaction_status / owner_approval / not_applicable_reason
- Standards / Architecture / Ship Disclosure / Resolution Parity / Browser Evidence:
- Evidence Index: command / exit code / summary / path / layer / artifact
- Replayable Evidence Bundle: source_snapshot / input_snapshot / environment_snapshot / tool_transcript / tool_transcript_digest / artifact_hashes / expected_assertions / sensitive_data_review / non_replayable_reason
- Appshots / UI Evidence Boundary: visible_text_boundary / permission_scope / sensitive_content_review / runtime_evidence_or_not_applicable
- Runner Smoke Contract: event_stream_schema / sandbox_approval_cwd / thread_turn_or_resume_reply / failure_cancel_path
- Tool / Skill Evidence Plan: primary_skill / supporting_skills / required_artifacts / skipped skills / tool_fallback / fallback_evidence / evidence_paths
- Codify Decision: 按 ../SKILL.md 的适用条件、权威模板和完整字段填写。
- Completion Guard Payload: required_checks / passed_checks / failed_checks / skipped_with_reason / stale_checks / verifier / completion_allowed
- Lifecycle Operation Evidence: not_applicable_reason | contract / owner / state-events / termination / runtime-evidence
- Review Convergence Evidence: review_round / review_mode / finding_classes / new_finding_class_count / reopened_finding_count / consecutive_clean_reviews / contract_change_decision / replan_reason / reviewer_independence
- Subjective Feature Proof: feature / independent_verifier / expected / observed / evidence / verdict
- Review Status (B/M/m) / Breaking Change Decision / Risk + Rollback / Final Gate Result:
```
