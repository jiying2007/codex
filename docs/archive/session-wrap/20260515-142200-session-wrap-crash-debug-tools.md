# 2026-05-15 会话收口：音频崩溃排查与 docs/tools 落地

## 一、目标与范围

本会话聚焦三件事：

1. 排查 `prog_pcr02` 相关 core（SIGBUS/SIGSEGV）并确认是否与 audio/wav 读流逻辑相关。
2. 修复 `modules/api` 音频读流健壮性问题（fd 判定、短读、EINTR、Read8 返回值）。
3. 建立跨模块可复用的崩溃排查资产（`docs/runbooks` + `tools/debug` + `tools/.codex/skills`）。

## 二、关键结论

1. 两个关键 core（`core-th_0x283855-913-12`、`core-th_0x283855-1038-17`）均显示主线程在 `audio_wav.c` 解析路径触发 `SIGBUS`，与 WAV chunk 解析链路高度相关。
2. `api_audio_player` 流层存在可导致错误数据传播/误判的健壮性缺陷，已修复并完成编译验证。
3. 已在 WAV 入口加入硬防御日志（`[WAV_GUARD]`），可直接输出 chunk 异常特征、seek 前后上下文，便于下一轮复现时快速定位。
4. 崩溃分析流程已产品化为脚本+runbook+skill，支持低 token 快速诊断。

## 三、代码改动（本仓）

### 1) 音频流层修复

- `modules/api/src/api_audio_player/stream/file/api_player_stream_file.c`
  - 修复 fd 判定边界：`fd=0` 不再误判失败；关闭逻辑改为 `>=0`。
  - `read/write` 改为循环处理短读短写，支持 `EINTR` 重试。
  - `open` 失败、`lseek` 失败路径更明确。

- `modules/api/src/api_audio_player/stream/api_player_stream.c`
  - `StreamRead8` 增加返回值校验，避免未初始化字节返回。
  - `ReadLe/ReadBe` 系列改为定长读取 + 宏解析，减少 1-byte syscall 并统一失败处理。

### 2) WAV 入口防御日志

- `modules/api/src/api_audio_player/parser/wav/audio_wav.c`
  - 新增 `_WAV_LogGuardChunk(...)`。
  - 在 chunk size 异常、seek 前、seek 失败回退、fmt 扩展 seek 前后增加 guard 日志。

## 四、文档与工具资产落地

### 1) runbooks（新增/增强）

新增：
- core 采集、fastpass、崩溃分诊、core-bin 配对、ASAN 离线符号化、崩溃包采集、SIGBUS 对齐排查、多线程关联分析。

增强：
- `gdb-debug-guide.md`：补充工具入口、关联流程。
- `asan-debug-guide.md`：补充离线符号化关联。
- `docs/README.md`：补齐主文档索引（含 asan/gdb/core 系列）。

### 2) tools/debug 脚本（新增）

- `gdb-core-fastpass.sh`
- `gdb-core-deeppass.sh`
- `core-env-snapshot.sh`
- `verify-core-match.sh`
- `collect-crash-bundle.sh`
- `asan-log-symbolize.sh`
- `summarize-gdb-fastpass.sh`
- `extract-crash-signature.sh`
- `match-build-artifact.sh`

### 3) tools 级技能体系

- `offline-gdb-core-debug`
- `asan-crash-triage`
- `sigbus-memory-triage`
- `crash-report-normalizer`

并已统一迁移公共技能到 `tools/.codex/skills`，`modules/api` 旧副本已清理。

## 五、验证结果

执行并通过：

1. `rtk make -j8 NC=1`（多次增量编译，目标改动文件已参与构建）
2. `rtk python3 docs/governance/check_docs_naming.py --changed-only`
3. `rtk python3 docs/governance/check_docs_schema.py --changed-only`
4. `rtk python3 docs/governance/check_agent_skill_consistency.py`
5. `rtk bash -lc 'bash -n tools/debug/*.sh'`

## 六、未决项 / 风险

1. 历史 core 有 `Source file is more recent than executable` 与 `core may not match executable` 提示，历史结论存在版本漂移风险。
2. 需要基于“当前修复后二进制”重新复现场景，验证 `[WAV_GUARD]` 输出与崩溃是否消失。
3. 若仍崩溃，应按 fastpass -> deeppass -> 签名提取 -> 材料打包流程继续推进。

## 七、下一会话建议起手

1. 复现一次当前场景，收集新 core 与 `[WAV_GUARD]` 日志。
2. 执行 `tools/debug/verify-core-match.sh` 确认 core 与 `*.debug.full` 配对。
3. 用 `gdb-core-fastpass.sh` + `summarize-gdb-fastpass.sh` 先出低 token 结论，再决定是否 deep pass。
