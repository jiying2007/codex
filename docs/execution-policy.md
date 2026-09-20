# Execution Policy

Codex 的唯一任务执行策略面绑定 ADK 7.0.4 canonical Execution Policy v2。

- 配置：`manifests/execution_policy.json`
- exact engine：`tools/codex_assets/execution_policy/engine.py`
- exact contracts：`tools/codex_assets/execution_policy/contracts.py`
- Codex host adapter：`tools/codex_assets/execution_policy_adapter.py`
- CLI：`python3 -m tools.codex_assets execution-policy`

旧 `runtime-control` Python/CLI/config surface 已 hard-cut，不提供 alias、fallback、双读或双写。保留的 `runtime_control.*` 字符串仅是 ADK 冻结 wire schema 名称，不表示旧执行面仍存在。

Execution Policy v2 要求每个 goal 在 `goal.started` 时携带可验证 intake：task mode、request/routing digests、authority id 与 routing provenance。缺失 intake、使用 v1 policy、source-set blob 漂移或 behavior baseline 漂移均 fail closed。

`readonly`/debug/review 若没有受管 mode-authority verifier，不会自动获得较弱 artifact gate；canonical engine 会按 fail-closed 规则提升到 implementation artifact boundary。

入口示例：

```bash
scripts/execution-policy.sh goal start \
  --goal-id example \
  --token-budget 200000 \
  --time-budget-seconds 14400 \
  --success-criterion tests-pass \
  --required-evidence tests-pass \
  --open-items 1 \
  --task-mode implementation \
  --request-sha256 <sha256> \
  --routing-decision-sha256 <sha256> \
  --authority-id digital-worker \
  --decision-id <decision-id> \
  --source-id digital-worker \
  --source-version <version>
```

Journal 仅保存结构化事件和哈希，不保存 prompt/messages/content/raw cwd。当前 journal 位于 `~/.codex/execution-policy/`。
