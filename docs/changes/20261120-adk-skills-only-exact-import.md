# ADK 11.4.16 Skills-only 受信升级

## 边界和原因

ADK 11.4.16 已发布为不可变来源，提供 65 项中文 UI 元数据；Codex 当前启用的 41 项 ADK Skill 仍固定于 11.2.1。Codex 执行策略另以独立来源锁固定于 ADK 8.2.0，以保持现有 Python 3.8 Host 运行兼容。直接执行旧版完整导入会错误复制 ADK 11.4.16 的 Python 3.12 策略，这是明确的跨层升级风险。

## 本轮最小实现

- 显式启用 `--preserve-execution-policy` 后，仅升级经签名证据和完整目录核验的 Skill/Agent 源码、Codex UI、注册表、provider lock，以及独立策略锁的 *consumer* 来源指针。
- 导入前核对当前锁、策略源码 Git Blob 和独立 source pin；原始 Python 3.8 策略源码、`execution_policy.json.engine.behavior_baseline`、原策略锁的 `source` 字段不变。参数或策略身份不一致即 fail-closed。
- 仅当新来源版本已明确前移、旧分发目录未被用户修改且所有导入及 README 投影检查通过，才在隔离候选中移除旧版本 Skill/Agent 目录。不改用户 `~/.codex`。
- 维护版冻结证据始终按 `manifests/provider-locks/agent-dev-kit.json` 的当前签名来源版本选择，旧版 `tests/fixtures` 继续作为不可变历史保留。新版本的 `openai_source` 取经精确 Git Tree 校验的上游 `agents/openai.yaml`，不得引用旧英文包装。

## 真实来源与执行条件

- ADK 11.4.16 release: `c41f7c933f653dd702b0d8042ae9df38807430dc`
- Release archive SHA256: `66107c68a2ac76488cd06238bc582114dcc4c595aa691da3d6114743b534d59b`
- ADK main promotion CI: run `44700552832`，原生签名 artifact `adk-promotion-evidence-c41f7c933f653dd702b0d8042ae9df38807430dc`
- 导入仍须实际提供干净 exact-HEAD ADK checkout、promotion-evidence.json、promotion-attestation.json 和 **SHA256=6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66** 的已核可信 Sigstore root。CLI 验签不能被模拟测试替代。

在干净、隔离的 Codex 候选分支上，按现有 `tools.codex_assets.adk_source_import` 命令提供：

```sh
python3 -m tools.codex_assets.adk_source_import \
  --root . --provider-root /verified/adk-exact-checkout \
  --expected-provider-commit c41f7c933f653dd702b0d8042ae9df38807430dc \
  --promotion-evidence /verified/evidence/promotion-evidence.json \
  --promotion-attestation /verified/evidence/promotion-attestation.json \
  --trusted-root /verified/trusted_root.json \
  --release-artifact-sha256 66107c68a2ac76488cd06238bc582114dcc4c595aa691da3d6114743b534d59b \
  --allow-reviewed-native-ui --preserve-execution-policy --summary-json
```

核实计划确为 41 项、模式 `preserve-independent` 且无 removed/blocked 后，使用相同参数加 `--apply`。完成后运行独立 `--write-source-fixture --baseline-provider-version 11.2.1`（仅对 exact provider checkout）；拒绝从已退役的 7.0.31 Skill 集合猜测当前人口。完成新来源冻结夹具后运行全部测试及 Codex build/plan/dry-run/rollback，再提交受保护 PR。**不直接部署成员 HOME，不声称 Native UI 已通过**。

## 当前状态

源码修复与确定性单元回归已完成；正式受信升级的 41 项资产必须在真实 GitHub runner 或其它受控联网环境执行，并单独保留签名与 native UI 验收回执。绝不把临时测试替身作为该回执。
