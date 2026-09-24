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

## 日常 CLI 与线程身份

Digital Worker 不是日常 CLI 的安装依赖。下方 `authority-id/source-id=digital-worker` 仅是显式采用该集成时的来源示例，不得照抄成实际未发生的授权或路由证据。普通项目记录实际采用的项目/资源治理来源，验证、审查和发布仍由项目规则决定；不能为了通过门禁伪造 intake。

在项目目录中执行门禁时，模块从资源仓加载，检查绑定当前准确线程，而不是按“最近更新”猜测其它会话：

```bash
(cd ~/codex && rtk python3 -m tools.codex_assets execution-policy \
  --thread-id "${CODEX_THREAD_ID:?current thread id required}" gate --event final)
```

没有当前线程 ID 时先核实实际会话，不能借用别的线程状态。`gate_allowed` 只表示该线程的本地执行策略结论，不等于项目测试、独立审查、设备验证或产品放行已经完成。CI 的外部 cwd `gate --help` 仅验证命令可解析，不是一次真实门禁通过。

入口示例（在 Codex 资源仓中、显式采用 Digital Worker 来源时）：

```bash
python3 -m tools.codex_assets execution-policy goal start \
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
