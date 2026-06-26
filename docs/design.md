# Codex V2 设计

## 核心模型

v2 采用构建系统模型，而不是目录镜像模型：

```text
src/codex-home + manifests -> build/codex-home -> ~/.codex
```

- `src/codex-home/`：人工维护源资产。
- `manifests/`：声明式 SSOT。
- `build/codex-home/`：生成产物，可随时删除重建。
- `~/.codex`：Codex 运行目录，保留系统 skill、认证、session、日志、缓存和本机私有状态。
- `~/knowledge-hub/domains/codex/archive/codex-archive/`：长期知识沉淀，不参与注入。

## Manifest

`manifests/assets.json` 定义源目录、构建目录、默认 profile 和复制根。

`manifests/profiles.json` 定义可选运行 profile。profile 是能力选择边界，不直接包含文件路径。

`manifests/skills.json` 与 `manifests/agents.json` 定义可激活能力：

```json
{
  "name": "skill-asset-manager",
  "enabled": true,
  "source_kind": "vendor",
  "version": "0.2.0",
  "vendor_rel": "vendor/skills/skill-asset-manager/0.2.0",
  "target_rel": "skills/skill-asset-manager",
  "profiles": ["solo-dev", "team-collab"]
}
```

`manifests/policies.json` 定义受保护路径。构建和注入必须跳过这些路径，尤其是 `skills/.system/**`、密钥、session、缓存和日志。

`manifests/workflows.json` 定义可复用工作流编排。每个 workflow 必须显式声明启用 profile、触发词、依赖 skill、依赖 agent、入口命令和验证命令。

`manifests/workflow_recipes.json` 定义 workflow 的执行契约。recipe 不替代 workflow，而是补充上下文输入、完成标准、审查产物、失败模式和验证命令，用于把“会用”变成“可评测”。

`manifests/automations.json` 定义等待型或定时任务候选。automation manifest 只声明数据源、频率、sandbox、approval policy、worktree policy、停止条件和输出产物；默认不创建真实调度器，也不得绕过人工审批执行外部写操作。

`manifests/mcp_servers.json` 定义 MCP server 声明和 readiness。build 只把匹配 profile 的 server 渲染到 `config.toml`；manifest 支持 `stdio` 和 `http` transport。官方 OpenAI Docs MCP 使用 `openaiDeveloperDocs` + `https://developers.openai.com/mcp`，只读、无 env token。启用前必须有工具清单、网络目标、可执行 deny-path、日志脱敏、smoke 和回滚边界；启用后仍不得把私有代码、凭证或未脱敏日志作为查询内容。

`manifests/subagent_contracts.json` 定义子代理契约。它约束 agent、profile、读范围、写范围、禁止路径、sandbox、最大并行和输出契约，用于避免并行代理跨边界写入。

`manifests/memory_candidates.json` 定义长期记忆候选。它只记录候选状态、来源、拟提升动作、人工审查和 secret scan 门禁，不直接写入 `~/.codex/memories`。

`manifests/eval_suites.json` 定义 routing、governance、completion 和 prompt 级 eval 契约。每个 suite 必须声明 cases 路径、成功指标、最低通过率、负例要求、命令、产物和 promotion gate。

`manifests/cli_command_contracts.json` 定义 Codex slash command 控制面契约，例如 `/goal`、`/review`、`/compact`。它约束输入、允许动作、禁止动作、输出格式和验证命令，防止命令入口绕过验证或静默扩大权限。

`manifests/guidance_promotions.json` 定义指导规则提升路径。任何从会话、归档、manifest、测试或官方资料提升到 `AGENTS.md`、skill、archive 或 memory 的内容，都必须有来源、review、secret scan、最小证据、验证和回退方式。

`manifests/goal_templates.json` 定义 weak、strong、continuous 目标模板。强目标必须包含范围、成功标准、验证命令和可审查产物；continuous 目标必须额外明确数据源、刷新边界和停止条件。

`manifests/prompt_experiments.json` 定义 prompt、AGENTS 或 skill 指导规则实验。实验必须声明目标路径、假设、至少两个 variant、eval suite、样例、grader、人工评审、成功指标、产物和回退方式。

