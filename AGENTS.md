# 全局 Agent 规则

本文件约束本机 Codex 的默认工作方式。目标是低噪音、可验证、adk-first；Superpowers 仅作为显式兼容 fallback。

## 1. 优先级

1. 当前会话中用户的明确要求
2. 当前仓库的 `AGENTS.md`、文档和约定
3. 本文件
4. 已触发的 adk / skill / Superpowers 流程定义

若规则冲突，遵循更高优先级；若安全、验证或权限边界不清楚，先收敛风险再执行。

## 2. 默认工作模式

- 默认使用 **adk-first** 工作流；已有 `adk-*` 等价能力时优先使用 adk。
- Superpowers 只在以下情况使用：用户明确点名、adk 无等价能力、需要迁移期回归对照、或当前平台缺少 adk 所需能力；默认 profile 不激活 Superpowers，显式兼容使用 `superpowers-compat`。
- 不默认启用 full Superpowers；小任务走轻量路径，中大型任务再升级流程。
- 能直接完成并验证的，不升级为重流程；能用单一专项 skill 解决的，不扩展为多 skill 组合。
- 只读分析任务可不进入实现流程，但结论必须清晰、可追溯。
- 用户明确要求 `continue nonstop` 时，持续推进到验收达成或出现真实阻塞。

## 3. 任务分流

- 轻量任务：单文件或小范围修改、明确 bug 修复、配置 / 文案调整、小测试补充、局部文档修改。
- 轻量任务默认直接实现并做定向验证；仅在关键不确定且无法从上下文或代码确认时提 1 个关键问题。
- 中大型实现默认先明确目标、边界、风险、验证方式；长任务使用 `adk-planning-execution-loop` 分阶段推进。
- Debug / 测试失败 / 异常行为优先使用 `adk-systematic-debugging`，先确认根因再修复。
- Review / 提交 / PR 门禁优先使用 `adk-commit-pr-quality-gate`。
- 完成前优先使用 `adk-verification-before-completion`。

## 4. adk 路由主干

- 需求收敛：`adk-requirements-triage`
- 任务拆解：`adk-task-breakdown`
- 长任务计划与恢复：`adk-planning-execution-loop`
- 系统化调试：`adk-systematic-debugging`
- 嵌入式测试策略：`adk-test-strategy`
- C/C++ 静态分析：`adk-static-analysis-c-cpp`
- 并行子代理治理：`adk-parallel-agent-governance`
- worktree 治理：`adk-worktree-governance`
- 代码审查闭环：`adk-code-review-loop`
- 提交与 PR 门禁：`adk-commit-pr-quality-gate`
- 完成前验证：`adk-verification-before-completion`
- 分支收尾：`adk-branch-closeout`
- 运行时 skill 路由：`adk-runtime-router`

Superpowers fallback 不应覆盖已有 adk 路由，除非满足第 2 节条件。

## 4.1 辅助 skill 路由索引

- 当前会话收尾 / 结束会话 / 总结本次会话：`session-wrap`
- 提交总结 / commit 日报：`commit-daily-summary`
- 项目日报 / 按项目总结：`project-daily-summary`
- 调研纪要 / 分析结论：`research-note-wrap`
- 知识归档 / 长期沉淀 / 保存到 docs/archive：`knowledge-archive`
- memory / memories / 记忆整理：`memory-curator`
- 上下文压缩 / 会话接力 / resume prompt / 90 秒模板：`context-compress-handoff`
- 多源搜索 / 交叉验证 / 资料核验：`multi-search-engine`
- 浏览器查看 / 微信公众号 / agent-browser：`browser-reader`
- skill 资产 / 注册 / build / apply / rollback：`skill-asset-manager`
- 并行开发规划 / 多 worktree 协作：`codex-parallel-collab`
- 分支或 worktree 收口梳理：`worktree-closeout`
- 多个总结类同时命中时，优先级为 `session-wrap -> commit-daily-summary -> project-daily-summary -> research-note-wrap`。
- 归档类需求先生成对应总结或笔记，再用 `knowledge-archive` 归档。
- 本次使用过专用 skill 时，在回复中简短说明；未命中时说明未使用专用 skill。

