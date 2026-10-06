# ADK 8.0.0 精确来源消费升级

从已发布7.14.2升级到 canonical jiying2007/agent-dev-kit 的 immutable v8.0.0，main commit2c5bd3574c660c5d71bd7e71502977f8cadcf0ad，tree de25cff5da1725b2dbbad44c47080fd7e9d219a7，manifest blob b3481fadd6b9a7a8391c14aba3e2986bd9c1d6f8；实际公开归档 SHA256 9712f4e43898727264d528b0a7051ae1c4d6074d39f1f5d7cf0062e471dbf291。

main CI37411676809 attempt1 全9项通过，tag/Release流程37412113614成功。annotated tag410819a2ec2db0f4b2a9a35b0a75403094d230bc解析到该main；Release immutable=true、draft=false、prerelease=false。固定官方workflow identity、GitHub OIDC issuer与受审trusted-root验签Verified OK；归档hash与API、签名promotion evidence及release contract一致，不使用候选commit或本地重建作为producer。

使用既有signed importer 分别plan/apply、生成新source fixture及刷新31份consumer README。42个Skill changed_skills为空；9个Agent正文与7.14.2逐字节相同；四个policy原文无diff。来源锁、Agent版本路径、consumer adapter/test基线和当前文档同步前移；旧fixtures、source历史、LICENSE、profile、权限、模型、并行与MCP声明保留。

上游8.0.0的MAJOR变化为维护CLI退役无审查 --apply 并迁移到只读计划，安全descriptor不足的平台拒绝相关安装/receipt回滚；迁移说明位于exact上游 docs/changes/20261006-comprehensive-contracts/design.md。Codex此包消费的Skill/Agent/Execution Policy内容未改变；不添加维护executor或不安全fallback。

本地验收为来源/binding审计、支持Python完整unittest、team-collab build及repo/build/governance doctor和独立只读冻结复审。最终证据在source外记录；实际commit/push/托管检查/merge与完整同计划source-to-live后续单独验证，不由本文件提前声明live或产品资格。真实模型未调用，~/codex五项用户修改与journal不进入候选。

回滚保留7.14.2 exactsource与历史fixture/备份，通过受管source-to-live恢复；不手改上游mirror或live，不恢复旧版本runtime alias。
