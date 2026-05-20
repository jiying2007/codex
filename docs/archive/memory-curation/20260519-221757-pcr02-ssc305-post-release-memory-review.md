# pcr02_ssc305_compile Memory Review - 2026-05-19

## Scope

整理 `pcr02_ssc305_compile` 在 2026-05-19 提交、推送、完整发布验证后的长期记忆候选。
本文件是审计报告，不直接覆盖 `~/.codex/memories` 或 `AGENTS.md`。

## Source Evidence

- Main repo commit: `eaf39335068010c415c901377fb1f45e77ba4f70`，`feat(build): 完善发布构建与整机OTA流程`
- App repo commit: `c488234121e68e75f523fd8b7d3c9c8808ecc7eb`，`chore(build): 移除测试宏并忽略工具链目录`
- Full validation command: `rtk ./build.sh release --profile ap6303bh_512m_v20 --sync-sources --publish-soc --force-vehicle-ota`
- Validation result: command exited `0`
- NAS release: `/mnt/mcu-release-nas/robot/soc/DVT/pcr02_ap6303bh_512m_v20/pcr02_soc_release_v1.1.8_20260519-132149`
- Published version: SOC `1.1.8`, mainboard MCU `1.1.18`, motor MCU `0.0.8`

## Stable Facts To Keep

- `build.sh` 是主仓标准入口，负责应用、SOC 固件、SD 升级、SOC OTA、整机 OTA 和 SOC 发布链路。
- 工具链由 `ssh://git@192.168.1.4:10022/vosen/toolchain/ssc305.git` 同步到主仓 `.toolchains/ssc305`，不提交到主仓。
- 当前阶段应用优先级仍是 `SourceCode/sdk/verify/xcrz_sigmastar_demo` 优先，`SourceCode/sdk/verify/gros` 作为后续切换目标。
- `build.sh release --sync-sources` 会显式同步主仓和应用仓到远端 upstream，并执行 hard reset / clean 类清理动作；这是发布自动化入口的预期行为，不再是“脚本完全不拉取”。
- 默认 SOC OTA 分区选择为 `boot kernel misc miservice customer`，跳过 `data`；只有确需升级 data 时才应显式选择。
- 设备无 USB，不生成 USB 工厂包。
- 发布目录使用浅层职责目录：`01_line_flash_bootloader`、`02_sd_upgrade`、`03_soc_ota`、`04_whole_ota`、`99_trace`。
- 整机 OTA 会从 NAS 读取最新主板 MCU 和电机 MCU 发布物，打包为 `ota_pkg_v<soc_version>.tar.gz`。

## Memory Update Recommendations

### Update `~/.codex/memories/projects/pcr02_ssc305_compile.md`

Suggested action: `write-memory-after-review`

Replace stale fact:

```text
自动化构建不在脚本内隐式 checkout 或 pull；CI 或发布操作者应先同步主仓、应用仓和工具链，再执行自检和构建。
```

With:

```text
自动化发布可通过 `build.sh release --sync-sources` 显式同步主仓和当前应用仓到 upstream，并清理本地改动；未传 `--sync-sources` 时不做远端同步。
```

Add stable fact:

```text
SOC 发布通过 `--publish-soc` 输出到 `/mnt/mcu-release-nas/robot/soc/DVT/<profile>/pcr02_soc_release_v<version>_<timestamp>`，并更新同级 `latest.json`。
```

Add stable fact:

```text
整机 OTA 由仓内 `tools/ota-packager/ota-packager.sh` 调用随仓二进制封装，不依赖 `ota-packager` 源码仓；MCU 固件从 `/mnt/mcu-release-nas/robot/mcu` 解析最新发布物。
```

Add validation baseline:

```text
提交后完整发布验证：`rtk ./build.sh release --profile ap6303bh_512m_v20 --sync-sources --publish-soc --force-vehicle-ota`。
```

Add known risk:

```text
完整构建后仍会产生 tracked 构建产物噪音，已观察到主仓 `SourceCode/boot/include/autoconf.mk.dep`、`libss_mbx.so` 和应用仓 `libs/arm/libs/glibc/11.1.0` 下库文件变化；提交前必须区分源码变更与构建产物。
```

## Archive-Only Details

- 完整构建过程中的 SDK `modpost` warning、`cp cannot stat` warning、`chmod cannot access` warning 属于当前 SDK 构建噪音，命令最终退出 `0`。这些不应写入长期 memory，保留在会话/验证记录即可。
- 发布产物 SHA256 与完整 manifest 保留在 NAS 发布目录，不扩写到 memory。

## Review Status

- Memory candidate written: no
- Recommended next manual action: update `~/.codex/memories/projects/pcr02_ssc305_compile.md` after user approval
