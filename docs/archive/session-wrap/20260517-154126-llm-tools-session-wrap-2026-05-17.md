# llm_tools 三仓治理与单提交发布归档

## Source

- Date: 2026-05-17
- Project: llm_tools / sigmastar-flasher / ota-packager
- Scope: 当前 Codex 会话
- Archive Type: session-wrap
- Sanitization: 已移除内网远端地址、登录凭据、私有 env 内容和一次性过程噪音

## 本次完成

- 全面优化三仓治理资产：AGENTS、SKILL、tool manifest、脚本、发布文档和运行手册。
- 母仓新增统一生成物清理入口 `scripts/clean_generated.sh`，并在 `scripts/toolctl.py` 暴露 `clean-generated`。
- 将 wheelhouse 发布依赖从脚本内联改为 `requirements/release.txt`，支持 `LLM_TOOLS_RELEASE_REQUIREMENTS` 临时覆盖。
- 新增母仓长期文档：`docs/initial-release-baseline.md` 与 `docs/script-maintenance.md`。
- `sigmastar-flasher` 与 `ota-packager` 均补齐 `docs/runbook.md`、`docs/release.md`、`docs/troubleshooting.md`。
- 两个子仓 `tooling/tool.json` 统一标准动作：`test`、`preflight`、`validate`、`inspect`、`smoke`、`release_check`、`codex_check`、`clean`。
- 两个子仓 `scripts/clean_workspace.sh` 支持 `--dry-run`，并拒绝未知参数，避免误清理。
- 三个仓库均通过 `git commit --amend --no-edit --reset-author` 合并为单一初始化提交，并使用 `--force-with-lease` 覆盖推送。

## 当前仓库状态

- `llm_tools`: `0d17885040d33f5c765e3cfc45df123a31611951`
- `sigmastar-flasher`: `2efe549dfa772a882b02da2808e4409488b0a7bd`
- `ota-packager`: `6ac23a8814ad2183e0f94a74ce917d0267cb3322`
- 三仓均为 `master...origin/master` 同步状态。
- 三仓 `git rev-list --count HEAD` 均为 `1`。
- 三仓 author / committer 均为当前用户配置：`Leonard <wenjun.lei@videostrong.com>`。

## 关键决策

- 三仓当前阶段保持单一初始化提交，不保留中间优化提交历史。
- 覆盖推送使用 `git push --force-with-lease`，避免无保护地覆盖远端新增提交。
- 母仓只负责治理、注册、发布编排和跨仓脚本；两个子仓保持独立 Git 历史。
- 不在母仓使用 `git clean -X`，因为两个子仓目录对母仓是 ignored 目录，有误删风险。
- Windows 发布机制继续走内网 Windows 构建机和 Authenticode 可选/强制门禁；证书、密码、私有 pip 凭据不进入仓库。
- 发布基线文档不固定初始化提交短哈希，改为以实时 `HEAD` 和 commit manifest 为准，避免 amend 后文档漂移。

## 验证证据

已执行并通过：

- `rtk ./scripts/toolctl.py doctor`
- `rtk pytest -q`，母仓 `105 passed`
- `rtk ./scripts/toolctl.py run-all test`，`sigmastar-flasher 42 passed`，`ota-packager 46 passed`
- `rtk ./scripts/toolctl.py run-all preflight`
- `rtk ./scripts/toolctl.py run-all smoke`
- `rtk ./scripts/toolctl.py clean-generated --dry-run`
- `rtk ./scripts/build_wheelhouse.sh --help`
- 三仓 `git diff --check`
- 两个子仓 `release_check`，均完成 Linux 产物构建与 smoke test
- 三仓 `git ls-remote origin refs/heads/master` 复核远端哈希与本地一致

验证说明：`sigmastar-flasher` preflight 有 `max_workers > 当前串口数量` 警告，但 `ok=true`，属于当前无完整产线硬件环境下的非阻塞风险。

## 经验与风险

- `toolctl run-all clean --dry-run` 与子脚本自身参数语义必须区分；本次已补子脚本 `--dry-run`，防止 dry-run 被当作普通 passthrough 后实际清理。
- `release_check` 会生成 ignored 产物：`.venv/`、`build/`、`dist/`、缓存等；需要释放空间时使用 `rtk ./scripts/toolctl.py clean-generated`。
- Authenticode 机制已接入，但若没有证书只能生成 `NotSigned` 状态；正式发布前应配置证书并跑 required-mode 验证。
- wheelhouse 已外置依赖清单，但尚未做完整供应链审计报告；后续可补锁定和审计。

## 恢复提示

下一次继续时先执行：

```bash
cd /home/leiwenjun/bin/llm_tools
rtk ./scripts/toolctl.py doctor
rtk git status --short --branch
rtk bash -lc "cd sigmastar-flasher && git status --short --branch && cd ../ota-packager && git status --short --branch"
```

如需发布验证，继续执行：

```bash
rtk ./scripts/release_all.sh X.Y.Z --skip-windows
rtk ./scripts/windows_builder_doctor.sh
rtk ./scripts/release_windows_remote.sh X.Y.Z
rtk ./scripts/validate_release_artifacts.py --version X.Y.Z
```

## 后续建议

- 配置正式 Authenticode 证书后，跑一次 `WIN_SIGN_MODE=required` 的 Windows 远程发布。
- 为 wheelhouse 增加供应链审计报告或 constraints 锁定策略。
- 如继续扩大工具集合，按 `llm-tools-governance` 的 AGENTS / SKILL / manifest / docs / scripts 最小规范接入。
