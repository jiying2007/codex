# 任务与状态

- [x] 保护原 `~/codex` dirty；隔离候选逐字节纳入 9 文件差异，整份 diff SHA256 匹配。
- [x] 基线 Python 3.8 定向测试 6/6，repo doctor 0 errors/0 warnings。
- [x] 固定 ADK 7.12.4 main、Sigstore promotion、annotated tag 与 Release artifact 身份；只读审计 42 个启用 Skill 的差异。
- [x] 导入 42 个 Skill 的 exact source set、9 个 Agent 与 Execution Policy；来源/分发元数据审计、Agent 与 Runtime Binding 校验通过。
- [x] Python 3.8 全套 312/312、`team-collab` build、repo/build/governance doctor、针对 live 的 plan/dry-run 和完整 pre-apply gate 通过。
- [ ] Python 3.11/3.12 托管 CI 与独立审查；候选仍需提交、推送和 PR 门禁。
- [ ] 在目标计划安全且授权范围内执行 live apply、check、drift、no-op 与 rollback 锚点核验。
- [ ] 将 Codex commit/push/merge、Knowledge Provider reviewing candidate、模型行为和产品资格分别收口。
