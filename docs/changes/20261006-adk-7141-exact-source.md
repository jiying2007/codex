# ADK 7.14.1 exact-source 消费升级

Codex 从 ADK 7.12.4 消费基线更新到 canonical ADK 7.14.1。受管来源统一绑定公开发行的 exact commit、tree、manifest blob 和实际归档 digest；42 个 Skill、9 个 Agent 和四个 Execution Policy 文件经过逐字节比较，受管上游内容没有变化。

- Provider：`jiying2007/agent-dev-kit`。
- Release：`v7.14.1`。
- Commit：`19dafa7c61355c04c08e87adcf3eae6946020f92`。
- Tree：`8cdc8d4e022184e3f247a963610fe10d76732bb2`。
- Manifest blob：`00d1e3b9977642c432335596daea5c8f007179a3`。
- Annotated tag object：`3672d025b16269ab4d00bdff8142fa1e0df59731`，解析到上述 commit。
- `agent-dev-kit-7.14.1.tar.gz` SHA256：`e32fd405b6cef3698ff8148a79dddac647a7f96f1bc3be727c842bd242f50826`。

来源通过既有 signed source importer 导入。真实 promotion evidence 来自 main push CI run `37380832484` attempt 2，签名使用 issuer `https://token.actions.githubusercontent.com`、identity `https://github.com/jiying2007/agent-dev-kit/.github/workflows/ci.yml@refs/heads/main`，并以受审 trusted-root 文件验证；实际下载归档与签名 evidence、发布 API digest 和 release contract 相同。官方自动 tag/release run `37382573380` 成功，公开发行非 draft、非 prerelease。

首次 producer 的 Python 3.11 临时 Git fixture 清理失败仍是真实历史；同源码授权重跑成功，没有修改上游测试。cleanup writer 未被确认，重跑成功不构成根因定位结论。

更新包括 provider lock、Skill/Agent source identity、Execution Policy baseline、consumer validator/test pins，以及 `adk-skill-sources-7.14.1.json`。历史 fixtures 保留。Agent mirror 从 7.12.4 路径迁到 7.14.1，旧受管路径退休。Skill 的局部 README 仅更新其来源 commit，继续由 consumer 拥有；上游 mirror 正文与四个 policy 源文件保持 exact。

验证要求：来源审计与两个 binding validator；Python 3.8 和 3.11 全部 unittest；候选 `team-collab` build 及 repo/build/governance doctor。每项新鲜结果和 source/build hashes 交接给独立审查者。运行设置 `CODEX_OFFLINE_HERMETIC=1`，避免真实 provider/model 网络调用。

配置变化限于上述来源身份和 Agent 版本路径，没有调整 runtime profile、并行上限、模型、provider operation 或信任校验条件。当前候选只构建 `team-collab`，后续 source-to-live 仍须由获授权的整合者依次执行 plan、apply dry-run、apply 和 check，绑定 source/build/target receipt。

回滚应在独立工作树恢复本变更前的受管 source set，再重新 build 同 profile，并通过既有 managed plan/backup/rollback 流程处理 live；不得手改 mirror 或覆盖用户非受管资产。候选源码测试和 build 不代表 live 已采用、跨域产品资格或 owner 放行。
