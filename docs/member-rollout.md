# 成员安装与现场验收

适用于 Ubuntu 上 `~/codex -> ~/.codex` 的现有资源链。默认 `default` profile；
不新增安装器、服务、Work/Run 系统或 Digital Worker 前置依赖。
维护侧的 Full Regression 负责全量测试，成员执行本机配置、计划、安装与使用验收。
仅安装资源不要求配置飞书 SDK/凭证；使用对应集成时再按其声明安装依赖。

## 开始前

在本机终端执行，停止正在修改同一资源目录的安装、同步和 Codex 会话；新资源不在
旧会话中热替换。需要 Git、Python、PyYAML 和现有脚本使用的 RTK。
不自动升级 Codex CLI、模型或系统软件，不调整内核、AppArmor 或沙箱权限。

维护者提供已通过三条主线 CI 的完整 Codex **源码 SHA**；ADK 版本号不是这个 SHA。
在当前 shell 设置 `CODEX_ASSET_SOURCE_SHA`。以下步骤拒绝脏工作区和非快进更新，
不会 reset、clean、stash 或替成员处置本地修改。构建产生的旧 lock 变更也先核对，
不要为了继续安装直接丢弃。

```bash
set -euo pipefail
: "${CODEX_ASSET_SOURCE_SHA:?set the reviewed full Codex source SHA}"
[[ "$CODEX_ASSET_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]
ROOT="$HOME/codex"
TARGET="$HOME/.codex"
PROFILE=default
test "$(git -C "$ROOT" branch --show-current)" = main
test -z "$(git -C "$ROOT" status --porcelain=v1 --untracked-files=normal)"
case "$(git -C "$ROOT" remote get-url origin)" in
  https://github.com/jiying2007/codex.git|https://github.com/jiying2007/codex|git@github.com:jiying2007/codex.git) ;;
  *) echo 'STOP: verify the source repository origin'; exit 1 ;;
esac
git -C "$ROOT" fetch origin main
git -C "$ROOT" merge --ff-only "$CODEX_ASSET_SOURCE_SHA"
test "$(git -C "$ROOT" rev-parse HEAD)" = "$CODEX_ASSET_SOURCE_SHA"
mkdir -p "$ROOT/.backups"
ROLLOUT="$(mktemp -d "$ROOT/.backups/member.XXXXXXXX")"
export ROOT TARGET PROFILE ROLLOUT
printf 'ROLLOUT=%s\nSOURCE=%s\n' "$ROLLOUT" "$CODEX_ASSET_SOURCE_SHA"
```

计划与原始备份保存在本地 `ROLLOUT`，每次使用新目录，不能用上一轮目录覆盖旧备份。
已经位于更新版本时也会因最后的 exact HEAD 检查停止，不把旧 SHA 误称为已部署。

## 1. 检查和预览：还不修改运行目录

```bash
set -euo pipefail
: "${ROOT:?}" "${TARGET:?}" "${PROFILE:?}" "${ROLLOUT:?}"
rtk bash "$ROOT/scripts/build.sh" --profile "$PROFILE"
rtk bash "$ROOT/scripts/doctor.sh" --scope repo
rtk bash "$ROOT/scripts/doctor.sh" --scope build
rtk bash "$ROOT/scripts/doctor.sh" --scope governance
(cd "$ROOT" && rtk python3 -m tools.codex_assets.adk_skill_audit --summary-json)
rtk bash "$ROOT/scripts/plan.sh" --target "$TARGET" --prune-stale \
  --backup-root "$ROLLOUT/backup" --output "$ROLLOUT/plan.json"
rtk bash "$ROOT/scripts/apply.sh" --plan "$ROLLOUT/plan.json" --target "$TARGET" --dry-run
```

确认目标、profile、copy/overwrite/delete 清单和备份位置。没有 `--overwrite`：
用户修改的普通文件默认保留，`config.toml` 继续按既有允许漂移边界处理。
其它资产冲突会在后续差异检查中暴露，不能用全局强制覆盖跳过处理。

符号链接在**资产叶子**位置可以是合法 Skill 入口；在目标根、受管子目录或备份父目录
位置则拒绝自动跟随。遇到 `directory symlink`，明确选择真实目录并重新生成计划，
不要自动删除链接；显式覆盖叶子链接时备份/替换的是链接本身，不写它指向的文件。
含“替换父目录且同时操作旧子路径”的计划也会阻断，不能制造安装后沿新链接清理的顺序。

