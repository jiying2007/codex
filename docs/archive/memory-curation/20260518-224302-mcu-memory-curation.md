# MCU 工作区记忆整理报告

## Source

- Workspace: `/home/leiwenjun/work/mcu`
- Captured At: 2026-05-18
- Scope: MCU 固件相关长期记忆审计
- Mode: report-only
- Safety Note: 不包含 NAS 密码、凭据文件内容、私钥或一次性命令流水。

## 输入概览

- 已读 memory:
  - `~/.codex/memories/projects/gd32l235.md`
  - `~/.codex/memories/projects/charge_hc32f072.md`
  - `~/.codex/memories/projects/firmware-toolchains.md`
- 缺失 memory:
  - `~/.codex/memories/projects/hc32f072.md`
  - `~/.codex/memories/projects/mm32spin023c.md`
  - `~/.codex/memories/projects/firmware-release-tools.md`
- 参考归档:
  - `~/codex/docs/archive/session-wrap/20260518-223626-mcu-session-wrap-firmware-release-nas.md`
- 参考仓库规则:
  - `/home/leiwenjun/work/mcu/firmware-release-tools/AGENTS.md`
  - `/home/leiwenjun/work/mcu/firmware-release-tools/SKILL.md`
  - `/home/leiwenjun/work/mcu/firmware-release-tools/docs/nas-release-guide.md`

## 结论

当前 MCU 记忆需要从旧的 `charge_hc32f072` 命名迁移到 `hc32f072`，并补齐 `firmware-release-tools` 与 `mm32spin023c` 的独立记忆。不要把“MCU 工作区路径调整”“三仓库独立记忆整理”这类一次性过程描述写入长期 memory；只保留稳定仓库事实、发布入口、硬约束和验证方式。

## 建议动作

| Action | Target | Reason |
| --- | --- | --- |
| `manual-write` | `~/.codex/memories/projects/hc32f072.md` | 替代旧 `charge_hc32f072.md`，记录当前仓库名、路径和 HC32F072FAUA 事实。 |
| `manual-review-drop` | `~/.codex/memories/projects/charge_hc32f072.md` | 旧仓库名会干扰后续上下文，应在 `hc32f072.md` 写入并确认后移除或改名。 |
| `manual-write` | `~/.codex/memories/projects/mm32spin023c.md` | 第三方 boot/app hex 发布项目，发布规则不同于源码构建固件。 |
| `manual-write` | `~/.codex/memories/projects/firmware-release-tools.md` | 中央发布工具仓，承载三固件统一发布、NAS 同步和 tag 门禁。 |
| `manual-update` | `~/.codex/memories/projects/gd32l235.md` | 可补充统一发布由 `firmware-release-tools` 承载；不要记录易过期 app 版本号。 |
| `archive-only` | 当前会话流水、版本验证日志、临时 batch id | 属于过程证据，不应进入长期 memory。 |

## 推荐记忆草案：hc32f072

```markdown
# hc32f072

Repository: `~/work/mcu/hc32f072`
Updated: 2026-05-18

## Stable Facts

- HC32F072 charge-board firmware repository.
- Target MCU: `HC32F072FAUA`, package `TQFN-32-EP/QFN32(5x5)`.
- Single `App` image repository; no Stage0/Stage1 boot chain.
- Shared toolchain submodule path: `Tools/Vendor/toolchains`.
- Build/release entrypoint: `Tools/Firmware/fwtool.py`.
- Unified release orchestration is provided by `~/work/mcu/firmware-release-tools`.

## Memory Layout

- Flash: `0x00000000`, 128KB.
- SRAM: `0x20000000`, 16KB.
- App: `0x00000000`, 128KB.
- No Stage0/Stage1/Download/Flag partition.

## Rules

- Do not apply the GD32L235 Stage0/Stage1 partition model unless explicitly requested.
- Artifact/package naming uses `hc32f072`, not the old `charge_hc32f072` name.
- HC32 values, IRQs, startup files, registers, package and Flash/RAM facts must come from HC32 official material, not GD32 inference.
- VSCode debug/flash defaults to SEGGER J-Link with device `HC32F072FAUA`.
```

## 推荐记忆草案：mm32spin023c

```markdown
# mm32spin023c

Repository: `~/work/mcu/mm32spin023c`
Updated: 2026-05-18

## Stable Facts

- Third-party firmware release repository; vendor provides separate boot and app HEX files.
- The repository packages boot/app/flag images, OTA app payload, merged programming image and full production image.
- Non-CI app version is declared by `release.json`; package and tag versions must be app versions.
- Unified release orchestration is provided by `~/work/mcu/firmware-release-tools`.

## Memory Layout

- Flash image range: `0x08000000..0x08007FFF`.
- App start: `0x08001800`.
- BootJumpFlag: `0x08001400`, value `55 AA AA 55`.
- Last 1KB data partition is reserved for parameters/calibration values.
- SRAM range: `0x20000000..0x20000FFF`.

## Rules

- OTA payload is the app `.bin`.
- Default field programming should use the merged boot/flag/app image and preserve the data partition.
- `flash_full` is for factory first programming or full recovery and includes the whole flash image.
- Do not add an extra `images/` layer inside the release bundle.
- Build output root uses `build/package`, aligned with source-build firmware package naming.
```

## 推荐记忆草案：firmware-release-tools

```markdown
# firmware-release-tools

Repository: `~/work/mcu/firmware-release-tools`
Updated: 2026-05-18

## Stable Facts

- Central firmware release tooling for `gd32l235`, `hc32f072`, and `mm32spin023c`.
- Profiles drive release metadata, programming defaults, OTA payloads and NAS display directories.
- Main CLI wrapper: `scripts/firmware-release.sh`.
- Source-build release wrappers: `scripts/release-gd32l235.sh`, `scripts/release-hc32f072.sh`.
- Third-party MM32 wrapper: `scripts/release-mm32spin023c.sh`.
- Unified NAS release wrapper: `scripts/release-to-nas.sh`.
- Team NAS mount helper: `scripts/setup-nas-mount.sh`.

## Rules

- NAS official release root is `/mnt/mcu-release-nas/robot/mcu`; do not append another `release` directory.
- Do not store NAS passwords in repositories, command examples, manifests or memory files.
- `--publish` requires release root to already exist and be writable.
- Same version with same content is idempotent; same version with different content must fail and require manual review.
- Release tags are app-version tags and must be created only after build/package/check and dry-run or verified real validation pass.

## Validation

- `rtk bash scripts/setup-nas-mount.sh --check`
- `rtk bash scripts/release-to-nas.sh --dry-run --release-root /tmp/<empty-release-root>`
- `rtk python3 -m unittest discover -s tests`
```

## 推荐更新：gd32l235

保留现有 `gd32l235.md` 的 memory layout 和 Stage0/Stage1/App 规则。可补充一条：

```markdown
- Unified release orchestration is provided by `~/work/mcu/firmware-release-tools`; do not duplicate NAS release logic in this firmware repo.
```

## 不建议进入长期记忆的内容

- 本次临时 batch id、timestamp、终端输出。
- 当前 app 版本号，除非它是正在进行的发布目标；版本会快速过期。
- “工作区路径改名”“记忆整理过程”这类一次性操作。
- NAS 用户密码、凭据内容、挂载过程中的本机 sudo 状态。
- `release/` 本地历史目录冲突细节；保留为归档证据即可。

## 下一步

如果需要把以上草案写入实际 memory，请明确要求“写入 memory 候选”或“直接更新 memory”。默认阶段只保留本审计报告。
