# 覆盖与恢复记录

每次调用返回 receipt，含 resource、revision、status、coverage，不含正文或凭据。这是单次读取回执，不是自动归档或全项目验收。

全局记录至少包含：authorized_scope、resources；每个资源记录 url、sheet_id/document、基线 revision、version_consistency（matched/changed/unknown）、planned、complete、partial_or_unknown、unread、resume、unsupported_embedded_resources；最后记录 whole_resource_complete。

完成判据：授权集合对象已列出，计划范围/块清单来源可靠；所有计划项得到完整实际覆盖，未读/未知/版本冲突为空；嵌入资源缺口独立报告。表格被裁剪不能按请求范围计完成，文档 excerpt 不是整个顶层块，单段 complete 不是整个对象 complete。

恢复时核对链接、对象、工作表、后端身份与版本；旧覆盖不能与新版本无标记合并。选择重读或明确混合版本的阶段性分析，保留坐标/块ID和缺口即可，不要求保存全部正文。需要长期记录时使用 Knowledge Provider 契约，临时回执不得称已归档。

输出模板：

| 资源/工作表 | 基线版本 | 计划范围/块 | 已完整覆盖 | 未读/未知 | 下一段/处理 |
|---|---|---|---|---|---|
| 用户授权对象 | 返回版本 | 可靠边界 | 实际完整并集 | 缺口清单 | 继续位置 |

非网格对象、隐藏/不可读工作表和未支持资源不能无声跳过，也不能替换成另一对象。版本变化须保留旧记录并说明失效范围。
