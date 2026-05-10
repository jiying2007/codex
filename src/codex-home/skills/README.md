# Skills 激活层说明

`~/.codex/skills` 现在是**激活入口层**，不再存放第三方实体内容。

## 规则

1. `.system/` 保留系统技能目录。
2. 第三方技能通过软链接指向 `~/.codex/vendor/skills/...` 或 `~/.codex/vendor/plugins/...`。
3. 启停与版本由 `~/codex/manifests/skills.json` 与 `scripts/build.sh` 控制。

## 常用命令

```bash
# 构建指定 profile
rtk bash ~/codex/scripts/build.sh --profile solo-dev

# 预览应用计划
rtk bash ~/codex/scripts/plan.sh --target ~/.codex

# 应用到 ~/.codex
rtk bash ~/codex/scripts/apply.sh --profile solo-dev

# 完整检查
rtk bash ~/codex/scripts/check.sh
```
