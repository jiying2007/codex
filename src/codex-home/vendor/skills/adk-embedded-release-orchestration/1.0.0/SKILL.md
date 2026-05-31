---
name: adk-embedded-release-orchestration
description: 嵌入式全栈发布编排，覆盖 SoC、MCU、bootloader、SD 升级、OTA、NAS/产线发布、版本标签、制品包和非覆盖发布门禁
version: 1.0.0
last_updated: 2026-05-31
triggers:
  - "嵌入式发布编排"
  - "固件发布"
  - "OTA 发布"
  - "NAS 发布"
  - "产线发布"
  - "release bundle"
  - "SD 升级包"
  - "MCU 固件包"
non_triggers:
  - "普通语义化版本说明"
  - "仅写 changelog"
inputs:
  - 发布仓库、版本、构建脚本、固件制品、manifest、checksum、发布根目录、HIL/产测证据
outputs:
  - 发布图、制品清单、门禁结果、dry-run/publish 证据、回滚和剩余风险
constraints:
  - 默认禁止覆盖既有发布目录或标签
  - 不保存 NAS 密码、签名密钥、证书或私有 registry 凭证
  - 缺少真实硬件验证时不得声称硬件放行
---

# adk-embedded-release-orchestration

## Goal
- 把嵌入式发布从单点版本说明升级为跨构建、打包、校验、发布、产线交接和回滚的可审计流程。
- 适配 SoC、MCU、bootloader、rootfs、SD upgrade、OTA、factory/test guide 和现场维护包。

## Prerequisites
- 已确认发布源仓、版本号、制品类型、发布受众和发布根目录。
- 已确认是否允许真实发布；默认先 dry-run。
- 已明确 tag、manifest、checksum、release notes、rollback 的要求。

## Workflow
1. 建立发布图：SoC image、bootloader、partition、MCU bundle、OTA package、SD package、factory package。
2. 定义门禁：source sync、clean/no-clean、build、package、check、flash dry-run、HIL、tag、publish dry-run、publish。
3. 生成制品清单：路径、版本、hash、manifest、依赖、目标设备和受众。
4. 非覆盖发布：stage first；默认拒绝覆盖既有版本目录、tag 和 release bundle。
5. 凭证边界：NAS、签名、证书、registry 和 SSH 凭证只能来自运行环境，不写入 skill、docs、memory 或日志。
6. 产线可读：发布目录和 guide 应面向测试、生产和现场人员，不要求理解源码树。
7. 证据收口：记录每个命令、exit code、制品路径、hash、tag 状态和 publish 结果。

## Commands
```bash
rtk rg -n "build|package|ota|firmware|release|checksum|manifest|publish|tag" <repo>
rtk git status --short
<build-command>
<package-command> --dry-run
<check-command>
<publish-command> --dry-run
```

## Evidence Template
```md
status: pass | needs-fix | blocked
versions:
- soc:
- mcu:
- ota:
release_graph:
- <node -> artifact>
artifacts:
- path:
  sha256:
checks:
- build:
- package:
- check:
- flash_dry_run:
- publish_dry_run:
rollback:
risks:
```

## Quality Gate
- 发布前必须有 manifest、checksum、制品路径和版本证据。
- publish 前必须经过 dry-run 或人工确认。
- 缺少 HIL/真实板级验证时只能标 residual risk。
- 不得自动覆盖既有发布物、tag 或生产目录。
