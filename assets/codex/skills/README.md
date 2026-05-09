# Skills 激活层说明

`~/.codex/skills` 现在是**激活入口层**，不再存放第三方实体内容。

## 规则

1. `.system/` 保留系统技能目录。
2. 第三方技能通过软链接指向 `~/.codex/vendor/skills/...` 或 `~/.codex/vendor/plugins/...`。
3. 启停与版本由 `~/.codex/control/catalog/skills.csv` 和 profile 脚本控制。

## 常用命令

```bash
# 切换 profile（自动重建 skills 软链接）
~/.codex/control/scripts/activate-profile.sh ~/.codex solo-dev

# 体检
~/.codex/control/scripts/doctor.sh ~/.codex solo-dev
```
