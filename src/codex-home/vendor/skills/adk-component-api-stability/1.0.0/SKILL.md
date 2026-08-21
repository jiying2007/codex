---
name: adk-component-api-stability
description: 组件 API 稳定性治理
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "API稳定性"
  - "组件API"
  - "接口兼容"
non_triggers:
  - 私有一次性脚本
inputs:
  - 当前 API、调用方清单
outputs:
  - 兼容性评估与演进策略
constraints:
  - 破坏性变更必须附迁移路径
---

# adk-component-api-stability

## Goal
- 建立 API 稳定性基线，控制破坏性变更风险。
- 确保嵌入式组件（HAL/BSP/协议栈）接口在版本迭代中的向后兼容。

## Prerequisites
- 收集 API 使用方清单与版本分布。
- 明确当前语义不稳定点与历史兼容问题。
- 准备 ABI 检查工具（abidiff / abi-compliance-checker）。

## Workflow
1. **盘点公开 API**：按稳定（stable）/试验（experimental）/废弃（deprecated）分类。
   ```bash
   # 扫描公开符号
   nm -D --defined-only libcomponent.so | grep " T " | sort
   # 扫描头文件导出
   rg -n "^(int|void|struct|enum|typedef).*\(" include/component/*.h
   # 查找废弃标记
   rg -n "deprecated|DEPRECATED|__attribute__.*deprecated" include/
   ```
2. **ABI 兼容性检查**：对比新旧版本的 ABI 差异。
   ```bash
   # 使用 abidiff 检查 ABI 变化
   abidiff libcomponent_old.so libcomponent_new.so
   # 使用 abi-dumper + abi-compliance-checker
   abi-dumper libcomponent_old.so -o old.abi
   abi-dumper libcomponent_new.so -o new.abi
   abi-compliance-checker -l libcomponent -old old.abi -new new.abi
   ```
3. **API 版本管理**：遵循语义化版本（SemVer），维护变更日志。
   ```bash
   # 检查版本号定义
   rg -n "VERSION|version" include/component/version.h
   # 生成变更日志
   git log --oneline --since="$(git log -1 --format=%ai v1.2.0)" --grep="api\|API\|breaking"
   ```
4. **兼容测试设计**：老版本调用方回归验证。
   ```bash
   # 编译兼容性测试
   gcc -I include/ -L . -lcomponent -o compat_test_v1 tests/compat_v1.c
   # 运行兼容回归
   ./compat_test_v1 && echo "ABI compatible" || echo "ABI broken"
   ```
5. **评估兼容影响**：识别破坏性变更和行为变更。
6. **制定演进策略**：版本号规则、弃用窗口（>= 2 个版本）、迁移提示。
7. **形成发布建议**：可放行条件与阻断项。

## Commands
```bash
# 公开 API 扫描
rg -n "public|export|__attribute__.*visibility.*default" <component_path>

# ABI 检查
abidiff libcomponent_old.so libcomponent_new.so
abi-compliance-checker -l libcomponent -old old.abi -new new.abi

# 版本号检查
rg -n "#define.*VERSION" include/

# 兼容性测试
<project-test-cmd> --filter compatibility

# 符号导出检查
nm -D --defined-only libcomponent.so | c++filt | grep " T "

# 头文件依赖分析
gcc -M -I include/ src/component.c | head -20
```

## Evidence Template
```md
- API Inventory:
  | Category | Count | Examples |
  |----------|-------|---------|
  | Stable | __ | func_a, func_b |
  | Experimental | __ | func_x |
  | Deprecated | __ | func_old (remove in v2.0) |
- ABI Check Result:
  - Added symbols: __
  - Removed symbols: __ (BREAKING)
  - Changed signatures: __
- Breaking Changes: [list with migration path]
- Deprecation Window: [version range for removal]
- Consumer Impact:
  | Consumer | Version | Affected APIs | Action |
  |----------|---------|---------------|--------|
  | module_a | v1.2 | func_x | update call |
- Compatibility Test Result: [pass/fail + log link]
```

## Failure Handling
- 调用方影响无法评估时，强制 `needs-fix` 并扩大审查范围。
- 若发现未声明的 breaking change，阻断发布并补迁移文档。
- ABI 检查工具不可用时，手动对比 `nm` 符号表输出。
- 若废弃 API 仍有活跃调用方，延长弃用窗口并发送通知。

## Quality Gate
- 必须区分行为变更与签名变更。
- 必须给出调用方影响清单和迁移路径。
- 兼容回归结果必须可追溯到命令或报告。
- ABI 检查必须零未声明的 breaking change 方可发布。
- 版本号必须遵循 SemVer 规则（MAJOR.MINOR.PATCH）。

---

## 健壮性规范

- **输入验证**: 执行前校验所有必要输入是否存在且格式正确
- **重试策略**: 外部命令失败时最多重试 3 次，指数退避（1s, 2s, 4s）
- **超时控制**: 单步操作超时 30 秒，整体流程超时 300 秒
- **异常隔离**: 单个步骤失败不阻塞其他独立步骤
- **日志记录**: 关键操作记录命令、退出码、耗时
