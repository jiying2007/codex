# Pilot Measurement Evidence

仅用于 Agent/自动化效率试点；不替代设备、产测、OTA、回滚和维护门禁。

## 必需证据

1. 任务预注册：记录 task family、纳入标准、计划任务数和冻结时间。
2. 任务处置：记录 accepted/rejected 数量和拒绝原因分类；不得只选择适合 Agent 的任务。
3. 人类基线：使用实测或有来源的历史校准估时，记录样本数和方法。
4. 时间分离：wall-clock=经过时间；human-active=人员活跃区间并集；多人另记 person-minutes 合计人时，与基线同口径比较；agent-active=各 Agent 活跃时长之和。
5. 并发归一化：记录 concurrent-agent peak 和重叠区间，禁止把并行 Agent 总时间直接当 wall-clock。
6. 结果证据：测试、diff、review、回滚和失败案例必须能回到原始工件。
7. 独立复核：reviewer 记录选择偏差、时间测量方法和置信区间是否充分。

## 一致性规则

- `accepted + rejected == preregistered`。
- workload task count 必须等于 accepted task count。
- human baseline task count 必须覆盖 workload task count。
- `human_active_minutes <= wall_clock_minutes`。
- `agent_active_minutes <= wall_clock_minutes * concurrent_agent_peak`。
- 自报“完成”、AI 代码占比、Token 总量和 PR 数量不能单独作为生产率或质量结论。

## 最小模板

```md
- Preregistered / Accepted / Rejected:
- Rejection Reason Log:
- Human Baseline Method / Tasks / Minutes:
- Wall-clock / Human-active / Agent-active Minutes:
- Human Person-minutes / Participants / Overlap (multi-person only):
- Concurrent Agent Peak / Overlap:
- Functional / Safety / Review Evidence:
- Selection Bias Assessment:
- Time Measurement Assessment:
- Confidence Interval / Limitations:
```

字段缺失时，试点最多为 `needs-fix`；不得据此声称生产率提升或现场 ready。
