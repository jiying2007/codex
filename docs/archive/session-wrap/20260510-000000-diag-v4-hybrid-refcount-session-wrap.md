# Session Wrap - Diag V4 Hybrid RefCount + Discover

## 范围
- 仓库：`xcrz_sigmastar_demo`
- 分支：`dev/pcr02`
- 主题：V4 终态下的生命周期重构与 CLI 自发现能力设计/计划

## 本次关键结论
1. 生命周期策略定稿：`Hybrid`（owner 驱动 + 外部 bring up/down）。
2. 防重策略定稿：`RefCount`（调度层 `owner_ref/ext_ref` + 模块内部 `init_ref` 双层防重）。
3. 优先借鉴点定稿：
- `ccli` 的发现先行（catalog/help）
- `version` 的分层版本清单（version matrix）
- `updater` 的事务化维护语义（prepare/verify/commit/rollback）
4. 明确必须修复：`VSAPIDVR_RecordInit/DeInit` 需模块内 RefCount 防重复初始化。

## 已落盘文档
1. 设计规格：
- `docs/superpowers/specs/2026-05-10-diag-v4-hybrid-refcount-discovery-design.md`
2. 实施计划：
- `docs/superpowers/plans/2026-05-10-diag-v4-hybrid-refcount-discovery-implementation-plan.md`（未提交）

## 已完成提交
- `0450506` docs(diag):归档V4混合生命周期发现设计
- `933cafe` docs(diag):补充V4代码规范与门禁约束
- `c8effc9` docs(diag):补齐C代码规范基线约束

## 当前工作树状态（与本主题相关）
- 未提交：
  - `docs/superpowers/plans/2026-05-10-diag-v4-hybrid-refcount-discovery-implementation-plan.md`

## 约束与边界（续跑必须遵守）
1. 严格遵守：`docs/common/c_coding_standards.md`。
2. `modules/app/include/app_diag` 与 `include/app/app_diag` 必须逐文件一致。
3. `cmd_server` 不得执行业务诊断逻辑。
4. 分层依赖固定：`hdi -> api -> app`。
5. 所有命令响应保持：`{"code","msg","data"}`。

## 下一步（执行顺序）
1. 提交计划文档（若确认）。
2. 按计划任务 1-7 实施：先契约，再 registry 状态机，再 cmd_node 命令，再 provider/DVR RefCount，再 CLI 收敛，再门禁归档。
3. 每个任务完成后跑对应静态门禁并 commit。

## 风险提醒
1. `api_diag_*_provider` 与 owner init/deinit 双入口并发时，若锁粒度不一致可能出现状态抖动。
2. `cli.c` 现有硬编码分支较多，收敛时易引入参数兼容回归。
3. 计划文件当前未提交，压缩后会话切换前建议先确认是否提交。
