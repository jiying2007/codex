# PCR02 诊断架构 V4 结论归档（终态收口）

## 0. 归档信息
- 日期：2026-05-10
- 范围：`cmd_server`、`cli`、`modules/hdi`、`modules/api`、`modules/app`、`app_product_test`、`pcr02`
- 归档目标：沉淀 V4 终态架构结论，作为后续重构与验收基线

## 1. 架构结论（最终）
1. 控制面与执行面完全解耦：
- `cmd_server` 仅做 gateway/registry/router，不执行业务诊断逻辑。
- 业务命令执行只发生在业务进程侧 `app_diag` runtime。

2. 分层边界固定：
- `hdi -> api -> app` 单向依赖，不允许反向调用。
- 诊断能力按 owner 模块注册与下线，禁止聚合 provider 直接管理跨模块共享资源生命周期。

3. 生命周期语义固定：
- 统一通过 `MODULE_UP/DOWN`、`COMMAND_UP/DOWN` 建模可观测状态。
- 统一错误语义：无活跃 owner 返回 `no_active_handler`，不再保留 legacy 兼容语义。

4. 目录与命名收口：
- 业务 provider 不做多级目录嵌套，统一扁平化管理。
- 对外契约保持单轨，`modules/app/include` 与 `include/app` 保持一致发布。

5. 运维与测试路径固定：
- `cli` 只发 canonical payload。
- 静态门禁（命名/分层依赖）为持续门禁；运行验证按 APP/PT 两模式分开验收。

## 2. 当前落地状态（代码基线核对）
1. `app_diag` 已按终态目录组织：
- `modules/app/src/app_diag/framework`
- `modules/app/src/app_diag/provider`
- `modules/app/src/app_diag/ipc`
- `modules/app/src/app_diag/core`

2. provider 扁平化已落地（无二级嵌套）：
- `modules/app/src/app_diag/provider/app_diag_ai_provider.c`
- `modules/app/src/app_diag/provider/app_diag_perf_provider_{cpu,mem,sd,flash}.c`
- `modules/app/src/app_diag/provider/app_diag_uart_provider.c`
- `modules/app/src/app_diag/provider/app_diag_uart_maint_provider.c`
- `modules/app/src/app_diag/provider/app_diag_archive_maint_provider.c`

3. HDI/API provider 目录已归拢：
- `modules/hdi/src/hdi_diag/hdi_diag_{vi,ao,ai,os}_provider.c`
- `modules/api/src/api_diag/api_diag_{dvr,media,tick,event,msg,ws,wifi}_provider.c`

4. cmd node 命名已收敛到规范接口：
- `VSAPPDIAG_CmdNodeInit` / `VSAPPDIAG_CmdNodeDeInit`

## 3. 与 V4 设计的对齐结论
1. 已对齐项：
- 控制面/执行面边界清晰。
- provider owner 化方向已建立，目录与命名基本收敛。
- app_tool 主迁移路径已打通到 `diag.*` / `maint.*` 命令域。

2. 仍需持续压实项：
- 聚合逻辑残余需持续清扫，确保“每个模块独立 provider + owner 生命周期自管”。
- 运行验证（非静态）需要按 APP/PT 全链路回归完成一次基线签核。

## 4. 约束与守则（后续改动必须遵守）
1. 不引入 legacy 兼容分支，不新增双语义接口。
2. 不在 `cmd_server` 引入业务执行代码。
3. 不允许任意层跨边界直接调用上层能力。
4. 所有新增命令必须声明 owner、生命周期、错误语义和测试归属。

## 5. 后续执行清单（收口）
1. 补齐 owner 级运行验证记录（APP/PT 各一轮）。
2. 完成聚合残余清理审计并归档。
3. 将本归档作为 V4 终态基线，后续变更以增量 ADR 记录。

## 6. 关联文档
- `docs/project/07_diag_command_architecture_v4.md`
- `docs/project/08_diag_command_architecture_v4_development_plan.md`
- `docs/project/10_diag_command_architecture_v4_phase6_verification_release.md`
- `docs/project/10_app_tool_function_migration_checklist.md`
