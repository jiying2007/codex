# Codex Session Bootstrap — 独立 L0/L1

本功能只负责会话输入、ADK 来源身份、Knowledge Provider 当前身份与 Runtime Binding 引用；不运行模型、不改写项目代码、不签发工程验收或产品发布资格。

## 两种模式

- **L0 / quick-assist**：默认，Knowledge Provider 不可用时明确标记 degraded
- **L1 / governed-engineering**：当前 Knowledge Provider 缺失或来源漂移时阻断

当前合同为 \`manifests/session_bootstrap.json\` v2.0，输出 \`codex-session-bootstrap/v2\`。运行时身份直接从已有 ADK provider lock 派生，不维护第二份领域控制面。

\`\`\`bash
rtk bash ~/codex/scripts/session-bootstrap.sh --cwd "$PWD" \
  --task "解释 SPI NAND ECC 代码" --summary-json

rtk bash ~/codex/scripts/session-bootstrap.sh --cwd "$PWD" \
  --task "排查 UBIFS 只读" --governed \
  --knowledge-root ~/knowledge-hub --summary-json
\`\`\`

`--mode L2`、`--formal`、`--engineering-task-package`、`--digital-worker-root` 及相关正式证据参数已移除；传入会直接失败，而不是降级为 L0/L1。旧 Runtime Receipt v2 schema 在 `schemas/` 仅保留**历史证据校验语义**，不再作为活动会话启动/签发路径。

需求、源代码、设备/HIL 测试、CI、审查、风险接受与发布依然归属于项目自身。需要更严格交付时使用项目已有的确定性 CI 和责任人审核，而不是恢复已退役的 Formal L2。
