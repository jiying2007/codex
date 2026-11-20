---
name: adk-test-strategy
description: "用于跨模块测试策略、独立期望值、检查器校准、风险与行为覆盖；不用于只生成嵌入式局部替身代码或代替真实执行结果。"
version: 2.2.3
last_updated: 2026-11-20
triggers:
  - "测试策略"
  - "TDD"
  - "先写测试"
  - "补测试"
  - "回归测试"
  - "测试矩阵"
  - "验证策略"
  - "独立断言"
  - "检查器校准"
non_triggers:
  - 纯文档修改且无行为变化
  - 已有完整测试计划且只需执行命令
inputs:
  - 需求类型、行为变化、技术栈、现有测试入口、风险等级
outputs:
  - 测试级别、TDD 决策、测试矩阵、验证命令与证据要求
constraints:
  - 行为变化必须给出测试或明确说明不可测试原因
  - 高风险变更不得只依赖手工检查
  - 没有红灯证据不得声称完成 TDD
---

# adk-test-strategy

## Goal
按风险选择**最少但足够证明行为**的验证，复用已有测试入口；模板、全量执行或模拟结果本身不证明质量。

## Test levels
- **Level 0**：纯文字、局部非行为变更，用目标文档/格式检查；不强制完整测试矩阵或 TDD。
- **Level 1**：bugfix、脚本或局部行为改变；最小重现或回归例 + 定向测试。
- **Level 2**：新关键行为、共享逻辑、公共接口、高风险修复；真正 RED → GREEN → REFACTOR，并复跑受影响回归。红灯必须因目标行为失败而非环境错误。
- 仅高风险、跨层或无可靠单测替代时升级 SIL/HIL/provider/现场验证；缺环境标 `not-tested`，不得伪造通过。

## Workflow
1. 识别目标行为、受影响接口/数据/安全边界，读取现有 `pytest/ctest/go test/cargo test` 或项目特定入口；不创建平行测试框架。
2. 选择 Level 0/1/2 和最小反例。Level 0 不产出大量空表；Level 1/2 才列出必要 happy/boundary/failure/negative cases。
3. 本 Skill 只读，写测试/修复交已授权实现职责。Level 2 在公开 seam 执行红灯、修复、绿灯和重构；新增/可疑测试用独立 expected 拒绝明确错误变体，新建/修改/可疑 checker 校准阈值与失败路径，按需读 `references/high-value-tdd.md`。不以 mock 次数冒充行为。
4. **并行测试时**必须给 `Validation Resource Matrix:`，检查 output directory、binary/cache、port/device 是否隔离；有共享写入则串行，避免并发造成随机失败。
5. 对 Agent/prompt 更改固定输入任务、grader 和版本身份，比较逐例退化；模拟 router/handoff 成功不代表真实 provider、runtime 或设备副作用已验证。
6. 高风险安全补丁按需复核原始失败路径、同根因变体、合法行为保留和新引入风险；仅在授权隔离环境运行目标代码/样例，否则标 `not-tested`，不把 source 断言冒充 runtime 修复证明。
7. 从执行回执记录 `Evidence Index`（命令、退出码、版本、摘要/raw pointer）与未测试边界；缺回执标 `not-tested`。补测限受影响范围，不无条件扩大到昂贵全量套件。
8. 最终结论交 `adk-verification-before-completion`；失败两轮无信息增量先进入 `adk-systematic-debugging`，不重复盲跑。

## Quality Gate
- 行为变化有可复现断言或写明无法验证原因；Level 2 的 red/green 证据真实且原因正确。
- 共享接口须核回归范围；高风险不可只依赖格式或模拟检查；并行测试必须验证资源隔离。
- 不得用覆盖率、空矩阵或“已执行”自述代替测试证据，未运行就标 `not-tested`。
