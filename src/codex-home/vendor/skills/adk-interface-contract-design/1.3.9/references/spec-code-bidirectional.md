# Spec-to-Code 双向可观察行为验证（按需）

只用于已有实现/接口迁移/规格符合性审查。设计尚未落代码时报告 `not-applicable` 或 `proposed`；不凭模拟示例给 `verified`。

## 两个方向均需保留
1. **spec → code**：冻结现行 `spec_ref@digest`、`requirement_id`、条件/否定语义和验收指标。追踪实际受影响调用链 `implementation_path:symbol@sha`、相关测试、运行记录。保留最小状态 `verified / contradicted / absent / not-checked`；有证据时细分为 `implemented / partial / stronger-than-spec / undecidable`。`partial` 须指出未满足的路径，`stronger-than-spec` 指实现额外约束，`undecidable` 是规格表述不可检验；单纯 grep 命中只证明名称存在。判定 `absent` 前必须记录 `searched_scope`、不同语义检索词、调用者/包装层及排除理由；未搜索充分只能是 `not-checked`。
2. **code → spec**：从受影响实现或行为 diff 逆查可观察接口行为（状态转换、默认值、错误码、回调、超时、重试、权限、持久化、升级/回滚、资源副作用）；标 `documented / undocumented / not-checked`，对 `undocumented` 先判断兼容影响和 owner 决策，不能直接当漏洞。
3. **双向边界**：记录 `required_scope / inspected_scope / omitted_scope / evidence_ref / unknown_reason / risk_owner_decision`；没有授权访问的目标或真实板端测试标 `not-tested`。验证覆盖单元数 ≠ 缺陷发现率、误报率或运行效果。
4. **处理**：关键 `contradicted/absent` 停止实现/发布，进入需求和接口决策；关键 `not-checked` 需补查或由实际 owner 记录风险决策；不靠模板平均分放行。

最小输出：

```md
- Source: spec_ref@digest / implementation_sha / target
- Forward: requirement_id / implementation_path:symbol / test_or_trace / status
- Reverse: observable_behavior / matching_spec_ref / status / compatibility_risk
- Scope: inspected / omitted / unknown / owner_decision
- Verdict: pass | needs-fix | not-tested
```

本文件是现有 `adk-interface-contract-design` 的可选 reference，不构成额外独立 Skill、自动审计器或现场设备操作授权。
