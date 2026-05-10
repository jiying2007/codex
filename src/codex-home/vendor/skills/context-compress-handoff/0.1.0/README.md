# context-compress-handoff

标准化“压缩前 90 秒”与“会话接力”流程。

入口：

```bash
rtk bash ~/codex/scripts/context-preflight.sh
```

配套步骤：

- `session-wrap` 生成会话总结
- `knowledge-archive` 归档到 `docs/archive/session-wrap/`
- `memory-curator --dry-run` 生成审计建议
