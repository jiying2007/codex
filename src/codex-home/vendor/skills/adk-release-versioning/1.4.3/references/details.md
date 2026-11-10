# adk-release-versioning — 补充参考资料

此参考文件只提供可选背景、示例和检查提示；当前能力流程、权限、回退与放行结论以 `../SKILL.md`、Manifest 及运行时门禁为准。示例命令不得被解释为写权限授权。

## 语义版本规则 (SemVer)

格式：`MAJOR.MINOR.PATCH[-prerelease]`

| 变更类型 | 版本位 | 示例 | 说明 |
|---------|--------|------|------|
| Breaking change | MAJOR+1 | 1.0.0 → 2.0.0 | API 不兼容、删除功能 |
| 新功能 | MINOR+1 | 1.0.0 → 1.1.0 | 向后兼容的新功能 |
| Bug 修复 | PATCH+1 | 1.0.0 → 1.0.1 | 向后兼容的修复 |
| 预发布 | 后缀 | 1.1.0-beta.1 | 测试阶段版本 |

判断规则：
- 有删除/重命名公开 API → MAJOR
- 有新增公开 API → MINOR
- 仅修复内部实现 → PATCH
- 不确定时选择更保守的版本位

## 当前 ADK 发布边界

- 实际 Tag 和 GitHub Release 只由受保护 `main` 的 successful-main promotion 与 canonical release 自动生成。
- 不手动执行旧版 `git tag` / `git push origin <tag>` 示例，不移动不可变 Tag；升级必须先验证 source 版本、资产摘要和回退锚点。
