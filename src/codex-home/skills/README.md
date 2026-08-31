# Skills 激活层说明

`~/.codex/skills` 现在是**激活入口层**，不再存放第三方实体内容。

## 规则

1. `.system/` 保留系统技能目录。
2. 第三方技能通过软链接指向 `~/.codex/vendor/skills/...` 或 `~/.codex/vendor/plugins/...`。
3. 启停与版本由 `~/codex/manifests/skills.json` 与 `scripts/build.sh` 控制。
4. `registry.csv` 是由 manifest 派生的索引；变更 skill 后以 `manifests/skills.json` 为准并重新 build。

## 常用命令

```bash
# 构建默认 token-lean profile
rtk bash ~/codex/scripts/build.sh

# 预览应用计划
rtk bash ~/codex/scripts/plan.sh \
  --target ~/.codex \
  --prune-stale \
  --output ~/codex/build/apply-plan.json

# 预览并应用同一份计划
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json --dry-run
rtk bash ~/codex/scripts/apply.sh --plan ~/codex/build/apply-plan.json

# 查询未常驻的长尾 skill
rtk bash ~/codex/scripts/skill-search.sh --query "<任务>" --summary-json

# 完整检查
rtk bash ~/codex/scripts/check.sh
```

## Profile 切换

默认 profile 是 `token-lean`。其他可选值为 `minimal`、`solo-dev` 和 `team-collab`。

查看当前 live profile：

```bash
rtk bash ~/codex/scripts/doctor.sh --scope live
```

快速切换，以 `team-collab` 为例：

```bash
rtk bash ~/codex/scripts/apply.sh \
  --profile team-collab \
  --target ~/.codex \
  --prune-stale \
  --plan-out ~/codex/build/apply-plan.switch.json
```

`build.sh --profile ...` 只生成 build，不会修改 live。切换到较小 profile 时必须保留 `--prune-stale`；切换成功后新开 Codex 线程，才能刷新已注入的 Skill/Agent catalog。需要先审计 plan、dry-run 或回滚时，按 `~/codex/README.md` 的“Profile 选择与切换”流程执行。

## 知识沉淀

当用户要求“知识归档”“日报归档”“会话总结归档”“排障结论归档”时，路由到 `adk-knowledge-archive`，固定归档到：

```text
~/knowledge-hub/domains/codex/archive/<topic>/
```

不要把知识材料放进 `~/.codex`、`src/codex-home/` 或 `control/`。

## 记忆整理

当用户要求“记忆整理”“整理 memories”“周期性整理记忆”时，路由到 `adk-memory-curator`。默认只生成审计报告：

```bash
rtk bash ~/codex/scripts/curate-memory.sh
```

报告固定进入 `~/knowledge-hub/domains/codex/archive/memory-curation/`；只有明确要求时才写入 `~/.codex/memories/.codex/curation-inbox/` 候选 memory。

记忆治理阶段：

- Phase 1：默认只归档和生成审计报告。
- Phase 2：人工确认后手动写入 memory 或 codex-agent-mem。
- Phase 3：会话开始读取 context，结束时归档并整理。

## 上下文压缩与会话接力

当用户要求“上下文压缩前处理”“会话接力”“恢复上下文”“resume prompt”时，路由到 `adk-context-compress-handoff`。

入口：

```bash
rtk bash ~/codex/scripts/context-preflight.sh
```

默认闭环：

- 生成 preflight 模板
- `session-wrap` 产出会话总结
- `adk-knowledge-archive` 归档总结
- `adk-memory-curator --dry-run` 生成记忆审计建议

## 多源搜索

当用户要求“多源搜索”“交叉验证”“资料核验”时，路由到 `multi-search-engine`。默认 `token-lean` 先用 `skill-search` 延迟发现，`team-collab` 直接激活；本地代码库问题仍优先读取仓库。

## 浏览器读取

当用户要求“浏览器查看”“打开网页读取”“微信公众号文章整理”时，路由到 `browser-reader`，并可按需使用受限 `agent-browser`。

边界：只读、用户手动验证、禁止绕过验证码、禁止自动登录/提交、禁止批量抓取。
