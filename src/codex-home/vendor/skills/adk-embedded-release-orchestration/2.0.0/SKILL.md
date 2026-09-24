---
name: adk-embedded-release-orchestration
description: 嵌入式全栈发布编排；release preparation、真实 publish 与 live-device flash 分权治理
version: 2.0.0
last_updated: 2026-09-17
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
  - 发布仓库、版本、构建脚本、固件制品、manifest、checksum、发布目标 identity、HIL/产测证据
outputs:
  - 发布图、制品清单、门禁结果、dry-run、授权边界、publish/flash 证据、回滚和剩余风险
constraints:
  - 默认只到 release-preparation，不因准备发布而自动获得 publish 或设备刷写权限
  - 默认禁止覆盖既有发布目录、标签或设备分区
  - 不保存 NAS 密码、签名密钥、证书或私有 registry 凭证
  - release-target publish 与 live-device flash 必须分别显式授权
---

# adk-embedded-release-orchestration

## Goal
- 把嵌入式发布升级为跨构建、打包、校验、交付、产线和回滚的可审计流程。
- 让 `prepare`、`publish`、`flash/deploy` 成为不同 authority domain，避免一条发布指令隐式跨越外部系统和真实设备边界。

## Prerequisites
- 已确认发布源仓、版本、制品、发布受众、release target 和设备族 identity。
- 已明确本轮最多允许 `prepare | publish | flash/deploy` 中哪些 operation；未声明时仅允许 prepare/dry-run。
- 已明确 manifest、checksum、release notes、rollback/recovery 和 HIL/产测证据要求。

## Workflow
1. **发布图**：列出 source→build→package→verify→stage→publish→device-deploy 节点，并标每个节点 owner/authority。
2. **制品 identity**：记录路径、版本、SHA-256、manifest、依赖、目标设备族和受众。
3. **prepare gate**：完成 source sync、clean/no-clean decision、build、package、check、HIL/field evidence lookup、publish dry-run；此阶段不产生真实外部发布或设备写入。
4. **非覆盖策略**：stage first；已存在版本目录、tag、bundle 或目标路径默认 fail-closed，除非独立 overwrite policy 明确授权。
5. **publish escalation**：真实 NAS/registry/release target 发布前必须冻结 destination identity、artifact digest、explicit authorization、rollback/withdraw path 和 post-publish verification。
6. **device escalation**：真实 flash/OTA/deploy 前必须另行冻结 device/board identity、分区/region、explicit authorization、recovery image/path 和 post-write verification；publish 授权不能复用为 device authorization。
7. **凭证边界**：NAS、签名、证书、registry、SSH 和设备凭证只由运行环境注入，不写入 skill/docs/memory/log。
8. **产线交接**：guide 面向测试/生产/现场人员，明确允许的 artifact、设备范围、失败停止条件和恢复入口。
9. **证据收口**：分别记录 prepare、publish、flash/deploy 的 actor、命令、exit code、artifact digest、target identity 与结果。

## Commands
```bash
rtk rg -n "build|package|ota|firmware|release|checksum|manifest|publish|tag" <repo>
rtk git status --short
<build-command>
<package-command> --dry-run
<check-command>
<publish-command> --dry-run

# 以下不属于默认 release-preparation authority：
# <publish-command> <explicit-destination>
# <flash-or-deploy-command> <explicit-device-id> <artifact>
```

## Evidence Template
```md
- Status: pass | needs-fix | blocked
- Versions / Source Identity:
- Release Graph:
- Artifact Manifest + SHA-256:
- Preparation Checks: build / package / check / HIL / publish_dry_run
- Publish Escalation:
  - required / target_identity / actor / explicit_authorization / rollback_or_withdraw / post_publish_verification
- Device Escalation:
  - required / target_identity / partition_or_region / actor / explicit_authorization / recovery / post_write_verification
- Credential Boundary:
- Remaining Risks:
```

## Failure Handling
- prepare 失败时不得继续 publish/flash。
- destination identity、artifact digest 或授权不一致时停止真实 publish。
- device identity、分区、recovery 或写后验证任一缺失时停止 flash/deploy。
- 外部发布成功但验证失败时执行 withdraw/rollback；设备写失败时进入预定义 recovery，不继续批量推进。

## Quality Gate
- 发布前必须有 manifest、checksum、artifact identity 和版本证据。
- `release-preparation` 只允许生成/检查/stage/dry-run，不等价于真实 publish 或 live-device write。
- publish 与 device mutation 必须是两份独立授权证据，不能由同一宽泛“发布批准”隐式覆盖。
- 缺少 HIL/真实板级验证时不得声称设备放行；不得自动覆盖既有发布物、tag、生产目录或设备分区。
