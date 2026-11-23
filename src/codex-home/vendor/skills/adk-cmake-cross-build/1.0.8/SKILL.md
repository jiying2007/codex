---
name: adk-cmake-cross-build
description: "用于嵌入式 CMake 工程的交叉编译、工具链配置与多目标构建排障；不用于无 CMake 的构建系统或直接设备部署。"
version: 1.0.8
last_updated: 2026-11-20
triggers:
  - "CMake"
  - "CMake交叉编译"
  - "CMakePresets"
  - "CMake工具链"
non_triggers:
  - 与构建无关的需求分析
  - Autotools缺少aclocal
  - Makefile-only 工程
inputs:
  - toolchain 文件、构建目标
outputs:
  - 构建配置方案
constraints:
  - 必须区分 host/build/target
---

# adk-cmake-cross-build

## Goal
复现目标 CMake 交叉构建，区分构建与执行。

## Prerequisites
核 host/build/target、权限和目录归属。测试需 CTest ≥3.21 和 host Python 3 标准库；compile-only 不需 Python。

## Workflow
1. 选 `ADK_BUILD_MODE=preset|manual`。preset 名称可不同，但 `configurePreset`、`binaryDir`、configuration 须匹配；否则按核实参数手工配置。
2. 复用前对照本次期望与旧构建证据：toolchain 路径/内容、compiler/target/sysroot/ABI、generator/configuration。核旧 cache、`CMakeFiles` 下的 `CMakeSystem.cmake`/`CMake*Compiler.cmake`、编译命令/日志；cache 新路径或 configure 成功不证明身份已变。
3. 同身份才增量复用；变化或旧身份无法证明时换新任务自有 binaryDir 及匹配 preset，保留旧 cache/log。不硬改旧 cache 或盲清目录；`--clean-first` 不切换配置身份。
4. 核 `host-unit|compile-only|emulator|board-runner`；emulator 配真实 `CROSSCOMPILING_EMULATOR`。缺后端用 compile-only；host 不证明板端运行。
5. 从本次 binaryDir/configuration 定位 `ADK_ELF`，不猜路径；目标工具核架构、段/符号/map。失败不消费旧产物。

## Commands
完成身份核对后在源码根运行，变量经核实、路径为绝对值。`ADK_CONFIG` 固定配置，`ADK_BUILD_JOBS` 按 CPU/RAM/CI 配额取正整数（`--parallel <resource-budget>`）。测试时 `ADK_EVIDENCE_DIR` 为已有任务证据目录，保留新 JUnit。
```bash
# cmake-build:
set -euo pipefail
case "$ADK_BUILD_MODE" in
  preset)
    cmake --preset "$ADK_CONFIGURE_PRESET"
    build_args=(--preset "$ADK_BUILD_PRESET") ;;
  manual)
    cmake -S "$ADK_SOURCE_DIR" -B "$ADK_BINARY_DIR" -G "$ADK_GENERATOR" \
      -DCMAKE_TOOLCHAIN_FILE="$ADK_TOOLCHAIN_FILE" -DCMAKE_BUILD_TYPE="$ADK_CONFIG"
    build_args=("$ADK_BINARY_DIR") ;;
  *) exit 2 ;;
esac
cmake --build "${build_args[@]}" --config "$ADK_CONFIG" --parallel "$ADK_BUILD_JOBS"
case "$ADK_TEST_BACKEND" in
  compile-only) printf 'target tests: not-run\n' ;;
  host-unit|emulator|board-runner)
    if [[ "$ADK_BUILD_MODE" == preset ]]; then
      test_args=(--preset "${ADK_TEST_PRESET:?}")
    else
      test_args=(--test-dir "$ADK_BINARY_DIR")
    fi
    report_dir=$(mktemp -d "$ADK_EVIDENCE_DIR/ctest.XXXXXXXX")
    report="$report_dir/ctest.xml"
    printf 'CTest report: %s\n' "$report"
    ctest "${test_args[@]}" -C "$ADK_CONFIG" --output-on-failure --no-tests=error --output-junit "$report"
    python3 - "$report" <<'PY'
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
cases = root.findall("testcase")
states = [c.get("status") for c in cases]
if root.tag != "testsuite" or len(cases) != int(root.get("tests", "-1")) or any(s not in ("run", "notrun", "disabled", "fail") for s in states):
    raise SystemExit("invalid CTest report")
if any(c.find(k) is not None for c in cases for k in ("failure", "error")) or "fail" in states:
    raise SystemExit("CTest failures in report")
if any(c.get("status") == "run" and c.find("skipped") is not None for c in cases):
    raise SystemExit("invalid passing status")
passed = states.count("run")
status = "pass" if passed == len(cases) and passed else "partial"
print(f"status={status} passed={passed} selected={len(cases)} skipped={states.count('notrun')} disabled={states.count('disabled')}")
if not passed:
    raise SystemExit("no executed passing tests: not-run")
PY
    ;;
  *) exit 2 ;;
esac
```
混合结果须核必跑用例；skip/disabled 不算通过，缺项保持 partial/blocked。`--no-tests=error` 不拒绝全部动态 skip。

产物工具用已核实目标路径：
```bash
# built-artifact:
set -euo pipefail
file "$ADK_ELF"
"$ADK_SIZE" -A "$ADK_ELF"
"$ADK_OBJDUMP" -h "$ADK_ELF"
```

## Evidence Template
```md
- Host / Target / Toolchain / Sysroot:
- Build Identity / Evidence / Reuse or New Directory Reason:
- Mode / Presets or Parameters / binaryDir / Configuration:
- Commands / Exit Codes / Duration / Logs / JUnit:
- ELF / Hash / Architecture / Sections / Size:
- Backend / Selected / Pass / Skip / Disabled / Not-run / Limitations:
```

## Failure Handling
依赖失败核 sysroot/`CMAKE_FIND_ROOT_PATH`；host 工具查找核 `CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER`；链接失败核 ABI，preset 失败核版本/引用链，不盲重跑。

## Quality Gate
目标构建成功；裸 bin 的 `file` 不证明 CPU，未运行测试记 not-run。只清理任务自有构建目录，保留日志及受版本控制的 toolchain。

依据：[Presets](https://cmake.org/cmake/help/v3.27/manual/cmake-presets.7.html)、[CTest](https://cmake.org/cmake/help/v3.21/manual/ctest.1.html)。
