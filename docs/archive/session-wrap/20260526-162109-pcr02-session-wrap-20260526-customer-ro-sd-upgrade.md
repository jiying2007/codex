# 2026-05-26 会话收口：PCR02 /customer 只读挂载与 SD 升级固件

## 范围

- 项目：`pcr02_ssc305_compile`
- 仓库：`/vsdata/leiwenjun/pcr02_ssc305_compile`
- 主题：评估并修改 `/customer` 正常运行态挂载策略，编译 SD 升级固件，并分析其他 UBIFS 分区风险。

## 本次完成

- 将当前 profile 使用的 `spinand_MX35_512M.squashfs.partition.config` 中 `/customer` 挂载参数改为只读：
  - `customer$(MOUNTPARAM) = -o ro,noatime`
- 重新编译系统镜像：
  - `rtk bash -lc './build.sh compile --profile ap6303bh_512m_v20 --jobs 16 --allow-dirty --no-sync-sources'`
  - 结果：退出码 0。
- 打包 SD 升级固件：
  - `rtk bash -lc './build.sh package --profile ap6303bh_512m_v20 --pack sd --skip-defconfig --allow-dirty --no-sync-sources'`
  - 结果：退出码 0。
- 校验生成启动脚本包含：
  - `mount -t ubifs ubi0:customer /customer -o ro,noatime`
- 分析其他 UBIFS 分区：
  - `/config`：启动关键内容，当前仍 rw，无 `noatime`，风险仅次于 `/customer`。
  - `/factory`：设备个体数据，应倾向平时 ro，产测/校准窗口 rw。
  - `/ota`：维护态写入分区，已有 `noatime,bulk_read`，重点在升级状态机和断电恢复。
  - `/data`：运行态写分区，不适合 ro，建议至少加 `noatime` 并治理原子写和日志轮转。

## 关键决策

- `/customer` 正常运行态不应再有必须写入路径，应作为 app/lib/static resource 分区处理。
- 对 `/customer` 使用 `ro,noatime`，减少 UBIFS 元数据写、relatime 写和误写窗口。
- OTA/archive/产测校准如需写静态资源，应进入维护态，显式 remount rw，完成后 sync/fsync 并 remount ro。
- 本次构建使用 `--allow-dirty --no-sync-sources`，避免源码同步覆盖本地挂载配置修改。

## 验证证据

- `rtk git diff --check -- SourceCode/project/image/configs/general/spinand_MX35_512M.squashfs.partition.config`：通过。
- 生成 `rcS` 校验：
  - `SourceCode/project/image/output/rootfs/etc/init.d/rcS:26`
  - 内容：`mount -t ubifs ubi0:customer /customer -o ro,noatime`
- `compile`：退出码 0，镜像尺寸检查和 load address 检查通过。
- `package --pack sd`：退出码 0。
- SD 产物目录：
  - `SourceCode/project/image/output/images/Sd_Upgrade/`
- SD 产物：
  - `IPL`：35.1K
  - `IPL_CUST`：21.0K
  - `UBOOT`：226.4K
  - `SigmastarUpgradeSD.bin`：112.4M
- `SigmastarUpgradeSD.bin` SHA256：
  - `815b6cc3d558190530bdfc21c73425767c546b354a44a178b701738d9cce121e`
- `final-ready`：pass，但提示工作区仍有未提交变更。

## 风险与未决

- 未做上板烧录、启动和 OTA 实机验证，不能声明现场升级通过。
- 当前 dirty worktree：
  - `SourceCode/project/image/configs/general/spinand_MX35_512M.squashfs.partition.config`：本次有效配置修改。
  - `SourceCode/boot/include/autoconf.mk.dep`：构建生成/变动文件，需要提交前确认是否纳入或还原。
  - `SourceCode/project/release/chip/iford/sigma_common_libs/glibc/11.1.0/release/dynamic/libss_mbx.so`：构建生成二进制变动，需要提交前确认是否纳入。
- `/config` 仍是下一个重点风险点；它含 `/config/lib`、`/config/modules/5.10`、`modparam.json` 等启动关键内容，当前默认 rw。
- `/factory` 是否可改 `ro,noatime` 取决于产测/校准流程是否支持短时 remount rw。
- `/data` 建议先加 `noatime`，但不建议只读。

## 下一步建议

- 上板验证 SD 升级包：
  - 升级后检查 `/proc/mounts` 中 `/customer` 是否为 `ro,noatime`。
  - 启动 app，验证读取 `/customer/bin`、`/customer/lib`、resource、mp3、模型无异常。
  - 执行 OTA/archive/产测校准流程，确认需要写 `/customer` 的路径被维护态管控。
- 审计 `/config` 运行态写入路径；若无必须写入，考虑改 `ro,noatime`。
- 审计 `/factory` 写入窗口；推荐正常态 `ro,noatime`，产测/校准态短时 rw。
- 给 `/data` 增加 `noatime` 并继续保留 rw。

## 记忆候选

- `pcr02_ssc305_compile` 项目中，针对未提交本地改动的固件验证构建，继续使用 `--allow-dirty --no-sync-sources`，避免构建入口同步源覆盖本地配置修改。
- PCR02 当前 active image config 为 `spinand_MX35_512M.squashfs.partition.config`，`/customer` 已按静态资源分区策略改为 `ro,noatime`。
- 后续 UBIFS 分区治理优先级：`/config` 高于 `/factory`，`/ota` 关注升级状态机，`/data` 优先加 `noatime` 而不是只读。
