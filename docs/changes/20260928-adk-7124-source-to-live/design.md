# 设计与回退

1. 以 ADK annotated `v7.12.4` 的 exact commit、tree、Manifest blob、Release artifact SHA256 和 main Sigstore promotion 为来源锚点；不从参考仓或 Codex 运行目录反推身份。
2. 在本隔离候选先冻结原 main dirty 差异的 SHA256，随后逐项导入 42 个 Skill 的真实上游目录身份；内容变更的 5 项使用新版本目录，未变项仍核对其源 blob，不以仅改 `source_ref` 代替导入证明。
3. Agent 与 Execution Policy 分别核 exact upstream blob，更新 provider lock 与行为基线；运行现有 provenance、runtime binding、Python 3.8 和完整回归。
4. 源仓通过后依次 build、doctor、plan、dry-run；live apply 只接受同一计划，检查 unknown/protected paths、backup、回滚与 no-op。

回退锚点：Codex main 当前 HEAD 与既有 ADK provider lock 7.0.31；当前 `~/codex` 的 9 文件 dirty 差异另以完整 diff SHA256 `234c76f8d2187f5655320ed1d712f13cb0fe5b6c101d4e5c7f53c8ef0f07df55` 保留。任何 live 安装须另绑定实际 backup 和目标快照。
