# MCU 固件发布与 NAS 同步会话归档

## Source

- Project: `/home/leiwenjun/work/mcu`
- Captured At: 2026-05-18
- Scope: 当前 Codex 会话
- Archive Topic: `session-wrap`
- Safety Note: 已脱敏；不包含 NAS 密码、凭据文件内容或私钥。

## 本次完成

- `firmware-release-tools` 增加统一 NAS 发布同步能力：
  - 新增 `publish-nas` 发布逻辑，支持 staging、checksum 校验、同版本防覆盖、批次 manifest。
  - 新增 `release-to-nas.sh`，串联三个固件的 build/package/check/dry-run 与 NAS 发布计划。
  - 新增 `setup-nas-mount.sh`，用于团队本机 CIFS 挂载初始化、凭据保存、fstab 配置、挂载检查和发布根目录检查。
  - 新增 `docs/nas-release-guide.md`，归档 NAS 发布目录、挂载、发布、防覆盖、tag、批次记录和回退规则。
  - 更新 `AGENTS.md`、`SKILL.md`、`README.md`、`docs/release-guide.md`，把团队使用入口和质量门禁固化到项目规则。
- 三个固件仓版本递增，用于验证 NAS 发布链路：
  - `gd32l235`: `1.1.18`
  - `hc32f072`: `1.1.2`
  - `mm32spin023c`: `0.0.8`
- `mm32spin023c` 增加 `release.json`，非 CI 发布时优先以该文件声明 app 版本。
- 已提交并推送四个仓库：
  - `firmware-release-tools`: `992186c feat: 增加 NAS 发布同步流程`
  - `gd32l235`: `b852651 chore: 升级发布版本到 1.1.18`
  - `hc32f072`: `dabcb82 chore: 升级发布版本到 1.1.2`
  - `mm32spin023c`: `2ad4bdd chore: 声明发布版本 0.0.8`

## 关键决策

- NAS 正式发布根目录固定为 `/mnt/mcu-release-nas/robot/mcu`，不要再追加 `release` 子目录。
- NAS 密码不得写入仓库、命令示例、日志、manifest 或归档材料。
- 团队本机凭据文件使用 `~/.config/firmware-release-tools/nas.robot.credentials`，权限要求 `600`。
- `release-to-nas.sh --publish` 必须要求 release root 预先存在且可写，避免 NAS 未挂载时误写本地目录。
- 同版本发布规则：
  - 同版本不存在：发布到 staging，校验后 rename 到最终目录。
  - 同版本同内容：幂等复用，状态为 `existing`。
  - 同版本不同内容：立即失败，禁止自动覆盖。
- tag 创建顺序：先预检 tag，发布门禁通过并写入发布目录后，再创建或推送 app 版本 tag。

## 已做验证

- `setup-nas-mount.sh --check`：CIFS 工具、凭据文件、fstab、NAS mount、`/mnt/mcu-release-nas/robot/mcu` 可写均通过。
- `release-to-nas.sh --dry-run --release-root /tmp/mcu-release-commit-check`：
  - `gd32l235` build/package/check 通过，生成 `would-publish` 计划。
  - `hc32f072` build/package/check 通过，缺少 OpenOCD 时按脚本规则输出 dry-run warning。
  - `mm32spin023c` package/check、烧录脚本 dry-run、compare、split-full smoke check 通过。
- `firmware-release-tools` 单测：`12 tests OK`。
- `python3 -m compileall firmware_release_tools tests`：通过。
- 四个相关仓库 `git diff --check`：通过。
- 敏感信息扫描：未发现 NAS 明文密码。
- 默认本地 `release/` 发布 dry-run 被同版本不同内容阻断，验证了防覆盖门禁生效。

## 当前仓库状态

- `firmware-release-tools`: `master...origin/master`
- `gd32l235`: `master...origin/master`
- `hc32f072`: `master...origin/master`
- `mm32spin023c`: `master...origin/master`
- `firmware-toolchains`: `main...origin/main`

## 恢复提示

- 发布到 NAS 前先执行：

```bash
rtk bash firmware-release-tools/scripts/setup-nas-mount.sh --check
```

- 正式发布命令基线：

```bash
rtk bash firmware-release-tools/scripts/release-to-nas.sh \
  --release-root /mnt/mcu-release-nas/robot/mcu \
  --publish \
  --tag \
  --push-tag \
  --verified-hc32f072
```

- 若只发布部分固件，使用 `--targets gd32l235` 或 `--targets gd32l235,mm32spin023c`。
- 若出现同版本不同内容冲突，不要覆盖目录；应升级 app 版本或人工复核历史发布目录。

## 后续建议

- 下一次真实发布时，用 NAS 根目录执行 `--publish --tag --push-tag`，并保留终端输出中的 batch id。
- 如需把 NAS 发布规则提升为长期个人记忆，应另行运行 `memory-curator --dry-run` 生成候选，不要把一次性会话噪音写入长期 memory。
