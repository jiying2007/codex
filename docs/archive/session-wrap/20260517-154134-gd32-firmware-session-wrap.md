# GD32 固件仓库会话归档

## Source

- Date: 2026-05-17
- Captured At: 2026-05-17 15:40:51 HKT
- Scope: 当前 Codex 会话
- Projects:
  - `firmware-toolchains`
  - `gd32l235`
  - `charge_hc32f072`

## 本次完成

- `gd32l235` 提交前重新检查：
  - 确认 `master` 与远端对齐。
  - 重新执行 fresh build、package、`fwtool check --scope all`。
  - 扫描旧 `Examples/`、`GD32L235_APP_BOOT`、旧构建产物和本机路径残留。
- `gd32l235` 纯固件工程清理：
  - 从 `.vscode/tasks.json` 移除个人 `Codex:*` 任务。
  - 删除旧根目录 `.agents/`、根目录 `skills/` 和 `.vscode/codex-tasks-sync.ps1`。
  - 保留 VSCode 固件构建、打包、检查、烧录和调试配置。
- 三仓库 Codex 配套：
  - 为 `firmware-toolchains`、`gd32l235`、`charge_hc32f072` 生成仓库级 `AGENTS.md`。
  - 将项目 skill 放入 `.codex/skills/...`，避免污染根目录固件结构。
  - 为三仓库新增 `scripts/codex-check.sh` 作为统一提交前检查入口。
  - 为工具链仓库新增 `docs/codex-workflow.md`，为两个固件仓库新增 `Docs/codex-workflow.md`。
- 提交并推送：
  - `firmware-toolchains/main`: `caeb712 chore: 添加 Codex 工具链维护规范`
  - `gd32l235/master`: `1ea219b chore: 规范 Codex 固件维护配置`
  - `charge_hc32f072/master`: `e2cdd29 chore: 添加 HC32 Codex 维护规范`

## 关键决策

- 不再要求 `gd32l235` 保持单一提交，因此使用普通提交推送，未改写远程历史。
- Codex 支持文件统一放在 `.codex/`、`AGENTS.md`、`Docs/codex-workflow.md` 或 `docs/codex-workflow.md`、`scripts/codex-check.sh`。
- VSCode 配置保持纯固件用途，不混入个人 Codex 配置切换任务。
- HC32F072 仓库继续按 `HC32F072FAUA`、TQFN-32-EP/QFN32(5x5)、单 App 镜像维护，不套用 GD32L235 的 Stage0/Stage1 分区。
- `firmware-toolchains` 以 `manifest.json` 作为消费仓库工具路径机器契约，新版本工具链应并排新增，不原地覆盖。

## 验证证据

- `firmware-toolchains/scripts/codex-check.sh --versions`: PASS
  - ARM GCC: xPack GNU Arm Embedded GCC 9.2.1
  - OpenOCD: xPack OpenOCD 0.12.0 GD32 package
- `gd32l235/scripts/codex-check.sh --full`: PASS
  - JSON 配置检查通过。
  - `Tools/tests/*.py` 全部通过。
  - fresh build、package、`fwtool check --scope all` 通过。
  - App FLASH 约 77.13%，Stage1 FLASH 约 81.76%，Stage0 FLASH 约 28.32%。
- `charge_hc32f072/scripts/codex-check.sh --full`: PASS
  - JSON 配置检查通过。
  - fresh build、package、`fwtool check --scope all` 通过。
  - App FLASH 约 11.94%，RAM 约 14.36%。
- 三仓库 `git diff --check`: PASS。
- 推送后状态：
  - `firmware-toolchains`: `main...origin/main`
  - `gd32l235`: `master...origin/master`
  - `charge_hc32f072`: `master...origin/master`

## 已知风险与未决项

- Windows 本机未在本轮重新实际构建；此前用户已确认相关 Windows 构建链路可用。
- `gd32l235` 仍有 GD32 官方库 `gd32l23x_rcu.c` 的 allowlist 内 `-Wtautological-compare` 警告。
- `charge_hc32f072` 仍有既有 C warning，例如 `unused parameter`、`-Wmain`、`unused function`、`sign-compare` 等；当前 `fwtool check` 通过。
- Windows OpenOCD GD32L23x flash/debug 仍需硬件验证；仓库文档已记录 Windows 包限制。

## 恢复入口

- 工具链仓库检查：`firmware-toolchains/scripts/codex-check.sh --versions`
- GD32L235 完整检查：`gd32l235/scripts/codex-check.sh --full`
- HC32F072 完整检查：`charge_hc32f072/scripts/codex-check.sh --full`
- 固件仓库通用手动检查：
  - `python3 Tools/Firmware/fwtool.py build --generator ninja --build-dir build/gcc-ninja --fresh`
  - `python3 Tools/Firmware/fwtool.py package --build-dir build/gcc-ninja`
  - `python3 Tools/Firmware/fwtool.py check --scope all --build-dir build/gcc-ninja`

## 后续建议

- 在 Windows 主机上分别运行 `gd32l235` 与 `charge_hc32f072` 的 `scripts/codex-check.sh --full` 或等价 PowerShell 命令。
- 如需将这些仓库规则提升为长期行为记忆，可另行运行 memory-curator 并人工确认候选记忆。
