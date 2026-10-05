# ADK 重复导入的受管 README 身份

目标：移除 README 刷新对固定 `adk-skill-sources-7.0.31.json` 历史身份的依赖，连续升级时使用导入前受管 manifest 中每项 Skill 的 version/source_ref；提前拒绝 README 漂移，不从 README 自述推断或接受身份。

授权：仅指定隔离 Codex worktree 的 `tools/codex_assets/adk_source_import.py`、`tests/test_adk_source_import.py` 与本文。未修改原 `~/codex`、live、provider checkout、vendor、manifest、baseline fixture、CI 或版本；本轮仅临时 fixture 的确定性测试，无网络、模型调用、真实签名、正式 commit/push 或 live apply。共享资产由主线程整合。

实现：plan 在现有签名、保护文件及 source audit 后预检受管 README 的 installed blob/mode 和精确唯一 version/commit 行，并在每项计划记录 old_source_ref。apply 在首次写入前重新检查 README 并捕获旧 version/source_ref，确认计划的旧 version/source_ref/vendor_rel 仍匹配受管 manifest，随后将捕获身份传给刷新。刷新先验证整个 README 集合和 exact upstream projection，再更新本地包装文字及 installed/local-tree 身份。独立刷新只允许目标 commit 等于当前受管 source_ref。既有签名、source blob、保护文件、changed-skill 版本检查及导入资产选择保留。

负向基线：使用基线 `a03184f9b36975adba4d3f0e7bdf481363b1b118` 的原始 importer 与可销毁 fixture 重放 apply，旧历史 commit 与当前 README 不同，最后抛出 `local README provenance needs manual review: adk-example`。失败时 manifest 已改到 Skill `1.1.0`/新 commit，新 vendor 已存在，11 项文件字节已变化。该结果确认原来的 late failure/partial write；没有对正式工作区执行 apply。

回归：临时 fixture 连续进行 `1.0.0 -> 1.1.0 -> 1.2.0` 两次升级，验证各轮捕获 predecessor commit、README、installed metadata、source projection 与 local-tree digest，无历史 fixture 文件也通过。另覆盖未变化 Skill 版本的 commit 更新、README 自述漂移（即便 metadata 同步重绑也拒绝）、计划后 README 漂移、stale managed identity、独立刷新错误目标 commit，以及 verifier/trusted-root/source-blob/changed-version/protected-dirty 拒绝。

测试使用明确的 Git/签名边界 doubles，不生成 attestation，不证明真实 release 已验签；现有 source audit 回归仍使用自己的 exact Git fixture。最终定向验证由本轮新鲜执行记录交接，整体导入和 source-to-live 资格由主线程另行验收。

新鲜定向验证：本机 CPython `3.8.10` 执行 `rtk python3 -m unittest tests.test_adk_source_import tests.test_adk_skill_audit -v`，新导入回归 `12/12`、既有 audit `28/28`，合计 `40/40`，exit=0；CPython 3.8 grammar 检查和 `rtk git diff --check` exit=0。未执行真实签名导入或 live apply。

回滚：在隔离候选中恢复本轮三个文件的变更；已发生的 source import 应按原 owner 审查策略恢复导入前受管 manifest、registry、policy、lock 与 vendor 快照，不对用户 dirty 或 live 自动回退。本修复提前阻断 README 身份类失败，但没有把整个多文件 apply 改成原子事务；其他复制/I/O 失败仍可能需要从候选快照恢复。
