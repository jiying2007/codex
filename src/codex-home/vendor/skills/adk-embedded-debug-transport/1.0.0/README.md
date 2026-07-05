# adk-embedded-debug-transport

嵌入式设备调试通道治理 skill。覆盖 ADB/logcat、SSH、串口控制台、GDB remote、硬件调试探针和厂商 CLI 的连接边界、命令风险、证据采集和回滚锚点。

## Provenance
- Owner: `agent-dev-kit`
- Source: ADK 原生实现，采用通用设备调试通道模型；具体工具名不作为 skill 身份或路由锚点。
