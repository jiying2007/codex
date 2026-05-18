# llm_tools 发布治理优化归档

## 背景

- 项目：llm_tools 母仓，统一管理 sigmastar-flasher 与 ota-packager。
- 目标：硬切换到规范命名与清晰边界，建立可复用的 Linux/Windows 发布机制。
- Windows 发布策略：内网 SSH Windows 构建机为权威路径，默认 x64-only，x86 仅实验验证。

## 决策

- Windows 默认发布目标只包含 x64：sigmastar-flasher EXE、sigmastar-flasher 安装包、ota-packager GUI EXE。
- x86 构建不进入默认发布基线；如需验证，必须显式开启并单独记录风险。
- Windows 发布默认执行最终 EXE `--smoke-test`，不得只信任 PyInstaller 构建完成。
- Linux 与 Windows 发布目录均生成 `release-manifest.json` 与 `SHA256SUMS.txt`。
- 发布说明统一由 `scripts/generate_release_notes.py` 从 manifest 与产物清单生成。
- 工具清单结构由 `schemas/tool-manifest.schema.json` 与 `schemas/tool-registry.schema.json` 固定。
- Windows 构建依赖使用持久 pip cache；源码打包排除 `.venv-win-*`，避免依赖环境混入源码包。

## 落地入口

- 本地 Linux 发布：`./scripts/release_local.sh <version>`
- Windows 远程发布：`./scripts/release_windows_remote.sh <version>`
- 全量编排：`./scripts/release_all.sh <version>`
- 构建机诊断：`./scripts/windows_builder_doctor.sh`
- 发布说明生成：`./scripts/generate_release_notes.py <version> --out release-notes/v<version>.md`

## 关键文件

- `AGENTS.md`
- `README.md`
- `docs/release-mechanism.md`
- `docs/tool-governance.md`
- `docs/windows-builder-runbook.md`
- `.codex/skills/llm-tools-governance/SKILL.md`
- `scripts/windows/remote_release.ps1`
- `scripts/release_windows_remote.sh`
- `scripts/release_all.sh`
- `scripts/release_local.sh`
- `scripts/generate_release_notes.py`
- `schemas/tool-manifest.schema.json`
- `schemas/tool-registry.schema.json`

## 验证证据

- `python3 scripts/check_codex_standards.py`：通过。
- `python3 scripts/check_git_remotes.py`：通过。
- `python3 scripts/toolctl.py validate`：通过。
- `python3 scripts/toolctl.py run sigmastar-flasher test`：42 passed。
- `python3 scripts/toolctl.py run ota-packager test`：46 passed。
- `./scripts/windows_builder_doctor.sh`：通过。
- `./scripts/release_windows_remote.sh 0.2.0`：通过，Windows x64 产物 SHA256 校验 OK。
- `./scripts/release_all.sh 0.2.0 --skip-windows`：通过，Linux 产物、Linux manifest、release notes 生成成功。
- `python3 -m json.tool release-manifest.json`：Linux 与 Windows manifest 均可解析。

## 已知环境提示

- 当前 Linux 环境缺少 `python3-venv`，脚本会降级到隔离依赖目录；建议发布机安装对应 `python3-venv` 包以减少警告。
- PySide6 在当前 Linux Python/OpenSSL 组合下会出现 OpenSSL 版本提示；本次构建成功，但长期建议统一发布机 Python 与 OpenSSL 基线。

## 后续可选优化

- 增加离线 wheelhouse 或内网 PyPI 镜像，减少首次 Windows/Linux 构建耗时。
- 增加 Windows Authenticode 签名与安装包发布渠道策略。
- 增加 JSON Schema 自动校验器，而不是仅检查 schema 文件存在和关键字段。