`manifests/trace_eval_contracts.json` 定义过程轨迹评分契约。它不只看最终结果，还约束必须出现的工作事件、禁止事件、rubric 权重、最低分、验证命令和可审查产物。

`manifests/context_state_contracts.json` 定义上下文状态契约。stable、dynamic、evidence 和 excluded 四层必须各自声明必填字段、默认去向和 promotion gate，excluded 层必须永不提升。

`manifests/automation_run_records.json` 定义 automation 单次运行记录。记录只承载 triage、清理、保留、人工审查状态和禁止动作，不创建真实调度器，也不得替代人工审批。

`manifests/skill_mcp_dependencies.json` 定义 skill 对 MCP server 和 tool 的依赖。它声明访问模式、所需工具、允许动作、禁止动作、审批要求、fallback 和验证命令，防止 skill 隐式启用外部能力。

`manifests/slash_command_runtime_audits.json` 定义 slash command 的运行态审计。它绑定 `manifests/cli_command_contracts.json` 中的 command contract，记录 audit events、runtime controls、required evidence、retention 和禁止动作。

`manifests/official_docs_freshness_gates.json` 定义官方文档 freshness gate。官方资料提升到长期规则前，必须有官方 source URL、retrieved_at、review_status、expires_at、stale action、验证命令和回退方式。

`manifests/permission_profiles.json` 定义本地权限边界审计。它把有效 sandbox、approval、filesystem、network、forbidden modes 和 rollback 写成可验证契约；当前默认仍使用旧 `sandbox_mode`，不得和 beta `default_permissions` 混用。

`manifests/exec_rules.json` 定义 Codex command rules 的声明式审计。每条 prefix rule 必须带 match / not_match 样例和 justification；治理校验会拒绝 broad allow `bash`、`python`、`git`、`curl`、`npx` 等高风险前缀。

`manifests/hook_contracts.json` 定义 Codex hook 的设计契约。hook contract 只声明事件、matcher、输入/输出、允许动作、禁止动作、retention 和验证；默认 disabled/report-only，不等同于已安装或完整执行边界。

`manifests/project-templates.json` 定义项目类型映射。它用路径模式把项目归类到默认 profile、推荐 workflow 和归档主题，解决“不同项目之间如何复用同一套 Codex 工作流”的问题。

`manifests/overlays.json` 定义场景覆盖层。overlay 用来约束个人本地、团队共享、发布脱敏等场景下哪些 live 差异允许存在，哪些路径必须阻断。

治理 manifest 只描述关系，不直接改变 build 复制内容；关系正确性由 `doctor --scope governance` 和 `scripts/check.sh` 检查。例外是 `manifests/mcp_servers.json` 会被 build 读取并生成禁用优先的 MCP 配置块，但真实凭证和启用决策仍留在人工审查边界内。`permission_profiles`、`exec_rules` 和 `hook_contracts` 是本地审计契约；除已纳入 `src/codex-home/rules/default.rules` 的 rules 文件外，不自动生成或安装运行态权限和 hook。

## 构建

`scripts/build.sh` 是薄 wrapper，核心实现在 `tools/codex_assets/`。构建负责：

1. 清空并重建 `build/codex-home/`。
2. 从 `src/codex-home/` 复制声明的资产根。
3. 根据 profile 为 skills 和 agents 创建相对 symlink。
4. 生成 `skills/registry.csv`。
5. 生成 `control/state/active-profile.env` 与 `managed-files.json`。
6. 生成 `manifests/lock.json`，锁定 active vendor skill 的内容摘要。

构建产物不纳入 git，不手工编辑。

## 注入

`scripts/apply.sh` 只从 `build/codex-home/` 注入到 `~/.codex`。注入前可生成机器可读计划：

```bash
rtk bash scripts/plan.sh --target ~/.codex --output build/apply-plan.json
```

计划记录 copy、keep、overwrite、mkdir、skip、backup 路径和目标信息。注入策略：

- 新文件复制。
- 已存在普通文件默认保留。
- `--overwrite` 时先备份再覆盖。
- 生成文件和 profile symlink 会更新。
- 目录合并，不整体替换目标目录。
- protected paths 永远跳过。

