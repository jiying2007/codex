# ADK 来源审计与受控升级

## 先区分三个事实

ADK 最新 Release、Codex provider lock、每个 Skill 实际复制的来源是不同事实。Agent/Execution Policy 的 exact-source 检查通过，不能推导所有 Skill 已来自同一 ADK release；成员 live 安装又是单独的事实。

2026-09-24 的升级检查发现现有 Skill manifest 中仍有 `llm_agent/agent-dev-kit`、短 commit 和缺少 source_blob 的条目。禁止把这些字段直接重标为新版本；先读真正来源、比较完整 Skill support tree，再进行独立导入与回归。

首次真实清点来自 Run 35975523298（PR #30 merge ref 4f7f4e40cb3725c99a9061175ddbdb399ad74cd6）：42 个 active ADK Skill，42 个非 canonical repository、42 个缺失/无效 source_blob、36 个非完整 commit，0 个 source_ref 匹配现有 provider lock commit。这些缺项相互重叠，说明来源记录待修复，不证明技能行为均错误。后续状态以新鲜 audit artifact 为准，不手工维护第二份动态状态表。

## 唯一实现入口

```bash
cd ~/codex
rtk python3 -m tools.codex_assets.adk_skill_audit --summary-json
```

模块只读既有 `manifests/skills.json`、ADK provider lock 和实际 Skill 目录，不新增资源 SSOT、状态台账、安装入口或服务。省略 `--summary-json` 输出完整逐 Skill 诊断，但不输出正文、认证或 session。

退出码：0 表示本次范围内 local metadata consistency；2 表示真实 provenance/目标映射缺项；3 表示输入无效或无法完成审计。任何一种都不是 release/installation/runtime qualification。尤其 `consistent` 不能证明未经本次读取的上游 blob 归属。

检查范围包括 enabled ADK Skill 的 canonical repository、40-hex commit、source_blob 与实际 SKILL.md 的 Git blob、来源/安装路径、完整目录的内容和执行位摘要。通过 name、owner、tag、repository 联合识别 ADK 条目，不能只改 owner 隐藏旧来源。拒绝重复条目、非 boolean 状态、路径穿越、符号链接和超预算输入；无 active ADK 条目不视为通过。

## 固定候选来源比较

```bash
rtk python3 -m tools.codex_assets.adk_skill_audit \
  --provider-root /reviewed/exact-adk-checkout \
  --expected-provider-commit <FULL_40_HEX_COMMIT> \
  --summary-json
```

候选必须是 exact HEAD 的干净 checkout；manifest 和 Skill 全目录的 blob/执行位必须匹配 Git tree。还必须逐项比对 expected 文件集合，不能仅凭 git status 干净认定完整：skip-worktree/sparse checkout 可以隐藏缺失文件，core.fileMode=false 可以隐藏执行位变化。目录不可读时阻断，不能静默跳过。

只按现有 source_path 对比，不猜测重命名、替代 Skill 或其它目录。记录新增、删除、内容/执行位变更、完整 tree digest 和需人工/语义复核标记。source_available 仅表示可读取的精确源码，不表示兼容、已采用或已安装。

Runtime Binding Contract 保留既有所有门禁，新增 27 项审计回归与当前仓库诊断制品。诊断收集允许保留 needs-fix；这不是给升级门禁加豁免。CI 绿色只表示测试/收集过程成功，JSON 中的缺项不会变成 pass。

候选对比有两种显式维护入口：workflow_dispatch 设置 `audit_adk_candidate=true`；或由维护者为本仓分支的 PR 添加 `adk-candidate-audit` 标签。后者会在添加标签及后续 PR 更新时按新 commit 重新比较；fork PR 即使带标签也不走该入口。标签只是要求只读比较，不是资产采用、发布或权限批准。关闭维护 PR 或移除标签即结束该 PR 的后续候选比较。

两种入口均只对照固定 ADK 7.0.31 commit `7367ef84787de75bb751940b32c9e80009660e47`。普通无标签 PR/push 不下载候选，不把跨仓网络检查加入日常必经链。候选比较只在 Python3.11 job 执行一次；两个 Python 版本都执行单元回归。报告绑定 consumer commit、manifest/lock digests 和 candidate commit，并作为 Actions artifact 留存。

```bash
gh workflow run runtime-binding-contract.yml \
  --repo jiying2007/codex --ref main \
  -f audit_adk_candidate=true
```

## 实际升级仍需独立完成

### 首批实际导入（2026-09-24）

已从上述固定 7.0.31 源码导入 `adk-runtime-router` 2.1.0、
`adk-code-review-loop` 1.7.0、`adk-verification-before-completion` 1.7.0。
三个目录共 8 个文件，包含新增的 3 个 references 文档；旧版本目录退役，
既有 profile/target/owner 不变，安装源 registry.csv 的对应版本同步更新。
本批没有上游目录之外的附加文件；未把其他 Skill 的许可证或 Codex 适配元数据作为删除清单。

每项来源在既有 skills manifest 绑定 canonical repository、完整 commit、
`source_blob`、`source_release` 和 `source_tree_sha256`。后者表示该项完整、精确复制的
目录摘要（包括路径、文件内容和执行位），不是第二份资源清单。
已声明此字段的导入必须通过整个目录一致性检查，不能只验证 SKILL.md；
旧资源没有该字段不代表其配套文件已经获得验证。

`tests.test_adk_daily_core_import` 验证固定来源、完整目录、引用文件、路由发现、
隔离目录中的 build/plan/dry-run/apply/no-op/rollback 与认证/session/system 文件保护。
该测试使用现有安装实现，不建立新安装入口；安装测试是临时目录验证，
不等于成员现场已更新或模型已执行过这些 Skill。一次性导入工作流不留在最终树。

三项 Skill 的来源版本与 Agent/Execution Policy provider lock 分开表达：本批并未
把仍锁定 7.0.4 的 Agent 和执行策略改标为 7.0.31。其余来源缺项继续如实报告，
每个 Skill 的版本应从该项 manifest 读取，不能由全局 provider lock 推断。

7.0.31 的 Execution Policy 已采用 contracts/decision/reducer 分工，不再存在旧 engine.py 源路径。后续升级必须迁移真正 consumer imports 与 exact blobs，不能为沿用旧代码而修改版本号、恢复 facade 或伪造 source identity。

先处理来源和候选差异，再分批导入现有 active Skill 的完整支持目录，保留本地 profile/触发映射并重新验证；Agent、Execution Policy 与 provider lock 的升级必须保持各自真实身份一致。实际 apply、漂移检查、回退和成员任务验证继续走原流程。

审计命令本身不升级 provider pin、不改已安装 Skill、不自动写成员 ~/.codex，不接触 Digital Worker 正式证据或 engineering-platform。上述首批导入只修改仓库的资源源目录；默认小团队路径保持 CLI + ADK + 项目验收 + Knowledge Hub。