## 5. 嵌入式全栈边界

adk 面向嵌入式全栈开发，覆盖芯片 / 板级约束、启动链、BSP、OS/runtime、驱动、中间件、协议栈、设备侧应用、上位机 / 产测 / 诊断工具，以及构建、调试、验证、发布、量产和现场维护闭环。

不把通用 Web、互联网后端、云原生和纯业务系统作为 adk 主目标；若项目本身包含上位机工具或设备配套工具，可按嵌入式交付链路处理。

## 6. 命令执行硬规则

- 所有 shell 命令必须通过 `rtk` 执行。
- 允许：`rtk <command> ...`
- 允许：`rtk bash -lc "<command> ..."`
- 禁止裸跑：`bash` / `git` / `rg` / `find` / `sed` / `awk` / `python` 等。
- 仅当 `rtk` 不可用或用户明确豁免时才临时降级，并在回复中说明。
- 不得虚构命令、退出码、日志或验证结果。

## 7. 文件与代码修改

- 修改前先理解相关代码、文档和局部约定。
- 默认最小充分实现，避免无关重构和格式化 churn。
- 手工创建或修改源码、脚本、配置和文档时，必须使用 `apply_patch`。
- 禁止用 heredoc、`cat > file`、`tee file`、shell 重定向、`python - <<EOF` 或 `Path.write_text("""...""")` 生成、覆盖或批量改写仓库文件。
- heredoc 只允许作为命令 stdin 测试输入使用，不得把输出落盘到仓库文件；确需使用时必须使用唯一且加引号的结束标记。
- 大量机械生成内容必须通过仓库内稳定生成器、模板工具或格式化工具完成，并纳入对应验证。
- 如果文件写入命令失败，先检查目标文件是否被部分写入或截断，再继续修复。
- 发现工作区已有改动时，默认视为用户改动；不得回退、覆盖或清理无关变更。
- 不运行破坏性命令，如 `git reset --hard`、`git checkout --`、危险删除，除非用户明确要求。
- 不使用非 Git 工具操作 `.git`。
- 不硬编码密钥、凭证、API key。
- 不用不可信输入拼接 shell 命令或 SQL。

## 8. Python 与脚本入口

- 仓库内新增 Python 工具入口时，优先收敛到 `tools.codex_assets` 包。
- `scripts/*.sh` 作为稳定包装层，负责定位 `ROOT`、注入 `PYTHONPATH`、转发模块入口。
- 文档、README、skill 和 agent 默认引用 `scripts/*.sh`，不直接引用内部 Python 文件。
- 新增或修改脚本入口后，至少从非仓库 cwd 执行一次帮助或 dry-run，防止隐式依赖当前目录。
- 新增或修改 Python / shell 脚本后，按风险运行语法检查、单元测试或入口 dry-run，防止半截文件进入提交。

## 9. 验证门禁

- 没有验证证据，不得声称“完成”“通过”“可提交”“可合并”。
- 小改动至少做定向验证；中等改动补回归；共享逻辑、高风险行为或新功能按风险升级测试。
- 验证无法执行时，必须说明原因、影响和剩余风险。
- 准备 final / commit / push / PR 前，应完成与改动直接相关的验证并如实报告。

## 10. `~/codex` 资产链路

修改 `AGENTS.md`、skill、workflow、manifest、script 或 docs 后，优先走 source 到 live 链路：

1. `rtk bash ~/codex/scripts/build.sh`
2. `rtk bash ~/codex/scripts/doctor.sh --scope all`
3. `rtk bash ~/codex/scripts/plan.sh --target ~/.codex --prune-stale --output ~/codex/build/apply-plan.json`
4. `rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json --dry-run`
5. `rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json`
6. `rtk bash ~/codex/scripts/check-routing-precedence.sh`
7. `rtk bash ~/codex/scripts/check.sh`

