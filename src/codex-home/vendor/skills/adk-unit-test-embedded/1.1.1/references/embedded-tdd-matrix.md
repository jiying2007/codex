# Embedded Full-stack TDD Matrix

## Test Level Decision

- Level: 0 | 1 | 2
- TDD required: yes | no
- Reason:

## Test Matrix

| Case | Layer | Type | Command | Expected |
|---|---|---|---|---|
| build-smoke | build | smoke |  |  |
| artifact-checksum | boot/image/rootfs | artifact integrity |  |  |
| host-unit-c-cpp | driver/component | happy path |  |  |
| cmake-ctest | component/application | regression |  |  |
| cross-build | silicon/board/OS | build |  |  |
| boot-smoke | boot chain/rootfs | smoke |  |  |
| flashing-smoke | board/flashing | smoke |  |  |
| linux-userspace | device application | smoke/regression |  |  |
| host-tool-test | upper-computer/tooling | unit/regression |  |  |
| qemu-sil | system | simulation |  |  |
| hil-confirmation | hardware/system | hardware confirmation |  |  |
| static-analysis | codebase | static |  |  |
| fault-injection | reliability | error path |  |  |
| ota-rollback | release/field | upgrade recovery |  |  |
| factory-diagnostics | production/field | production smoke |  |  |
| long-run | reliability | soak/stability |  |  |

## Red / Green Evidence

- Red command:
- Red result:
- Green command:
- Green result:

## Not Tested

- Gap:
- Reason:
- Follow-up:

## Evidence Requirements

- Boot evidence:
- Board/HIL evidence:
- Factory/diagnostics evidence:
- OTA/rollback evidence:
- Manual evidence owner:
