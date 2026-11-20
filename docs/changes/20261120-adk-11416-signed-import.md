# ADK 11.4.16 — 受信源码导入

## 来源和目标

- 发行仓：`jiying2007/agent-dev-kit`，正式不可变 Release [v11.4.16](https://github.com/jiying2007/agent-dev-kit/releases/tag/v11.4.16)。
- Source commit：`c41f7c933f653dd702b0d8042ae9df38807430dc`；Git Tree：`d8927518b9f5fafb944ba9e08a14a62dad5cb495`；Manifest blob：`65990ada947d4bb78e8c997db689d037a64050b2`。
- Source release archive SHA-256：`66107c68a2ac76488cd06238bc582114dcc4c595aa691da3d6114743b534d59b`。
- Sigstore Promotion 证据：ADK CI run `44700552832`、artifact `14612767990`；证书身份固定为 ADK `ci.yml@refs/heads/main`，OIDC issuer 固定为 GitHub Actions。
- 隔离导入执行：[Codex Actions run 44719286187](https://github.com/jiying2007/codex/actions/runs/44719286187)；精确校验 Release 包、Tag/树/Manifest、TUF trusted root SHA-256 `6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66` 及 Cosign bundle；严格验证后才运行现有导入器。

## 实际源码接入

- 使用既有 `tools.codex_assets.adk_source_import`，同时指定 `--preserve-execution-policy` 和 `--allow-reviewed-native-ui`；导入 41 个当前启用的 Skill 以及 9 项已有 Agent 的精确上游来源。
- 41 项全部改为源仓 `v11.4.16`，版本目录递增、配套 references/scripts/agents 元数据按来源复制，旧受管版本目录仅在导入验证后退役。
- `manifests/skills.json`、`manifests/agents.json`、Skill registry、Provider lock、独立 Policy 绑定和 `tests/fixtures/adk-skill-sources-11.4.16.json` 共同记录来源身份。
- Codex UI 的 `agents/openai.yaml` 使用来源的中文显示内容，原有 `SKILL.md`、工具、权限、路由与隐式调用安全边界仍由各自合同约束。
- 执行策略**继续来自独立可信 ADK v8.2.0**。这不会静默替换 Python 3.8 消费者所需的既有 Runtime Policy。
- 导入后同 SHA 的来源审计报告为 `status=consistent`，41 项与当前 Provider lock commit 一致；独立导入/来源测试 `54/54` 通过。一次性导入工作流已从候选最终树中删除，不纳入长期维护流程。

## 资格边界

这次证明受保护的源码分发候选的签名及内容身份，不等于已写入用户 `~/.codex`、Codex CLI 当前会话已显示中文、不等于模型触发效果或 token 实测改善，也不提升产品现场资格。候选需接受完整 PR CI 与合并后 fresh-main CI；本机部署另走 `build/plan/apply/doctor` 并验收实际 UI，任何失败不得自行降低门禁。

## 回退

只通过后续受保护 PR 恢复上一个已审核精确来源集及对应 Provider/Skill identity；不移动或覆盖历史不可变 Release、标签或用户工作目录。