本机缺失依赖、来源漂移或计划过期时，先解决相应问题并重新检查；不复用另一人的计划。
CI 的绿色结果不能替代这里的本机计划检查。这里也不把 doctor 通过解释成真实模型通过。

## 2. 应用同一计划，核对本机结果

阅读预览并接受其变更后，在同一个 shell 执行；换了终端则明确恢复真实 `ROLLOUT` 路径，
不要猜测“最新计划”。

```bash
set -euo pipefail
: "${ROOT:?}" "${TARGET:?}" "${ROLLOUT:?}"
rtk bash "$ROOT/scripts/apply.sh" --plan "$ROLLOUT/plan.json" --target "$TARGET"
rtk bash "$ROOT/scripts/doctor.sh" --scope all --target "$TARGET"
rtk bash "$ROOT/scripts/diff.sh" --target "$TARGET"
rtk bash "$ROOT/scripts/drift.sh" --target "$TARGET" --output "$ROLLOUT/drift.json"
rtk bash "$ROOT/scripts/plan.sh" --target "$TARGET" --prune-stale \
  --backup-root "$ROLLOUT/noop-backup" --output "$ROLLOUT/noop.json"
python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); sys.exit(0 if p["content_changes"] == 0 else 1)' "$ROLLOUT/noop.json"
```

`doctor/diff/drift` 成功且重复计划为零变化，才完成**本机资源安装验收**。
不上传认证、config 内容、原始会话或整个备份目录；报告 SOURCE、PROFILE、命令退出码、
变化数及未通过项即可。安装计划仍按原有 schema 保存，没有新增共享成员状态数据库。

## 3. 新会话和知识复用：单独验收

重新启动本机 Codex。在资源仓做一个不提交代码的真实 CLI 冒烟任务，例如：

> 使用实际安装的 adk-code-review-loop 审查 tests/test_member_install_paths.py。
> 先确认本会话读取的 SKILL.md 路径与版本，再运行该测试模块，给出风险与验证结果。
> 不修改文件、不提交、不发布、不连接设备；无法执行的部分明确说明。

这是模型实际读取资源和执行工具的冒烟，不等于业务功能或设备验收。
然后在项目 Issue/PR 上完成一个已有明确验收标准的真实缺陷/功能，记录项目提交、
构建/测试证据与接受结论；需要设备的结论不能由主机测试替代。

知识链复用现有 Adapter，不直接写 Hub 内部目录：

```bash
rtk bash "$ROOT/scripts/knowledge-provider.sh" status
rtk bash "$ROOT/scripts/knowledge-provider.sh" context \
  --cwd "$PWD" --query '本次项目任务相关的既有知识与适用条件' \
  --task-type debug --context-budget small --limit 3 --summary-json
```

在业务项目目录执行 context；`status=READY_FOR_CALL` 仅证明入口存在，实际 context
仍要返回可用路由/来源。只把有证据的经验送入 reviewing candidate；另一任务实际使用
且核对适用条件后，才记录知识复用成功。缺少权限或来源时不伪造主体、候选成功或 PASS。

Ubuntu 沙箱能力另用 `check-bwrap-capability.sh --require-modern` 验证。
失败不能用 `danger-full-access`、调整 sysctl 或关闭沙箱来充当通过。
该检查也不代替 Codex CLI 自己的实际执行验证。

## 回退与停止

仅撤销仍处于本轮安装维护窗口的计划：先停止会话/同步，确认应用后没有需保留的人工
修改，再预览和执行原计划回滚。现有 rollback 不是合并工具；有安装后改动时停止，
先在本机保存和核对差异，不能直接覆盖成员的新工作。

```bash
rtk bash "$ROOT/scripts/rollback.sh" --plan "$ROLLOUT/plan.json" --dry-run
rtk bash "$ROOT/scripts/rollback.sh" --plan "$ROLLOUT/plan.json"
```

回滚恢复运行目录文件，不会自动回退 `~/codex` 的执行策略源码，也不还原模型会话。
需要完整版本回退时，使用上一轮**实际安装记录中的源码 SHA/profile**恢复匹配源码，
再 build、doctor/diff/drift。不能把升级前碰巧存在的源仓 HEAD 当成旧 live 的来源证据。
不知道上一安装版本时先停止，不猜测、不重标历史记录。

路径检查会在 plan/apply/rollback 及每次文件操作前检查目录形态，但不是内核级文件锁。
安装窗口不得有并发目录移动或同步；高风险共享目录不能因这些单元测试通过而当成
支持任意并发写入的事务系统。CI 临时 HOME 的证据始终与成员现场验收分别记录。