不要直接手改 `~/.codex` 来绕过声明式资产仓。

## 11. Token 效率

- 默认把 token 视为受限资源。
- 读代码、日志、diff、JSON 时优先关键窗口、关键字段和摘要。
- 不复述大段工具输出；只报告结论、关键证据、风险和下一步。
- 设计阶段保留必要权衡；实现和验证阶段压缩到动作、证据、阻塞。
- 当会话过长、上下文压力高或目标切换时，建议收口并新开线程。

## 12. Session Continuity Coach

- 在 final / commit / push / apply 前，或修改 `AGENTS.md`、skill、workflow、manifest、script、docs 后，优先运行对应 ready / coach 检查。
- 常用入口：
  - `rtk bash ~/codex/scripts/session-coach.sh`
  - `rtk bash ~/codex/scripts/session-coach.sh --deep`
  - `rtk bash ~/codex/scripts/final-ready.sh`
  - `rtk bash ~/codex/scripts/commit-ready.sh`
  - `rtk bash ~/codex/scripts/apply-ready.sh`
- 出现 `THREAD_LONG`、`CTX_PRESSURE`、`HOT` 或 `CRITICAL` 时，优先执行会话收口、归档和新线程接力。
- 未经用户明确要求，不直接写入 `~/.codex/memories`。

## 13. 多代理与并行

- 默认先判断是否适合并行；不适合时串行推进。
- 仅当任务可拆成 2 到 4 个边界清晰、写入范围互不冲突、可独立验证的子任务时，才并行。
- 并行前明确 `scope_write`、`scope_read`、`must_not_touch`、阻塞条件和最终整合验证。
- 共享 contract / schema / shared types / 根配置 / 依赖 / CI / lockfile 默认串行处理。
- 子任务完成不等于项目完成；必须统一整合、查冲突并跑最终验证。

## 14. Git 与提交

- 不自动 commit / push / merge / rebase，除非用户明确要求。
- commit 格式：`<type>(scope): <summary>`
- `summary` 使用中文、动词开头、长度不超过 50 字、不加句号。
- 常用 type：`feat` / `fix` / `refactor` / `docs` / `test` / `chore`

## 15. 文档与记忆

- 文档只记录可复用信息：背景、约束、决策、验证结果、未决项。
- 长期经验优先沉淀到项目级 `AGENTS.md` 或 `~/codex/docs/archive/`，避免把一次性过程噪音写入长期规则。
- 记忆整理默认只生成审计报告或候选，不静默覆盖 memory。
- 归档材料不得写入 `src/codex-home/`、`build/` 或 control 产物目录。

## 16. Skill 资产治理

- 本仓直接维护的 skill 位于 `src/codex-home/vendor/skills/<name>/<version>/`。
- 每个 managed skill 至少包含 `SKILL.md`、`README.md`、`LICENSE`。
- `SKILL.md` frontmatter 至少包含 `name`、`description`、`version`、`last_updated`。
- 推荐提供 `agents/openai.yaml`，至少包含 `display_name` 与 `short_description`。
- `src/codex-home/vendor/plugins/**/skills/` 属于上游插件内容，默认不改写。
- 批量修改 skills 后运行 `rtk bash ~/codex/scripts/check-skills.sh`。

## 17. 输出风格

- 默认使用简体中文，技术标识保留英文。
- 优先给结论、动作、验证和阻塞；避免寒暄、重复背景和大段原始输出。
- 分析类回答说明依据和权衡；执行类回答说明当前动作、验证结果和剩余风险。
- 复杂任务使用 `update_plan` 维护高层进度，任一时刻仅保留一个 `in_progress`。

<!-- RTK 规则文档：vendor/policies/rtk/1.0.0/RTK.md -->
