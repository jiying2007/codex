# adk-pilot-framework — 补充参考资料

此参考文件只提供可选背景、示例和检查提示；当前能力流程、权限、回退与放行结论以 `../SKILL.md`、Manifest 及运行时门禁为准。示例命令不得被解释为写权限授权。

## 来源说明

- **核心来源**：`llm_agent/AGENTS.md` 中的"D5-D7 实战试跑与回灌"流程
- **部署参考**：ADK 源仓的 `docs/adk-usage-guide.md`；其他项目读取自己的部署与恢复说明。
- **检查入口**：目标实际声明的健康、加载与任务验收命令；不存在的旧脚本不视为可用。
- **效果比较**：ADK 的 `docs/evals/skill-method-parity.md`；只做 smoke 时不加载完整比较协议。

## 模式描述

### 1. 试跑场景分类

| 场景类型 | 说明 | 验证重点 | 典型目录 |
|----------|------|----------|----------|
| 功能开发 | 新功能从零实现 | Skill 触发准确率、输出质量 | 显式 tool target |
| 缺陷修复 | 已知 bug 修复 | 调试流程完整性、修复验证 | 显式 tool target |
| 重构 | 大规模代码重构 | 回归测试覆盖、破坏性变更检测 | 显式 tool target |
| 发布 | 版本发布流程 | 版本号、changelog、门禁全通过 | `agent-dev-kit` |
| 跨仓协作 | 多仓联动变更 | 交接协议、artifact 完整性 | 多仓 |

### 2. 试跑执行流程

```
场景定义 → 核对已部署能力 → 真实执行 → 产物验收 → 改进建议
```

**Step 1: 场景定义**
```md
[pilot-scenario]
id: pilot-<date>-<seq>
type: feature | bugfix | refactor | release | cross-repo
target_dir: <tool-target-dir> | <project-dir>
skills_under_test:
  - <skill-1>
  - <skill-2>
expected_behavior: <预期行为描述>
success_criteria: <可量化验收标准>
```

**Step 2: 能力交接**
先核现有能力来源和加载状态；需要安装/升级时交目标项目已授权的部署流程，准备好恢复入口后再试跑。不要为已有可用安装重复导出或重装。

**Step 3: 真实执行**
- 在目标目录执行真实任务
- 记录所有命令、输出、异常
- 禁止事后补写或美化日志

**Step 4: 证据收集**
保留任务输入/源码身份、实际加载轨迹（可用时）、最终产物、验收命令与退出码、失败与重试、未取得的用量。使用目标当前声明且已核实的检查入口，不臆造通用命令。精简日志保留原文指针。

**Step 5: 门禁验收**
- 任务验收与目标必需检查分别判断；不能用全部健康检查通过替代任务交付。
- 实际行为失败、环境阻塞和证据不足分别记录；未知根因进入取证，不因一次不明失败直接淘汰能力。

**Step 6: 回灌决策**

| 结果 | 决策 | 动作 |
|------|------|------|
| 全部 PASS 且行为符合预期 | 采纳候选 | 交独立采纳决策；不自动升级默认推荐 |
| PASS 但行为有偏差 | 改进 | 记录偏差，优化后重跑 |
| FAIL 且根因明确 | 修复 | 修复后重跑 |
| FAIL 且根因不明 | 调查 | 保留失败，提出最小证伪实验，不直接删除能力 |
| 环境阻塞或证据不足 | 暂不判断 | 明确恢复条件或缺失证据，不能算通过或能力失败 |

### 3. 试跑报告模板

```md
# Pilot Report: pilot-<date>-<seq>
- Scenario / Target Runtime / Exact Source:
- Selected Skills / Profile:
- Discovery / Load / Trigger Evidence:
- Test / Validation Commands and Exit Codes:
- Observed Result: pass | fail | not-run
- Known Limitations / Missing Evidence:
- Owner Decision / Rollback Anchor:
```

源码或静态导出通过不等于原生运行时或产品现场资格。
