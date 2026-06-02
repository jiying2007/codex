---
name: adk-skill-deep-analysis
description: 从产品视角深度拆解 AI Skill 的设计意图、独特解法和可借鉴模式
version: 1.0.0
last_updated: 2026-05-16
triggers:
  - 深度拆解 skill
  - 分析 skill 设计
  - 提取设计模式
  - skill 产品视角分析
non_triggers:
  - 编写新 skill
  - 修改现有 skill
inputs:
  - repo_path: 目标仓库路径
  - skill_name: 可选，指定分析某个 skill
outputs:
  - deep_analysis: Skill 深度分析报告 (Markdown)
constraints:
  - 禁止直接引用 description 字段，必须从实现细节反推
  - 每个解法必须提供"通用做法 vs Skill 做法"对比
  - 5 维评分必须给出具体证据
---

## Goal

从产品视角深度拆解目标仓库中的 Skill 设计，提炼可复用的设计模式、确定性边界和吸收边界。

## Prerequisites

- 理解相关领域的基本概念
- 熟悉项目结构和工作流程
- 具备基本的文档编写能力

从产品视角深度拆解目标仓库中的 Skill 设计，提炼可复用的设计模式和最佳实践。

## Workflow

1. 扫描资源构成：`SKILL.md`、scripts、references、assets、tests、manifest。
2. 反推真实痛点：禁止只摘 description，必须从流程、脚本和失败处理推导。
3. 标注模式类型：Tool Wrapper、Generator、Reviewer、Inversion、Pipeline 或混合型。
4. 拆解确定性边界：哪些步骤由脚本/模板/schema 固化，哪些留给 LLM 判断。
5. 检查渐进式披露：frontmatter、入口正文、references/assets 是否层次清晰。
6. 评估输出契约：产物、schema、pass/needs-fix、deny-path 和复验方式是否明确。
7. 提炼可借鉴点：每项必须包含通用做法、Skill 做法、设计巧思、适用边界。
8. 给出吸收建议：ADOPT、MERGE、REJECT、ENHANCE，并说明与现有 adk 资产关系。

## 执行流程（八阶段）

### 阶段 1: 结构扫描
1. 识别资源构成：SKILL.md / scripts / references / assets
2. 判断 Skill 类型：
   - Tool Wrapper（封装 CLI/API/MCP）
   - Generator（生成代码、文档、配置或资产）
   - Reviewer（评审、打分、复验）
   - Inversion（用户给目标，Agent 接管流程）
   - Pipeline（多阶段编排）
   - 混合型
3. 统计资源规模

### 阶段 2: 真实痛点挖掘
⚠️ **禁止引用 description 字段**
1. 从脚本逻辑反推：脚本解决了什么具体问题？
2. 从 references 内容反推：哪些知识是必须外部提供的？
3. 从 triggers 反推：什么场景下用户会触发此 skill？
4. 列出 ≥3 个具体痛点，每个痛点指向证据

### 阶段 3: 工作流程可视化
1. Mermaid 时序图：用户 → Agent → 资源 → 输出
2. Mermaid 流程图：决策分支和条件判断
3. 标注关键决策点和降级路径

### 阶段 4: Scripts 拆解
1. 功能原子化程度：每个脚本是否只做一件事？
2. 场景覆盖：脚本处理了哪些边界情况？
3. 流程编排：脚本间的依赖关系
4. **「确定性」价值分析**：
   - 哪些环节用脚本固化（确定性高）
   - 哪些环节留给 LLM 即兴（灵活性高）
   - 这个权衡是否合理？
5. 检查高风险工具是否有执行前 policy、deny-path 样例和审计字段。

### 阶段 5: References 拆解
1. 知识分层设计：元信息 → 核心知识 → 扩展资料
2. 按需加载机制：什么时候加载什么内容
3. **「渐进式披露」三层设计**：
   - Layer 1: frontmatter 元数据（name/description/triggers）
   - Layer 2: SKILL.md 正文（Goal/Steps/Constraints）
   - Layer 3: 按需加载 references/assets

### 阶段 6: Assets 拆解
1. 资产是「被读取」还是「被直接输出」？
2. 模板化程度：是否支持参数注入？
3. 复用性：资产是否可被其他 skill 引用？

### 阶段 7: 独特解法提炼 ⭐
**每个解法必须包含四要素**：
1. **通用做法**：没有此 skill 时，用户通常怎么做？
2. **Skill 做法**：此 skill 如何解决同一问题？
3. **设计巧思**：核心创新点是什么？
4. **适用边界**：什么场景下有效？什么场景下无效？

提炼可复用的设计模式。

### 阶段 7.5: 吸收边界判断
1. 是否已有 adk 同类 skill 或 runbook；若有，优先 MERGE。
2. 是否符合嵌入式全栈或通用 ADK 资产治理边界；不符合则 REJECT/OBSERVE。
3. 是否需要 manifest、profile、hook、MCP 或显式 tool target 交付链路变更。
4. 临时参考资料只作为输入证据，不进入长期 knowledge 或 adoption matrix。

### 阶段 8: 综合评估
5 维评分（每项 0-20，满分 100）：
1. **痛点精准度**：是否解决了真实痛点？
2. **工作流清晰度**：流程是否可执行、可验证？
3. **上下文效率**：渐进式披露是否合理？
4. **资源设计**：脚本/模板/文档是否高质量？
5. **可扩展性**：是否易于修改和扩展？

输出：评分表 + 最佳实践总结 + 改进空间

## 来源
方法论来源于 comeonzhj/comeonzhj-claude-plugins 的 howSkills.md，经 adk 本地化改造。

## 核心原则
- **反向推导**：从实现细节反推设计意图
- **产品视角**：关注"为什么这样设计"而非"它能做什么"
- **确定性权衡**：用脚本固化确定性环节，让 LLM 专注于理解和决策
- **Mermaid 可视化**：时序图 + 流程图贯穿分析过程

## 输出模板
分析结果写入目标仓库的 `analysis/skill-deep-analysis.md`，或写入 adk 的 `references/skill-patterns/` 目录。

## 与其他 Skill 的关系
- 与 `adk-repo-prompt-analysis` 配合使用
- 输出的"独特解法"可直接用于 adk 的 skill 设计参考
- 输出的"5 维评分"可纳入 adk 的质量评估体系

## Quality Gate
- 分析报告必须包含具体文件/行号证据
- 禁止直接引用 description 字段，必须从实现反推
- 5 维评分每项必须给出≥1个具体证据
- 输出报告必须包含"可借鉴点清单"章节

## Commands

```bash
# 分析仓库的 prompt 结构
bash scripts/devkit.sh analyze --repo <repo-path>

# 生成分析报告
bash scripts/devkit.sh analyze --repo <repo-path> --output reports/analysis.md

# 验证分析结果
bash scripts/devkit.sh verify --analysis reports/analysis.md
```

## Evidence Template

### 分析报告模板

```markdown
# <仓库名> Prompt 分析报告

> 分析时间: YYYY-MM-DD
> 分析工具: adk-repo-prompt-analysis

## 发现的 Prompts

| # | 文件路径 | Prompt 类型 | 用途 |
|---|---------|------------|------|
| 1 | ... | ... | ... |

## 建议

- 建议 1
- 建议 2

## 验证

- [ ] 所有 prompts 已识别
- [ ] 分类准确
- [ ] 建议可执行
```
