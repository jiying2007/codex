# ADK 来源审计与受控升级

## 先区分三个事实

ADK 最新 Release、Codex provider lock、每个 Skill 实际复制的来源是不同事实。Agent/Execution Policy 的 exact-source 检查通过，不能推导所有 Skill 已来自同一 ADK release；成员 live 安装又是单独的事实。

2026-09-24 的升级检查发现现有 Skill manifest 中仍有 `llm_agent/agent-dev-kit`、短 commit 和缺少 source_blob 的条目。禁止把这些字段直接重标为新版本；先读真正来源、比较完整 Skill support tree，再进行独立导入与回归。

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

候选必须是 exact HEAD 的干净 checkout；manifest 和 Skill 全目录的 blob/执行位必须匹配 Git tree。只按现有 source_path 对比，不猜测重命名、替代 Skill 或其它目录。记录新增、删除、内容/执行位变更、完整 tree digest 和需人工/语义复核标记。source_available 仅表示可读取的精确源码，不表示兼容、已采用或已安装。

Runtime Binding Contract 保留既有所有门禁，新增 23 项审计回归与当前仓库诊断制品。诊断收集允许保留 needs-fix；这不是给升级门禁加豁免。CI 绿色只表示测试/收集过程成功，JSON 中的缺项不会变成 pass。

仅在显式 workflow_dispatch 并设置 `audit_adk_candidate=true` 时，对照固定的 ADK 7.0.31 commit `7367ef84787de75bb751940b32c9e80009660e47`。普通 push/PR 不下载候选，不把跨仓网络检查加入日常必经链。候选比较只在 Python3.11 job 执行一次；两个 Python 版本都执行单元回归。报告绑定 consumer commit、manifest/lock digests 和 candidate commit，并作为 Actions artifact 留存。

```bash
gh workflow run runtime-binding-contract.yml \
  --repo jiying2007/codex --ref main \
  -f audit_adk_candidate=true
```

## 实际升级仍需独立完成

7.0.31 的 Execution Policy 已采用 contracts/decision/reducer 分工，不再存在旧 engine.py 源路径。后续升级必须迁移真正 consumer imports 与 exact blobs，不能为沿用旧代码而修改版本号、恢复 facade 或伪造 source identity。

先处理来源和候选差异，再分批导入现有 active Skill 的完整支持目录，保留本地 profile/触发映射并重新验证；Agent、Execution Policy 与 provider lock 的升级必须保持各自真实身份一致。实际 apply、漂移检查、回退和成员任务验证继续走原流程。

本次只读审计不升级 provider pin、不改已安装 Skill、不自动写成员 ~/.codex，不接触 Digital Worker 正式证据或 engineering-platform。默认小团队路径保持 CLI + ADK + 项目验收 + Knowledge Hub。
