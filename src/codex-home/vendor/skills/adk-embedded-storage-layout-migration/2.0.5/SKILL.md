---
name: adk-embedded-storage-layout-migration
description: "用于 MTD、UBI、分区及文件系统布局迁移的 host 端检查、演练和回退设计；不用于未授权的设备存储写入或纯日志检索。"
version: 2.0.5
last_updated: 2026-11-20
triggers:
  - "UBIFS转SquashFS"
  - "SquashFS转UBIFS"
  - "UBI卷布局调整"
  - "分区保留方案"
  - "存储布局迁移"
  - "OTA布局迁移"
  - "文件系统切换"
non_triggers:
  - "普通固件发布"
  - "只改版本号"
  - "非持久化临时挂载问题"
  - "只分析UBIFS只读故障"
  - "SquashFS空间占用解释"
inputs:
  - 分区表、配置、rootfs/ubinize/OTA layout、boot log、保留要求、目标设备 identity、恢复能力
outputs:
  - 迁移判定、受影响分区、保留策略、host/dry-run 证据、live-device operator handoff、回滚与剩余风险
constraints:
  - 文件系统形态切换不得被描述为普通 OTA，除非迁移、数据保留和回滚证据完整
  - 必须优先保护 factory/data/ota 等现场数据
  - workspace/release-preparation 权限不得推导 erase/flash/storage-write 权限
  - 真实设备 mutation 必须具备 target identity、explicit authorization、backup/recovery 和 post-write verification
---

# adk-embedded-storage-layout-migration

## Goal
- 管理 UBI/UBIFS/SquashFS/ubiblock、partition/volume 与 OTA layout 的迁移一致性。
- layout 设计、artifact 构建/dry-run 与真实设备 destructive mutation 分开授权。

## Prerequisites
- 已知道产品 profile、分区布局、升级方式和目标设备/板卡 identity。
- 已拿到配置、构建产物或 boot log 中至少一种证据。
- 已明确保留分区、最后可恢复版本和 recovery/backup 能力。

## Workflow
0. **问题分流**：仅解释 SquashFS 只读/df 100%、UBIFS 只读退化、挂载或 I/O 错误，交 `adk-systematic-debugging`；明确布局/FS 变更计划或迁移风险分析（含只读分析）才进入本 Skill。
1. **现状矩阵**：列 boot/rootfs、factory/data/ota、misc/pstore 等 partition/volume 的 FS、mount、update method、preserve policy 和运行态证据。
2. **变更分类**：区分普通内容更新、布局迁移、FS 切换、回滚迁移、产线重刷；不同类别不能共享同一风险结论。
3. **配置链对齐**：核 defconfig/current config、partition table、ubinize、mount script、OTA layout、release metadata、artifact hash；UBI/UBIFS 另对齐目标与镜像构建的擦除块 PEB、min-I/O/subpage、VID/data offset、LEB、volume 对齐/容量；未知或不符停在 host，不交设备。
4. **现场数据保护**：优先只更新目标 volume；whole-UBI/whole-device 覆盖默认禁止，除非明确说明为什么无法增量迁移并有完整备份恢复。
5. **host/build 验证**：重新生成 rootfs/customer/OTA/SD artifact，在不写真实设备的前提下校验 layout、manifest、size、hash 和 migration script dry-run。
6. **device escalation gate**：真实 erase/flash/storage-write 前生成 operator handoff：device identity、目标 partition/volume、前后布局、artifact hash、显式授权、backup/recovery、post-write readback/boot verification；缺项 blocked。本 Skill 不输出设备写命令。
7. **受控迁移证据消费**：消费受控 operator 的单设备/测试板 receipt；验证 cold boot、数据保留、read-only/write semantics、断电/失败恢复、rollback、重复升级。
8. **扩展准入**：单设备证据通过且 residual risk 可接受，才生成下一批 handoff；批量授权不得继承单设备授权。

## Commands
```bash
# 只读/host-side；真实设备写入不在此 Skill 执行。
rg -n "UBIFS|squashfs|ubiblock|factory|data|ota|ubinize|partition|layout" <repo>
rg -n "MOUNTPT|MOUNTPARAM|FSTYPE|VOL_TYPE|rootfstype|ubi.mtd" <repo>
rg -n "ubi0:|ubiblock|Mounted root|mounting .*customer|Kernel command line" <boot-log>
sha256sum <image-or-ota-package>
<migration-check-command> --dry-run
```

## Evidence Template
```md
- Migration Type:
- Target Identity:
- Preserve Requirements:
- Layout Matrix: partition / volume / FS / mount / update_method / preserve
- Config Chain + Artifact Hashes:
- Host/Dry-run Evidence:
- Live-device Operator Handoff:
  - required:
  - operation:
  - target_identity:
  - partition_or_volume:
  - artifact_sha256:
  - explicit_authorization:
  - backup_or_recovery:
  - post_write_readback:
  - boot_verification:
- Operator Receipt:
- Data Preservation Evidence:
- Failure / Power-loss / Rollback Evidence:
- Batch Expansion Decision:
- Gate Result: pass | needs-fix | blocked
```

## Failure Handling
- 配置、artifact 与 boot log 不一致时先停在 host/build 域，不通过设备写入“试出来”。
- 必须保留的数据没有可验证 backup/recovery 时禁止 destructive migration handoff。
- operator receipt 中 readback、boot 或数据保留任一失败时停止扩批并执行已声明 recovery/rollback。
- 设备出现只读/挂载异常时切 `adk-systematic-debugging`，保留原始 boot/storage evidence，不重复破坏性写入。

## Quality Gate
- 配置、产物和运行态证据必须可追溯；不一致时结论为 `needs-fix`。
- 每个必须保留的分区都要声明 erase/write 风险和验证方法。
- 任何 destructive mutation 都必须通过独立 operator handoff；本 Skill 最多产出 `ready-for-authorized-device-pilot`，不能自行声明 mutation 已执行。
- 批量迁移必须基于真实单设备 receipt 和独立 readiness/release gate，不得由 dry-run 自动升级。
