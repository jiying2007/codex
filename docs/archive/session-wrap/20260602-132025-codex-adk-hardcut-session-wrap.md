# Codex ADK Skill 命名硬切换会话归档

- Captured at: 2026-06-02 13:18:31 Asia/Hong_Kong
- Source scope: 当前 Codex 会话、`agent-dev-kit`、`/home/leiwenjun/codex`、`/home/leiwenjun/.codex`
- Project: codex
- Workstream: adk-skill-naming-hardcut
- Sanitization: 未包含 secrets、完整聊天记录、私有 token、运行态日志原文或 `.codex/sessions` 内容
- Memory action: candidate

## 本次完成

### agent-dev-kit 侧

- 完成 ADK skill 命名规范化与轻风险清理。
- 已提交并推送 `agent-dev-kit`：
  - `384610b refactor(skill): 规范化 Skill 命名边界`
- 硬切换的 skill 名称：
  - `adk-plan-lite` -> `adk-lightweight-planning`
  - `adk-developer-growth-review` -> `adk-engineering-growth-review`
  - `adk-repo-prompt-analyzer` -> `adk-repo-prompt-analysis`
  - `adk-skill-deep-analyzer` -> `adk-skill-deep-analysis`
  - `adk-grill-with-docs` -> `adk-structured-requirements-questioning`

### codex source 与 live 侧

- 发现 `/home/leiwenjun/codex` source 尚未吸收 `agent-dev-kit@384610b`，直接 apply 会把旧命名继续带入 `~/.codex`。
- 先把最新 ADK skill 资产同步到 `/home/leiwenjun/codex` source，再执行 source-to-live 链路。
- 已删除旧 skill source/live 残留，并补齐新 skill 的 `README.md`、`LICENSE`、`agents/openai.yaml`。
- 已提交并推送 `/home/leiwenjun/codex`：
  - `d396628 refactor(skill): 硬切换 ADK Skill 命名`

## 关键决策

- 本轮采用 hard-cut，不保留旧 skill ID 的兼容别名。
- `~/.codex` 只通过 `/home/leiwenjun/codex` 声明式资产链路 apply，不直接手改 live。
- 旧 ID 残留扫描只对 active source/runtime 路径做结论；历史 session、缓存或聊天记录中的旧文本不视为 active runtime 残留。
- `adk-repo-prompt-analysis` 和 `adk-skill-deep-analysis` 正文里仍有少量历史模板痕迹，但属于上游 ADK 内容问题；没有在 `/home/leiwenjun/codex` 单侧改写，以免制造 source drift。

## 验证情况

### agent-dev-kit

- `rtk bash scripts/devkit.sh validate --strict --summary-json`: pass
- `rtk bash scripts/check-profile-coherence.sh`: pass
- `rtk bash scripts/devkit.sh runtime-boundary`: pass
- `rtk git diff --cached --check`: pass
- 旧 ID 残留扫描: active source 无匹配
- `rtk bash scripts/devkit.sh token-budget --summary-json`: pass
- `rtk bash scripts/devkit.sh file-modes`: pass
- `rtk bash tests/run_all.sh`: `tests=40 pass=40 fail=0`

### codex source/live

- `rtk bash scripts/build.sh`: pass，`managed=665`
- `rtk bash scripts/doctor.sh --scope all`: `errors=0 warnings=0`
- `rtk bash scripts/check-skills.sh`: `skills=50 errors=0 warnings=0`
- `rtk bash scripts/check-routing-precedence.sh`: `active_superpowers_in_default=0`
- active source/runtime 旧 ID 扫描: 无匹配
- `rtk bash scripts/drift.sh --target /home/leiwenjun/.codex`: `changed=0 stale=0 unmanaged=0`
- `rtk bash scripts/check.sh`: pass，65 个 Python 测试 OK，`minimal`、`solo-dev`、`team-collab`、`superpowers-compat` smoke 全部 drift-clean
- `rtk bash scripts/final-ready.sh`: 命令通过，仅提示 `THREAD_LONG`

## 运行态 apply 记录

- 首次 hard-cut apply:
  - `copy=15, keep=404, overwrite=3, delete=24, mkdir=233, skip=0`
- 元数据补齐 apply:
  - `copy=9, keep=421, overwrite=1, delete=0, mkdir=236, skip=0`
- EOF 格式修复后的补 apply:
  - dry-run: `copy=0, keep=421, overwrite=10, delete=0, mkdir=236, skip=0`
  - live: `copy=0, keep=421, overwrite=10, delete=0, mkdir=236, skip=0`
- 最终 `check.sh` dry-run plan:
  - `copy=0, keep=431, overwrite=0, delete=0, mkdir=236, skip=0`

## 经验与风险

- 若 `agent-dev-kit` 已更新但 `/home/leiwenjun/codex` source 未同步，直接 apply 会应用 stale source。
- 对 managed source 做 EOF 或格式修复后，必须重新 plan/apply，否则 `check.sh` 会在 live drift 阶段报 DIFF。
- `commit-ready` 和 `final-ready` 的 `THREAD_LONG` 是会话长度风险，不代表 diff 或资产门禁失败；但后续应新开线程。
- 本轮没有写入 `~/.codex/memories`。

## 下一步

- 后续若继续清理 `adk-repo-prompt-analysis`、`adk-skill-deep-analysis` 的正文模板痕迹，应先在 `agent-dev-kit` 上游修复，再同步到 `/home/leiwenjun/codex`，不要只改 codex mirror。
- 新线程继续执行任何新增 ADK 资产扩展或真实场景试跑。
