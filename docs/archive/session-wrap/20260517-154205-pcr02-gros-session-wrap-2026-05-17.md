# PCR02 GROS 构建体系会话归档

## Source

- Project: `/home/leiwenjun/work/sigmastar/pcr02_ssc305_compile`
- Session Date: 2026-05-17
- Scope: 当前 Codex 会话中围绕 GROS 构建体系、模块边界、sysroot、快速构建与文档完善的工程收口
- Archive Type: session-wrap

## 本次完成

- 建立根目录 `build.sh` 作为统一构建入口，覆盖 `full`、`compile`、`kernel`、`kernel-ota`、`kernel-package`、`ota`、`package`、`app`、`sysroot`、`self-check`、`verify`、`lock`、`modules-status`、`modules-sync`。
- 将 GROS 应用构建切换到 CMake，应用入口收敛到 `SourceCode/sdk/verify/gros/apps/pcr02`。
- 将模块边界统一到 `SourceCode/sdk/verify/gros/modules/repos.csv`，支持 `repo`、`local`、`prebuilt` 三类模块。
- 将第三方依赖统一到 `SourceCode/sdk/verify/gros/3rdparty/libs.csv`，由 CMake 读取 include、link path、link libraries 和 runtime dirs。
- 生成并固化应用 sysroot 到 `SourceCode/sdk/verify/gros/sysroot/pcr02/ssc305`，同时生成 `.sysroot.lock` 记录来源 SHA 与关键目录 hash。
- 优化版本生成脚本 `scripts/generate-build-info.sh`，支持自检，只记录 main、GROS 和独立 repo 模块 SHA。
- 更新根 README，明确工具链、sysroot、模块仓、快速构建、CI/发布构建和版本信息。
- 新增 GROS 维护文档：`docs/module-guide.md`、`docs/troubleshooting.md`。
- 完善 `3rdparty/README.md`、`modules/proto/README.md`、`modules/wifi_manager/README.md`。
- 清理过程型 WiFi 文档，用终态模块说明替代。

## 关键决策

- GROS 聚合仓只维护聚合构建、平台边界、公共模块、应用入口、manifest 和文档。
- 独立模块源码按模块仓维护；GROS 不接管独立模块源码提交。
- 工具链独立仓管理，GROS 默认消费本地已拉取工具链目录，不把工具链解压内容直接纳入主工程。
- sysroot 作为应用独立编译基线保存在 GROS 本地目录；运行资源不放 sysroot，统一由 `resource` 安装到应用 release。
- 普通构建不隐式 checkout 或 pull；自动化构建应先完成源码更新，再用 `verify`、`lock`、`--require-upstream-sync` 做状态门禁。
- `ota` 和 `package` 只打包已有产物，不触发应用或系统重新编译。
- 旧 Makefile 模块构建入口和旧应用入口不作为终态边界保留。

## 涉及文件 / 模块

- Root: `build.sh`
- Root: `scripts/generate-build-info.sh`
- Root: `README.md`
- GROS: `CMakeLists.txt`
- GROS: `cmake/GrosManifest.cmake`
- GROS: `cmake/GrosPlatform.cmake`
- GROS: `cmake/GrosModules.cmake`
- GROS: `modules/repos.csv`
- GROS: `3rdparty/libs.csv`
- GROS: `docs/module-guide.md`
- GROS: `docs/troubleshooting.md`
- GROS: `3rdparty/README.md`
- GROS: `modules/proto/README.md`
- GROS: `modules/wifi_manager/README.md`
- Output: `SourceCode/project/pcr02_customer/etc/version.ini`

## 已做验证

- `bash -n build.sh scripts/generate-build-info.sh`：通过。
- `scripts/generate-build-info.sh /tmp/gros-version-test.ini --self-check`：通过，识别 tag `v1.1.8`。
- `./build.sh modules-status --allow-dirty`：通过。
- `./build.sh sysroot --allow-dirty --toolchain-root /tmp/gros/toolchain/ssc305 --no-copy-nfs`：通过，生成 `.sysroot.lock`。
- `./build.sh self-check --allow-dirty --toolchain-root /tmp/gros/toolchain/ssc305 --no-copy-nfs`：通过。
- `./build.sh verify --allow-dirty`：通过。
- `./build.sh app --allow-dirty --no-copy-nfs --toolchain-root /tmp/gros/toolchain/ssc305 --jobs 8`：通过。
- `./build.sh compile --allow-dirty --no-copy-nfs --toolchain-root /tmp/gros/toolchain/ssc305 --jobs 8`：完整编译通过，退出码 0。
- `./build.sh ota --skip-defconfig --allow-dirty --no-copy-nfs`：通过，生成 OTA 产物。
- 文档引用存在性检查：通过。
- 文档残留关键词扫描：无旧入口关键字输出。

## 当前工作区状态

- Root 仓有未提交改动，包括 README、`build.sh`、`scripts/`、版本文件、构建产物变更，以及若干构建入口删除项。
- GROS 子仓有未提交改动，包括 CMake/manifest/docs 新增、README 更新、旧 Makefile/旧入口相关删除项。
- 验证命令使用 `--allow-dirty`，因为当前会话本身产生了未提交改动。发布和 CI 不应使用该参数。

## 恢复风险 / 未决项

- 需要最终审查 root 与 GROS 两个 Git 工作区，确认提交边界，避免只提交新增文件而漏掉删除项。
- `docs/runbooks/asan-debug-guide.md` 原内容依赖旧 Makefile 构建路径，不应原样恢复；如需要 ASAN，应基于当前 `build.sh app` / CMake 重写。
- 完整编译日志存在平台既有 warning 和 SDK 打包阶段忽略型 `cp` 提示，本次未治理。
- OTA 产物生成命令通过，但产物内容仍依赖此前系统镜像状态；发布前应在干净工作区完整跑 CI 命令。

## 建议下一步

1. 对 root 仓和 GROS 子仓分别做 `git diff --stat` 与关键文件 review。
2. 在无 `--allow-dirty` 的干净环境跑 `./build.sh verify --require-upstream-sync`。
3. 生成 `sources.lock` 并做一次锁定构建验证。
4. 按仓库边界拆分提交：root 构建入口与 README 一组，GROS CMake/manifest/docs 一组，模块仓源码改动分别在模块仓提交。
5. 如需发布，使用不带 `--allow-dirty` 的 `compile` 或 `full` 构建。

## Commit 建议

- Root 仓：`refactor(build): 重构PCR02统一构建入口`
- GROS 仓：`refactor(gros): 切换CMake模块化构建`
- 文档补充可单独提交：`docs(gros): 完善构建与模块维护文档`
