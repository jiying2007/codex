# 完整回归与隔离安装验证

`Runtime Binding Contract` 与 `Profile Context Contract` 保留聚焦合同检查。
`Full Regression` 在 Python 3.11/3.12 上安装声明依赖，发现全部 `test_*.py`，
然后在精确源码的隔离副本中执行真实 `check.sh --pre-apply --offline-hermetic`。
随后使用该计划执行原有 apply CLI、完整 post-apply check、零变更重复计划和 rollback CLI，
核对原始文件/符号链接集合及认证/session/system测试文件未改变。
任何测试 failure/error/skip/expected-failure 均不计为完整回归通过。

## 环境与依赖

- Python 3.11/3.12、Git、Bash。
- PyYAML 6.0.2，与现有合同 CI 一致。
- 飞书 SDK 复用 `mcp/requirements-feishu-codex-bot.txt` 的 `lark-oapi==1.7.1`，
  不复制版本定义、不用假模块替代 SDK，也不连接真实飞书。
- 完整 shell gate 使用真实 RTK 0.50.0；CI 固定官方 Linux x86_64 musl 发行包的
  SHA256 `bc2b8902b0d9c796c82ef45f16ae2307e17757afeca5ee156235a3dc7bda5f89`，
  先验证摘要再解压，不执行远程安装脚本。
- `ripgrep`、`bubblewrap` 来自 Ubuntu 24.04 包仓；记录实际包版本，不更改内核或放宽沙箱权限。

RTK 仍是现有 `check.sh` 的真实依赖，两个 Git fixture 也使用它；本轮先在完整环境
验证既有调用链，不通过创建同名透传脚本或跳过 fixture 隐藏依赖。SDK 单测只模拟
网络客户端，仍使用真实 SDK 请求构造。无模型、飞书或工程设备凭证进入此工作流。

## 本地复现

先在隔离虚拟环境安装声明的 Python 依赖，并确认上述 shell 工具可用：

```bash
python -m pip install 'PyYAML==6.0.2' -r mcp/requirements-feishu-codex-bot.txt
CODEX_OFFLINE_HERMETIC=1 python -m unittest discover -s tests -p 'test_*.py'
bash scripts/check.sh --pre-apply --offline-hermetic --target /your/disposable/home/.codex
```

`check.sh` 会更新当前源码副本的 build/派生 lock，并运行使用临时目录的 smoke；
应在干净隔离副本中运行，不把成员真实 `~/.codex` 当作测试目录。
依赖下载属于环境准备，不属于测试中的真实服务调用；offline-hermetic 是仓库已有
测试模式，不等于操作系统级网络隔离。

## 证据与边界

工作流保留精确 checkout SHA、PR head（如适用）、源码快照摘要、解释器/包版本、
全量测试数、原始日志和 shell gate 退出码。PR 的 merge-ref 与 head 分别记录。
依赖安装失败、发现测试失败、shell gate 失败分别保留真实结果。
`bwrap-capability.json` 保留宿主机能力实测；默认检查中的 warning 不变成沙箱资格。
GitHub runner 的用户命名空间探测失败时，不调整 sysctl/AppArmor 或禁用沙箱来制造通过。

通过完整回归只说明这一源码/依赖组合的自动化测试和隔离安装前检查通过，
不提升剩余 Skill 来源缺项，不表示成员 live 已更新、真实飞书/模型可用、
Digital Worker 正式证据合格或产品发布可放行。
