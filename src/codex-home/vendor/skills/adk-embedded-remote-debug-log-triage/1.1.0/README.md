# adk-embedded-remote-debug-log-triage

嵌入式设备端远程调试与日志取证 skill。覆盖 SSH、ADB/logcat、串口、GDB remote、调试探针、分层连通性、设备失联恢复、部署前身份与授权门禁、boot/dmesg/应用/OTA/prog 日志、core dump 线索、HIL 分阶段扩大、健康恢复和下一步探针。

## Provenance
- Owner: `agent-dev-kit`
- Source: ADK 原生实现，吸收 `~/codex` 本地 `embedded-log-triage`、`embedded-core-dump-triage` 和 PCR02/SigmaStar 调试历史经验，并抽象为平台中立流程。
