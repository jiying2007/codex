# Knowledge Archive

`docs/archive/` 保存长期可复用的知识材料，不保存 Codex 运行态。

归档入口：

```bash
rtk bash scripts/archive-note.sh /path/to/note.md --topic topic-name
```

约定：

- 先脱敏，再归档。
- 默认复制，只有明确迁移时使用 `--move`。
- 每个 topic 目录由脚本维护 `index.md` 和每条材料的 `.meta.json`。
- 不归档 secrets、auth、session、logs、cache、tmp 和本机私有状态。
