---
name: adk-requirements-triage
description: "用于需求不清时澄清目标、范围边界和可验证验收标准；已明确的开发任务无需重复访谈，也不用于代替实际实现。"
version: 1.3.2
last_updated: 2026-11-03
triggers:
  - "需求不清楚"
  - "需求模糊"
  - "需求不明确"
  - "跨团队需求"
  - "新功能"
  - "实现新功能"
  - "目标边界"
  - "验收标准"
  - "需求梳理"
  - "帮我理清需求"
  - "边界和验收"
non_triggers:
  - 头脑风暴
  - brainstorming
  - grill me
  - gill me
  - 方案拷问
  - 挑战方案
  - 纯代码风格调整
  - 已有完整计划且只需按计划执行
  - 仅执行已有明确任务包
inputs:
  - 需求描述、上下文约束、现有代码入口
outputs:
  - 结构化需求清单、验收标准、非目标与风险清单
  - skill 路由建议（core/optional）与触发优先级
constraints:
  - 不得跳过边界与非目标声明
  - 不得省略 done-when、required evidence、artifact paths 和 blocker policy
  - 关键信息不足且无法安全假设时不得进入不可逆或高风险实现
---

# adk-requirements-triage

## Goal
- 将模糊需求收敛为可验收任务。

## Prerequisites
- 确认需求来源、owner、时间窗口和关键依赖方。
- 获取最小上下文：入口代码、现有行为、已知限制。

## 需求分类规则

| 类别 | 判定标准 | 处理方式 |
|------|---------|---------|
| 新功能 | 无现有代码对应 | 根据风险完成适用的 Workflow 步骤 |
| 增强 | 现有代码可扩展 | 重点分析影响面和兼容性 |
| 缺陷修复 | 行为偏离预期 | 先复现再定位，跳过部分规划步骤 |
| 技术债务 | 无功能变更 | 评估 ROI，低收益则推迟 |
| 配置变更 | 仅涉及配置文件 | 补迁移和回退步骤 |

## 优先级判断矩阵

| 优先级 | 业务影响 | 技术风险 | 时间紧迫度 | 处理策略 |
|--------|---------|---------|-----------|---------|
| P0-紧急 | 核心功能阻断 | 高 | 立即 | 停下手头工作，立即处理 |
| P1-重要 | 核心功能降级 | 中 | 本周 | 排入当前迭代 |
| P2-一般 | 体验优化 | 低 | 本月 | 排入下个迭代 |
| P3-低优 | 锦上添花 | 低 | 不急 | 积压，有空再做 |

## Workflow
1. **探索分流**：明确请求多轮头脑风暴或拷问时由 `adk-structured-requirements-questioning` 处理；本 Skill 只整理其已确认决策。普通模糊需求直接收敛。
2. **结构化快速扫描**：定位模块入口、现有实现、相关测试与依赖约束。
3. **识别关键疑问**：列出阻塞规划的问题，并按高/中/低优先级排序。
4. **领域建模预检**：有跨模块状态、协议、数据或生命周期风险时补齐关键术语、实体、状态、接口和边界样例；纯局部低风险变更只保留相关字段。
5. **上下文充分性检查**：区分真正阻塞的接口/安全/权限信息与可逆、低风险假设；不得重复询问已知事实。
6. **需求分类**：按分类规则判定需求类别，选择对应处理方式。
7. **优先级判定**：按矩阵评估业务影响、技术风险、时间紧迫度。
8. **触发路由判断**：输出 core/optional 技能建议、触发理由与排除理由。
9. **需求拆分策略**：仅在任务确实跨多个独立验收单元时拆包；小范围修复采用简短验收和定向验证。
10. **产出需求包**：目标、非目标、影响面、done-when、required evidence、artifact paths、blocker policy、验收标准、回退条件。
11. **明确下一步**：给出可执行任务切分与责任边界（owner/scope）。

## Discovery Template
- 嵌入式需求探索优先使用 `references/embedded-discovery-brief.md`。
- 发散与拷问由 `adk-structured-requirements-questioning` 处理，交接见 `references/exploratory-requirements-brief.md`。
- 当任务涉及芯片/板级约束、启动链、BSP、OS/runtime、驱动、组件、协议栈、设备应用、上位机/产测/诊断工具、构建调试、验证、发布、量产或现场维护时，必须先补齐目标层级、运行环境、接口边界和验证约束。
- 通用产品探索只作为辅助，不应冲淡 adk 的嵌入式全栈开发定位。

## Commands
```bash
# 扫描现有实现和依赖
rg -n "TODO|FIXME|HACK|deprecated" <target_path>
rg -n "test|spec|contract|schema" <target_path>

# 匹配相关 skill
bash scripts/devkit.sh match --skill <skill-name> --text "<需求片段>"

# 查看变更范围
git diff --name-only <base>...HEAD

# 检查依赖关系
rg -n "import|require|include|#include" <target_path> | head -20
```

## Evidence Template
```md
- Goal / Non-goal / Done-when / Required Evidence / Artifact Paths / Blocker Policy:
- 需求分类: 新功能 / 增强 / 缺陷 / 技术债务 / 配置变更
- 优先级: P0/P1/P2/P3 + 判定依据
- Impact Scope:
- Domain Model: 术语 / 实体 / 状态 / 接口 / 数据流 / 边界样例 / 反例
- Acceptance Criteria:
- 拆分策略: 模块/层次/阶段/风险
- Migration/Config Decision:
- Spec Chain Decision:
- Install Scope Decision:
- Skill Routing (core/optional + reason):
- Key Risks:
- Missing Context:
- Suggested Task Breakdown:
```

## Failure Handling
- 上下文不足时输出 `needs-fix` 并列出待补信息，不进入实现。
- 若需求混入多个无关问题，先拆分再继续。
- 优先级无法判定时，标记为 P2 并注明待确认。
- 需求分类模糊时，选择风险更高的类别处理。

## 与 adk-structured-requirements-questioning 的区别
- 本 Skill 收敛验收；对方负责 Explore / Challenge 多轮设计，完成后交接确认决策。

## Quality Gate
- 输出必须包含目标、非目标、影响面、验收标准四项。
- 输出必须包含 done-when、required evidence、artifact paths 和 blocker policy；缺任一项时结论固定为 `needs-fix`。
- 涉及状态、协议、跨模块或资源生命周期的任务必须包含适用 Domain Model；局部低风险任务标记不适用，不要求虚构字段。
- 至少给出一个关键风险及对应验证方式。
- 若缺失的是阻塞信息，结论为 `needs-fix` 并列出缺口；非阻塞细节记录可验证假设后可继续。
- 需求必须有明确分类和优先级。
- 拆分后的需求包必须各自具备独立验收标准。
