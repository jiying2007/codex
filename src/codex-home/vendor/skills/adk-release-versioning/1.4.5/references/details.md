# adk-release-versioning — 补充参考资料

按需读取；不授予发布、安装或远端写入权限。

## 完整发布历史（Bash）

先由项目政策和实际发布记录核实基线身份；可解析的 tag 本身不是发布证明。定义下列函数后，首发调用 `release_history initial`，其他发布调用 `release_history since-release <已核正式发布ref>`。在目标仓运行，HEAD 为本次目标；输出非零时整份清单无效，保留错误，不改用另一个范围凑成功。

```bash
release_history() (
  set -euo pipefail
  case "${1-}:$#" in
    initial:1|since-release:2) ;;
    *) printf 'usage: release_history initial | since-release <verified-release-ref>\n' >&2; exit 2 ;;
  esac
  target=$(git rev-parse --verify 'HEAD^{commit}') || exit "$?"
  shallow=$(git rev-parse --is-shallow-repository) || exit "$?"
  [[ "$shallow" == false ]] || { printf 'incomplete history: shallow repository\n' >&2; exit 1; }
  base=INITIAL
  range=$target
  if [[ "$1" == since-release ]]; then
    base=$(git rev-parse --verify --end-of-options "$2^{commit}") || exit "$?"
    git merge-base --is-ancestor "$base" "$target" || {
      printf 'release baseline is not a verified ancestor of HEAD\n' >&2; exit 1;
    }
    range="$base..$target"
  fi
  printf 'base=%s\ntarget=%s\n' "$base" "$target" || exit "$?"
  git --no-pager log --no-show-signature --reverse --format='commit %H%n%B' "$range" --
)
```

按完整清单分类后写 Changelog，逐项保留去向；未知类型、正文 `BREAKING CHANGE`、revert 和非用户可见变更不能被过滤。先核变更是否仍生效，再决定版本影响。没有提交仅表示已核范围为空，不自动证明可发布。

## 语义版本规则 (SemVer)

格式：`MAJOR.MINOR.PATCH[-prerelease]`

| 变更类型 | 版本位 | 示例 | 说明 |
|---------|--------|------|------|
| Breaking change | MAJOR+1 | 1.0.0 → 2.0.0 | API 不兼容、删除功能 |
| 新功能 | MINOR+1 | 1.0.0 → 1.1.0 | 向后兼容的新功能 |
| Bug 修复 | PATCH+1 | 1.0.0 → 1.0.1 | 向后兼容的修复 |
| 预发布 | 后缀 | 1.1.0-beta.1 | 测试阶段版本 |

## 当前 ADK 发布边界

- 实际 Tag 和 GitHub Release 只由受保护 `main` 的 successful-main promotion 与 canonical release 自动生成。
- 不手动执行旧版 `git tag` / `git push origin <tag>` 示例，不移动不可变 Tag；升级必须先验证 source 版本、资产摘要和回退锚点。
