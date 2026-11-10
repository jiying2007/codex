# Skill 行为回归：基线—候选—压力测试

此方法不规定某个模型供应商，也不自动调用 Codex/Work/付费 API。

1. **问题与基线**：给出一个真实任务失败，附脱敏原始 trace（缺哪条事实、错误推断、反复提问、误触发、越权或交付错误）；冻结模型/运行时、权限、工具、检索上下文、预算和任务集。
2. **RED**：不加载目标 Skill 跑场景，观察原始失败；若已发生过且证据可信可复用。没有模型调用渠道或记录时只标 `not-measured`。
3. **GREEN**：加载候选 Skill、其余不变，重跑相同场景；记录结果是否修正和原已成功场景是否退化。交互式场景保留每轮用户回复/依赖决策 frontier。
4. **压力边界**：至少包括 positive、near-miss、相邻 Skill 冲突、用户否定/退出、诱导跳过验证、失败后恢复；不同能力选择相关项而非强加模板。
5. **盲评**：对关键用户可见效果，两位不共用生成上下文的审查者按预注册 rubric 打分；包含安全/授权硬失败，不允许被平均分抵消。
6. **成本**：先判不低于现行质量，再比较实际输入/输出 Token、工具次数与耗时；不可用静态字节/估算 token 替代实测。
7. **资格边界**：E0/E1 的 source-test 可自动通过；E2 对话/行为、E3 native host、E4 任务轨迹未执行则始终 `not-measured`。附确切 trace 与来源 SHA，不伪造已通过认证。

汇报最小字段：`candidate_sha / baseline_sha / model_runtime / scenario_id / raw_trace_ref / judge / behavior_verdict / permission_verdict / tokens / tool_calls / unresolved`。
