---
name: adk-repo-prompt-analysis
description: 逆向分析开源项目中的 Prompt/系统指令设计，提取上下文工程模式
version: 1.0.0
last_updated: 2026-05-16
triggers:
  - 分析子仓 prompt
  - 提取系统指令
  - 拆解提示词设计
  - 上下文工程分析
non_triggers:
  - 编写新 prompt
  - 优化现有 prompt
inputs:
  - repo_path: 目标仓库路径
outputs:
  - analysis_report: Prompt 分析报告 (Markdown)
constraints:
  - 禁止直接引用项目自述，必须从代码反推
  - 所有结论必须指向具体文件/行号证据
---

## Goal
## Prerequisites

- 理解相关领域的基本概念
- 熟悉项目结构和工作流程
- 具备基本的文档编写能力

逆向分析目标仓库中的 Prompt、系统指令、上下文构造方式，输出结构化分析报告。

## Workflow

<what-to-do>

## 执行流程（四阶段）

### 阶段 1: 项目结构探索
1. 扫描目录结构，识别语言框架
2. 定位关键目录：`skills/`、`agents/`、`commands/`、`prompts/`、`scripts/`
3. 统计资产规模（文件数、行数、语言分布）

### 阶段 2: 提示词识别与提取
使用 4 种方法交叉验证：
1. **文件名模式匹配**：搜索 `*prompt*`、`*system*`、`*instruction*`、`*SKILL.md`、`*AGENTS.md`
2. **代码变量搜索**：搜索 `system_prompt`、`user_prompt`、`messages`、`content=` 等变量赋值
3. **API 调用特征搜索**：搜索 `chat.completions`、`model.generate`、`invoke` 等 API 调用
4. **配置文件检查**：搜索 `.yaml`、`.toml`、`.json` 中的 prompt/message 字段

### 阶段 3: 提示词文档化
对每个识别到的 Prompt，提取：
- 位置（文件路径 + 行号）
- 类型（system/user/template/hybrid）
- 用途（一句话描述）
- 上下文工程手法（渐进式加载/条件注入/模板填充）
- 确定性程度（纯 LLM 即兴 vs 脚本辅助构造）

### 阶段 4: 分析报告
输出 `prompt-analysis.md`，包含：
1. 项目概述
2. Prompt 清单（表格）
3. 上下文工程模式分析
   - Agent 型：LLM 自主决策循环，分析工具定义和 Tool Schema
   - 嵌入型：LLM 作为工具，分析前序上下文构造
4. Mermaid 数据流图
5. 可借鉴点清单
</what-to-do>

<supporting-info>
## 来源
方法论来源于 comeonzhj/comeonzhj-claude-plugins 的 howPrompt.md，经 adk 本地化改造。

## 核心原则
- **反向推导**：不依赖文档自述，从实现细节反推设计意图
- **证据驱动**：所有结论必须指向具体文件/行号
- **上下文工程思维**：关注如何为 LLM 构造输入上下文

## 与其他 Skill 的关系
- 与 `adk-skill-deep-analysis` 配合使用：先用本 skill 提取 Prompt，再用深度分析流程拆解 Skill 设计
- 输出可直接用于 adk 的 `adoption-matrix.md` 更新
</supporting-info>

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
