# 成员安装与现场验收

适用于 Ubuntu 上 `~/codex -> ~/.codex` 的现有资源链。默认 `default` profile；
不新增安装器、服务、Work/Run 系统或 Digital Worker 前置依赖。
维护侧的 Full Regression 负责全量测试，成员执行本机配置、计划、安装与使用验收。
仅安装资源不要求配置飞书 SDK/凭证；使用对应集成时再按其声明安装依赖。

## 开始前

在本机终端执行，停止正在修改同一资源目录的安装、同步和 Codex 会话；新资源不在
旧会话中热替换。需要 Git、**Python >=3.11**、PyYAML 和现有脚本使用的 RTK。
持续回归覆盖Python3.11/3.12。ADK7.0.31原始源码要求>=3.11，`datetime.UTC`也是
3.11新增；不能用Python3.10、修改vendor源码或安装同名datetime包绕过要求。
不自动升级 Codex CLI、模型或系统软件，不调整内核、AppArmor 或沙箱权限。

### 0. 在更新源仓之前确认解释器

`python3 -c 'import yaml'`仅验证PyYAML，不验证解释器版本。现有shell入口调用PATH
中的`python3`；每次新终端先激活正确venv。仅安装另一个Python、设置shell alias或
仅设置`PYTHON`变量不会自动修复这些入口。用3.10创建venv仍是3.10。

以下子shell仅准备源仓外的独立环境，不修改系统Python、资源源仓或`~/.codex`。
选取已安装且CI覆盖的3.11/3.12；不存在就停止，先通过机器认可的软件来源安装独立
解释器和venv支持。不会自动增加PPA、sudo安装软件或删除已有环境。

```bash
(
  set -euo pipefail
  PY=""
  for candidate in python3.12 python3.11 python3; do
    candidate_path="$(command -v "$candidate" 2>/dev/null)" || continue
    if "$candidate_path" -c 'import sys; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)' 2>/dev/null; then
      PY="$candidate_path"
      break
    fi
  done
  test -n "$PY" || { echo 'STOP: install independent Python 3.11/3.12 with venv support; keep system Python unchanged.'; exit 1; }
  VENV="$HOME/.venvs/codex-assets"
  if [ ! -e "$VENV" ]; then
    "$PY" -m venv "$VENV"
  fi
  test -f "$VENV/pyvenv.cfg"
  "$VENV/bin/python3" -c 'import sys; assert sys.prefix != sys.base_prefix; assert sys.version_info[:2] in ((3,11),(3,12)), sys.version'
  "$VENV/bin/python3" -m pip install --disable-pip-version-check 'PyYAML==6.0.2'
  printf 'ENV_READY=%s\n' "$VENV"
)
```

只有上面成功输出`ENV_READY`才继续；已有venv版本错误时保留它并换用新的明确目录，
不要直接覆盖。准备子shell不会改变当前终端PATH，必须在当前终端显式激活：

```bash
. "$HOME/.venvs/codex-assets/bin/activate"
hash -r
python3 -c 'import sys,yaml; from datetime import UTC; assert sys.version_info >= (3,11); print("PYTHON="+sys.executable); print(sys.version); print("PYYAML="+yaml.__version__)'
rtk python3 -c 'import sys,yaml; from datetime import UTC; assert sys.prefix != sys.base_prefix; print("RTK_PYTHON="+sys.executable)'
```

两次解释器输出均应属于上述venv；任何一步失败都停止，不继续预览。只在venv内安装
PyYAML，不为仅使用vendored策略引入完整ADK其它依赖，不用sudo/pip全局安装。

维护者提供已通过三条主线 CI 的完整 Codex **源码 SHA**；ADK 版本号不是这个 SHA。
在当前 shell 设置 `CODEX_ASSET_SOURCE_SHA`。以下步骤拒绝脏工作区和非快进更新，
不会 reset、clean、stash 或替成员处置本地修改。构建产生的旧 lock 变更也先核对，
不要为了继续安装直接丢弃。

```bash
set -euo pipefail
python3 -c 'import sys; assert sys.version_info >= (3,11), sys.version; import yaml; from datetime import UTC'
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

### 历史未受管资产不是安装失败后的自动删除授权

`--prune-stale` 只处理旧 managed state 已记录的路径及显式退役路径，不代表自动清空
运行目录。旧版导入或手工安装可能留下没有记录的入口和旧版本目录。现在 plan/apply
都会对照下一版 build 扫描这些资产；未被现有删除动作覆盖时，必须在写入前停止。
不把未知路径写入新清单假装已管理，不使用 `--overwrite` 或扩大忽略规则制造通过。

已经出现 `plan_state=applied dry_run=0` 后又被 doctor 报未管理资产时，安装动作已完成，
但整个目录尚未验收。不要重跑同一批写操作、重新构建、覆盖原计划或立刻回滚。
先保存原计划与备份，检查 build/live 差异和实际未受管清单。不能仅凭名字推断这些
目录都是可删除的历史文件；它们可能包含成员自定义内容。

可接受的恢复方式是明确审阅清单后，将**仅这份清单**完整隔离到 `~/.codex` 之外，
记录原路径、目标路径和文件/链接身份，保留原始内容，不跟随链接、不删除。
必须排除当前 build/managed 路径、受保护内容及活动入口依赖；目录形态或清单变化时停止。
保持单次维护窗口；中断按隔离记录恢复，不覆盖恢复目的地已存在的新文件。
隔离后重新运行 doctor/diff/drift 和重复计划；零变更不单独证明不存在未受管资产。
待真实任务确认不再依赖隔离内容后，再另行决定归档或处置，不自动清除隔离区。

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
