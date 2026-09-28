# 隔离候选验证与现场边界

## 已验证

- 原 `~/codex` 的 9 文件 dirty diff SHA256 为 `234c76f8d2187f5655320ed1d712f13cb0fe5b6c101d4e5c7f53c8ef0f07df55`，隔离候选导入前整份 diff 完全一致；原主仓没有被清理或改写。
- ADK `v7.12.4` main `35b5fb31810c654a295c25b89e04435d6a32f57c` 的签名 promotion、Release artifact SHA256 `cc6f21f6fba7b1976f934c2c09f670ec13643450b28df78e7e2ddf5a8f90a4a1` 与 exact source identity 均经根仓验证。隔离候选使用经审查的 Sigstore trusted root SHA256 `6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66`。
- `adk_source_import` 只读计划列出 42 个启用 Skill、9 个 Agent、5 个 Skill 内容变更；仅在隔离候选执行 apply。独立读取上游 Git tree 冻结了 7.12.4 测试向量，旧版本受管目录按新版本替换。
- `adk_skill_audit`：`consistent`、42/42 source_ref 匹配、0 gap；`validate-adk-agent-binding.py` 与 `validate-runtime-binding.py` 通过；repo doctor 0 errors/0 warnings。
- fresh review 发现 31 份本地 README 包装文件仍写旧来源 commit，5 份新版目录还写旧 Skill 版本；导入器只刷新 `distribution_metadata.README.md.source=null` 的本地文本并同步 installed blob。上游 README、SKILL.md、脚本与 references 不改；再次来源审计 42/42、分发/安装定向测试 24/24 通过。
- Python 3.8 `unittest discover` 312/312 通过；`team-collab` build managed=766，repo/build/governance doctor 均为 0 errors/0 warnings。
- live 当前 profile 从 `~/.codex/control/state/managed-files.json` 只读确认为 `team-collab`。README 包装修正后的计划对 live 为 34 copy、400 keep、42 overwrite、73 旧受管路径 delete、292 mkdir、0 skip，`apply --dry-run` 返回 `plan_state=ready`。完整 `check.sh --pre-apply --offline-hermetic --no-build --plan` 再次通过；所有 profile 的实际安装 smoke 仅在 `/tmp`，不是 live apply。

## 尚未声明

- 原 `~/codex` main 和 `~/.codex` 未写入本候选。隔离 clone 的 source path 不能作为最终 live 来源；必须先完成 Codex 候选提交、托管 CI、合并与受管主仓 clean 同步，再以最终 source SHA 重建 plan 并 apply。
- Python 3.11/3.12 的 Codex 托管 CI、真实模型效果、Software M5 产品资格和 Knowledge Provider promotion 均未验证。根仓的参考仓 baseline 与 M5 门禁仍独立阻断。
- 73 个删除动作仅在同一计划的旧受管路径范围内获得 dry-run 校验；live apply 前仍需 fresh target 快照、backup、保护路径复核与 no-op/rollback 锚点。