## 体检

统一入口：

```bash
rtk bash scripts/doctor.sh --scope repo
rtk bash scripts/doctor.sh --scope governance
rtk bash scripts/doctor.sh --scope build
rtk bash scripts/doctor.sh --scope live
rtk bash scripts/doctor.sh --scope all
rtk bash scripts/governance-report.sh --json
rtk bash scripts/drift.sh
```

`repo` 检查仓库结构、manifest、脚本语法和旧入口残留，并执行语义校验：profile 引用、source 路径存在性、target 冲突、protected path 写入、lock 与 build state 一致性。`governance` 检查 workflow、workflow recipe、automation、subagent contract、memory candidate、eval suite、CLI command contract、guidance promotion、goal template、project template、overlay 和 MCP readiness 的跨 manifest 引用关系与路径/权限边界。`build` 检查构建产物和 profile 激活 symlink。`live` 检查目标运行目录的 managed state 与系统 skill 状态。

`drift.sh` 基于 live 的 `control/state/managed-files.json` 检查运行目录是否被手工改动，区别于 `diff.sh` 的 build/live 当前差异比较。

## Schema 与测试

`schemas/*.schema.json` 记录 manifest 结构要求，`doctor --scope repo` 会执行内置结构与语义校验。`tests/test_governance.py` 覆盖 workflow、workflow recipe、automation、subagent contract、memory candidate、eval suite、CLI command contract、guidance promotion、goal template、MCP readiness、project template、overlay 的引用错误与报告输出。`tests/test_agent_routing_eval.py` 用 fixture 固化 recipe 路由样例。`tests/smoke.sh` 会为 `minimal`、`solo-dev`、`team-collab` 创建临时 Codex Home，验证 build、plan、apply、diff、drift、doctor 和 `.system` 保留。

## 回滚

`scripts/rollback.sh` 根据 apply plan 回滚一次发布：

```bash
rtk bash scripts/rollback.sh --plan build/apply-plan.live.json
```

默认恢复 overwrite 动作的备份，并移除该 plan 中新增的 copy 文件。不会触碰未出现在 plan 中的运行态文件。

## Skill 归档

第三方或运行中生成的 skill 生命周期：

```text
discovered -> inbox -> reviewed -> vendored -> built -> applied
```

命令：

```bash
rtk bash scripts/scan-skills.sh
rtk bash scripts/promote-skill.sh inbox/skills/<name>/<timestamp> --version 0.1.0
rtk bash scripts/build.sh --profile team-collab
rtk bash scripts/apply.sh --profile team-collab
```

正式归档位置是 `src/codex-home/vendor/skills/<name>/<version>/`。`src/codex-home/skills/` 只保留 registry、README 和维护脚本等基础层。

## 知识沉淀

知识态不再放入 `src/codex-home/control/archives`、`control/knowledge`、`control/roles` 或 `control/workflows`。这些内容不是 Codex Home 运行资产，长期归宿是 `~/knowledge-hub/domains/codex/archive/codex-archive/`。

生命周期：

```text
runtime/session note -> sanitized source -> ~/knowledge-hub/domains/codex/archive/codex-archive/<topic>/ -> indexed knowledge
```

归档入口：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name
rtk bash scripts/archive-note.sh /path/to/note-dir --topic topic-name --move
```

设计约束：

1. 默认复制，不移动来源；`--move` 只用于明确完成迁移的材料。
2. 每次归档生成时间戳文件/目录、同名 `.meta.json` 和主题 `index.md`。
3. 归档目标必须位于本仓库内，默认 `~/knowledge-hub/domains/codex/archive/codex-archive/<topic>/`。
4. 拒绝归档 `.codex` 运行态、密钥、日志、session、cache、`auth.json`、protected paths 和旧 control 知识态目录。
5. `scripts/check.sh` 会阻止旧 control 知识态目录重新进入 `src/codex-home/`。

进入 `~/knowledge-hub/domains/codex/archive/codex-archive/` 的材料应是可复用结论、背景、约束、决策和验证证据；一次性过程噪音、私密上下文和机器状态不沉淀。
