---
name: adk-bsp-porting-playbook
description: "用于 BSP 移植涉及启动链、驱动依赖、构建环境和迁移风险时规划与验证；不用于未授权的设备刷写或纯源码阅读。"
version: 2.0.3
last_updated: 2026-11-20
triggers:
  - "BSP移植"
  - "板级移植"
  - "BSP适配"
  - "启动链"
  - "Bootloader"
  - "rootfs"
  - "secure boot"
non_triggers:
  - 仅业务代码改动
inputs:
  - 旧平台信息、新平台约束、runtime 类型、目标板 identity
outputs:
  - 移植步骤、验证矩阵、刷写授权 handoff、回退证据
constraints:
  - 先最小可启动，再扩展外设
  - workspace/build 权限不得推导真实设备 flash/storage-write 权限
  - 真实刷写必须有 target identity、explicit authorization、recovery 和 post-write verification
---

# adk-bsp-porting-playbook

## Goal
完成 Linux/RTOS/bare-metal BSP 迁移，保留 last-known-good 恢复锚点；源码构建与真实设备写入分别授权。

## Prerequisites
- 明确 `linux-embedded | mcu-rtos | mcu-baremetal`、SoC/MCU、board revision、boot/storage、范围和里程碑。
- 获取原理图、芯片手册、参考 BSP、真实 toolchain、设备 identity 与恢复入口。

## Workflow
1. **冻结身份**：记录 old/new platform、runtime、board/device、source commit 与 last-known-good artifact/hash。
2. **差异矩阵**：比较 CPU、clock/reset、memory map、IRQ、DMA/cache、pinmux、storage/boot 与 peripheral IP。
3. **启动链**：Linux 为 ROM/SPL/bootloader → kernel/DT → rootfs；RTOS 为 ROM/bootloader → vector/startup/BSP/HAL → scheduler；bare-metal 为 startup/linker → clocks/memory → application。
4. **适配与构建**：workspace 内最小化 DTS/config/startup/linker/HAL/board diff。从项目核实目标架构、toolchain、配置及 image/DT 入口；不能从 host 或通用例子猜目标。jobs 同时受 CPU/CI 配额与 RAM/单任务峰值约束；缺测量先保守选值，不能直接用 `nproc`。超时按项目基线。
5. **设备写 handoff**：flash/storage-write 前填完整下方 payload，缺项 `blocked`；只交给获授权 operator，不输出直接刷写命令。
6. **启动与外设**：保留完整 boot evidence，确认目标 stage 到 console/shell/heartbeat；成功后按依赖逐项开外设，每步保留可回退配置。
7. **回归**：验证启动、稳定性、关键功能、功耗/实时性；量产放行交给 production-field readiness。

## Commands
仅适用于已核实的 Linux GNU make/Kbuild + GCC 新配置。变量均来自目标项目：source/output 为绝对路径；output 父目录存在且目录未创建；ARCH、工具链前缀、板级 defconfig、image 和可选 DT 目标已核实。先核编译器 `--version`/`-dumpmachine` 与目标 ABI。其他 runtime、LLVM 或厂商包装器用其真实入口。

```bash
# verified-linux-kbuild:
set -euo pipefail
: "${BSP_SOURCE_DIR:?}" "${BSP_OUTPUT_DIR:?}" "${BSP_ARCH:?}"
: "${BSP_CROSS_COMPILE:?}" "${BSP_DEFCONFIG:?}" "${BSP_IMAGE_TARGET:?}" "${BSP_BUILD_JOBS:?}"
[[ -f "$BSP_SOURCE_DIR/Makefile" ]] || exit 2
[[ "$BSP_BUILD_JOBS" =~ ^[1-9][0-9]*$ ]] || exit 2
[[ "$BSP_OUTPUT_DIR" = /* ]] || exit 2
mkdir -- "$BSP_OUTPUT_DIR" # 不用 -p；拒绝覆盖已有目录/配置
build_args=(-C "$BSP_SOURCE_DIR" "O=$BSP_OUTPUT_DIR" "ARCH=$BSP_ARCH"
            "CROSS_COMPILE=$BSP_CROSS_COMPILE" "-j$BSP_BUILD_JOBS")
make "${build_args[@]}" -- "$BSP_DEFCONFIG"
build_targets=("$BSP_IMAGE_TARGET")
[[ -z "${BSP_DT_TARGET:-}" ]] || build_targets+=("$BSP_DT_TARGET")
make "${build_args[@]}" -- "${build_targets[@]}"
```

失败保留现场，不清空重跑。已有 `.config` 迁移先保存原件，用项目 oldconfig/olddefconfig 流程核新符号与差异，不用 defconfig 重置。DT 用项目目标保留预处理/include 依赖；独立 DTS 确认无这些依赖才单调 `dtc`。用 `file`/ELF headers 核目标架构/ABI，裸 `.bin` 对应其 ELF 来源；`sha256sum` 记录配置及产物，文件名不证明架构。

## Evidence Template
```md
- Runtime: linux | rtos | bare-metal
- Target Identity: board_rev / device_id / SoC-or-MCU
- Platform Diff / Boot Chain / Source Changes:
- Build: source_commit / ARCH / toolchain_version-and-target / config_hash / output_dir
- Budget: jobs / CPU-quota / RAM / peak-per-job-or-conservative-basis
- Commands + Exit Codes / Artifact Hashes:
- Last-known-good Rollback Anchor:
- Live-device Handoff:
  - required: yes | no
  - operation: flash | storage-write | none
  - target_identity:
  - artifact_sha256:
  - target_partition_or_region:
  - explicit_authorization:
  - recovery_path:
  - post_write_verification:
- Boot / Device Enablement / Regression Evidence:
- Gate Result: pass | needs-fix | blocked
```

## Failure Handling
- host 构建/配置失败不升级到设备写；operator 报写入/启动失败时停止 mutation，执行已声明 recovery/rollback 再二分定位。
- 新外设引入不稳定时回到最后可启动配置并隔离问题。

## Quality Gate
- 配置与构建身份/目录一致；每个里程碑有产物、验证与阻塞证据，最小启动成功才扩外设。
- 构建或 release-preparation 权限不授予设备写；写前须有 explicit authorization、完整 handoff 与回退，生产/现场放行须独立 readiness gate。
