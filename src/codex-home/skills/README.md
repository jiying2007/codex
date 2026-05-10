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

## 知识沉淀

当用户要求“知识归档”“日报归档”“会话总结归档”“排障结论归档”时，路由到 `knowledge-archive`，固定归档到：

```text
~/codex/docs/archive/<topic>/
```

不要把知识材料放进 `~/.codex`、`src/codex-home/` 或 `control/`。

## 记忆整理

当用户要求“记忆整理”“整理 memories”“周期性整理记忆”时，路由到 `memory-curator`。默认只生成审计报告：

```bash
rtk bash ~/codex/scripts/curate-memory.sh
```

报告固定进入 `~/codex/docs/archive/memory-curation/`；只有明确要求时才写入 `~/.codex/memories/.codex/curation-inbox/` 候选 memory。

记忆治理阶段：

- Phase 1：默认只归档和生成审计报告。
- Phase 2：人工确认后手动写入 memory 或 codex-agent-mem。
- Phase 3：会话开始读取 context，结束时归档并整理。

## 多源搜索

当用户要求“多源搜索”“交叉验证”“资料核验”时，路由到 `multi-search-engine`。该 skill 仅在 `team-collab` profile 激活，用于需要外部证据的问题；本地代码库问题仍优先读取仓库。

## 浏览器读取

当用户要求“浏览器查看”“打开网页读取”“微信公众号文章整理”时，路由到 `browser-reader`，并可按需使用受限 `agent-browser`。

边界：只读、用户手动验证、禁止绕过验证码、禁止自动登录/提交、禁止批量抓取。
