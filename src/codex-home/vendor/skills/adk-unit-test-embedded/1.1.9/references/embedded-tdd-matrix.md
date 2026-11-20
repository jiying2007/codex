# Embedded Full-stack TDD Matrix

记录 Level（0/1/2）、TDD required（yes/no）与理由，只选适用层：

| 层次 | 候选检查 |
|---|---|
| 构建/制品 | build-smoke、cross-build、boot/image/rootfs checksum、static-analysis |
| 模块/应用 | host-unit-c-cpp、cmake-ctest、linux-userspace、host-tool-test |
| 系统/硬件 | qemu-sil、boot-smoke、flashing-smoke、hil-confirmation |
| 可靠性/现场 | fault-injection、ota-rollback、factory-diagnostics、long-run |

每个实际用例填写 layer/type、输入/expected、red/green command/result、artifact/raw path；未测记 gap/reason/follow-up。Boot、board/HIL、factory/diagnostics、OTA/rollback 分开留证，人工确认注明 owner。选择测试层不增加烧录或现场操作权限。
