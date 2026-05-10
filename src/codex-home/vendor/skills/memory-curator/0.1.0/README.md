# memory-curator

周期性整理 Codex 记忆来源：`~/.codex/memories`、`AGENTS.md`、日报、会话总结、调研与排障结论。

默认只生成审计报告：

```bash
rtk bash ~/codex/scripts/curate-memory.sh
```

需要候选 memory 时：

```bash
rtk bash ~/codex/scripts/curate-memory.sh --write-memory-candidate
```

阶段模型：

- Phase 1：默认只生成归档和审计报告，不写入长期 memory。
- Phase 2：人工确认后手动写入 `~/.codex/memories` 或 codex-agent-mem。
- Phase 3：会话开始读取 context，结束时执行 `knowledge-archive + memory-curator`。
