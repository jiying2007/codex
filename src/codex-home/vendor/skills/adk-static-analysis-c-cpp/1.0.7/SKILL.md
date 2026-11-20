---
name: adk-static-analysis-c-cpp
description: "用于 C/C++ 静态分析告警分级、根因追踪与误报确认，并补最小复现；不用于把单次扫描当作完整功能或动态安全验收。"
version: 1.0.7
last_updated: 2026-11-20
triggers:
  - "静态分析"
  - "代码检查"
  - "lint"
non_triggers:
  - 快速原型验证
inputs:
  - 代码路径、规则集
outputs:
  - 缺陷报告与修复建议
constraints:
  - 高优先级缺陷必须阻断合并
---

# adk-static-analysis-c-cpp

## Goal
定位静态缺陷；冻结编译数据库、规则/严重级别，保留修复与误报依据。

## Target Eligibility（按目标分流，非一次跑全部工具）
- `linux-embedded`：kernel/userspace、交叉编译数据库、sysroot、工具支持。
- `mcu-rtos`：RTOS/ABI、compiler/linker script/变体；Zephyr Kconfig/Devicetree 不通用。
- `mcu-baremetal`：无 libc/OS、进程/文件系统时选告警、ELF/map、MISRA/静态路径。
- 缺匹配 compile_commands/toolchain/target 或授权记 `not-applicable / not-scanned`；安装/许可证/固件写入需独立权限。

## Workflow
1. 源变化选 translation units（TU）；头文件按依赖图选消费者，规则/宏/构建变化选目标。范围不明扫目标完整库，不跳过仅 `.h/.hpp` 变化。
2. 带 TU、target flags、header filter 扫描，记录位置/规则/级别；头文件保留构建上下文，优先内存/并发/UB。
3. 修复重跑受影响 TU，比对残留，不以修改行过滤代替路径分析；零告警不等于零缺陷。
4. 动态复核按需交已安装的 `adk-systematic-debugging` sanitizer 方法，不可用记 `not-run`。插桩/运行与扫描分开留证，UBSan 报警即使 exit 0 也不通过。

## Commands
按真实构建及 `.clang-tidy`、cppcheck/PVS 配置选工具：
```bash
clang-tidy -p build src/example.c
cppcheck --enable=warning,style,performance --project=compile_commands.json
```

## 缺陷严重级别映射
按风险映射：Blocker（越界/UAF/空指针）阻断或批准豁免；Major（溢出/未初始化/泄漏）有 owner/SLA；Minor 风格、Info 优化按需。

## CI 集成示例

受信 `BASE_SHA/HEAD_SHA` 与依赖选 TU；纯文档可免，仅无 .c/.cpp 变化不够。Ubuntu/CMake 例：真实 preset/toolchain 生成数据库，缺依赖图扫全库；工具规则不可替代。
```yaml
static-analysis:
  steps:
    - run: cppcheck --enable=warning --error-exitcode=1 --project=build/compile_commands.json
    - run: |
        set -euo pipefail
        python3 - <<'PY' | xargs -0 -r clang-tidy -p build --header-filter='.*' --warnings-as-errors='*'
        import json, os, sys
        from pathlib import Path
        rows = json.loads(Path('build/compile_commands.json').read_text())
        paths = sorted({str((Path(row['directory']) / row['file']).resolve(strict=True)) for row in rows})
        if not paths:
            raise SystemExit('no translation units: not-scanned')
        for path in paths:
            sys.stdout.buffer.write(os.fsencode(path) + b'\0')
        PY
```

交付数据库/规则、完成 TU/头文件范围、分级数量/blocker、误报/抑制依据及 re-scan delta。空库/缺工具/解析失败记 `not-scanned`，先修配置；仅改头文件的已知告警须使 CI 非零。PR/fork 受信触发、secret 隔离。依据：https://clang.llvm.org/extra/clang-tidy/ 。
