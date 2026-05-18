# llm_tools 定向记忆整理附录

## Source

- Date: 2026-05-17
- Source Session Archive: `docs/archive/session-wrap/20260517-154126-llm-tools-session-wrap-2026-05-17.md`
- Base Memory Report: `docs/archive/memory-curation/20260517-154321-memory-curation.md`
- Scope: `llm_tools` / `sigmastar-flasher` / `ota-packager`
- Mode: report-only, no memory write

## 高价值稳定事实

1. `llm_tools` 是母仓，负责工具治理、注册、发布编排和跨仓脚本；`sigmastar-flasher` 与 `ota-packager` 保持独立 Git 仓库历史。
2. 当前三仓处于“单一初始化提交”阶段；后续治理优化如需保持该阶段，应使用 amend 后 force-with-lease 覆盖推送，而不是新增提交。
3. 三仓工具治理最小面包括：`AGENTS.md`、`.codex/skills/*/SKILL.md`、`tooling/tool.json`、`scripts/`、`docs/runbook.md`、`docs/release.md`、`docs/troubleshooting.md`。
4. `tooling/tool.json` 标准动作应覆盖：`test`、`preflight`、`validate`、`inspect`、`smoke`、`release_check`、`codex_check`、`clean`。
5. 发布依赖清单固定在 `requirements/release.txt`，`scripts/build_wheelhouse.sh` 只读取依赖清单，不再内联依赖。
6. 生成物清理统一使用 `rtk ./scripts/toolctl.py clean-generated`，不要在母仓使用 `git clean -X`，因为子仓目录对母仓是 ignored 目录。
7. 子工具清理脚本必须支持 `--dry-run` 并拒绝未知参数，避免 dry-run passthrough 导致实际清理。
8. Windows 权威发布目标保持 x64-only；x86 只作为实验项显式验证。
9. Authenticode、PFX 密码、内网 PyPI 凭据只允许存在于构建机或私有配置中，不进入仓库。

## 推荐动作矩阵

| Action | Memory Signal | Reason |
| --- | --- | --- |
| `archive-only` | 三仓当前 commit hash | hash 会随 amend 改变，只适合归档，不适合长期 memory |
| `promote-to-agents` | 禁止母仓 `git clean -X`，使用 `toolctl clean-generated` | 已写入项目 AGENTS，可保持为项目级规则 |
| `promote-to-agents` | 子工具必须维护 runbook/release/troubleshooting 文档 | 已写入项目 AGENTS 和治理 Skill，可保持为项目级规则 |
| `write-to-codex-agent-mem` | `llm_tools` 当前是三仓工具治理母仓，两个子仓独立管理 | 短小稳定项目事实，可人工确认后写入项目 snapshot |
| `write-to-codex-agent-mem` | 三仓当前处于单一初始化提交阶段 | 当前阶段状态，适合 snapshot，不适合永久规则 |
| `archive-only` | release_check 构建产物和测试结果 | 属于验证证据，保留在 session archive 即可 |
| `drop-or-review` | 内网远端地址、构建机登录细节、私有 env | 私有/敏感或机器状态，不应进入 memory |

## 候选 memory 草案（未写入）

以下仅作为人工审核草案，不代表已写入 `~/.codex/memories`：

```md
# llm_tools project snapshot

- `llm_tools` is the mother repository for embedded tooling governance and release orchestration.
- Current child tools: `sigmastar-flasher` and `ota-packager`, each kept as an independent Git repository.
- Current phase keeps each of the three repositories as a single initial commit; use amend plus `--force-with-lease` only when explicitly asked to preserve that shape.
- Use `rtk ./scripts/toolctl.py clean-generated` for generated artifacts; do not run `git clean -X` at the mother repo root because child repositories are ignored there.
- Standard tool manifest actions: `test`, `preflight`, `validate`, `inspect`, `smoke`, `release_check`, `codex_check`, `clean`.
```

## 不建议写入 memory 的内容

- 具体内网 Git 远端地址。
- Windows 构建机登录用户、授权文件细节、私有 env 路径。
- 本轮一次性提交哈希，除非作为短期 snapshot。
- 完整发布日志、PyInstaller 输出、checksum 细节。

## 下次恢复建议

```bash
cd /home/leiwenjun/bin/llm_tools
rtk ./scripts/toolctl.py doctor
rtk git status --short --branch
rtk bash -lc "cd sigmastar-flasher && git status --short --branch && cd ../ota-packager && git status --short --branch"
```

## 当前结论

- 适合长期保留：项目治理规则、清理安全规则、标准 manifest actions、x64-only 发布边界。
- 适合短期 snapshot：三仓单一初始化提交阶段和当前工作目标。
- 只适合归档：本轮具体验证输出、提交哈希和发布过程证据。
