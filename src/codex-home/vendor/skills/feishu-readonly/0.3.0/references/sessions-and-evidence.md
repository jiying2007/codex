# 会话、覆盖与审查证据

## 使用方式

单次stateless命令继续兼容。需要恢复时选择唯一任务名；一个session绑定一个授权链接、一个选定资源和固定后端身份，不跨任务复用。

```bash
rtk bash ~/codex/scripts/feishu-read.sh read --url '<文件或Wiki链接>' --session '<任务名>' --file-length 1500
rtk bash ~/codex/scripts/feishu-read.sh status --url '<同一链接>' --session '<任务名>'
rtk bash ~/codex/scripts/feishu-read.sh read --url '<同一链接>' --session '<任务名>' --resume
```

- 文件自动保存已返回字符区间、完整表示哈希和模式；resume固定模式/哈希并读取第一个缺口，不要求手工携带偏移。
- 表格必须从明确的工作表和可靠边界建立计划：首次调用加--sheet-id和--target-range A1:Z200。自动窗口满足100行/26列/2000格限制；partial/unknown不记完整覆盖，先拆小重试。范围完成不等于整个工作表/工作簿完成。
- docx先catalog，固定版本并取得可靠的全部顶层块清单，包含无标题正文；resume逐块读取。目录有无ID正文、截断或无法确认清单时保留缺口，不循环请求同一不可核验目录。大单块超预算/嵌入资源缺口不自动判整篇完成。
- resume不能同时带手工窗口；可设置max-chars调整输出预算。同一session不能更换资源、版本/哈希、表示或目标范围；变化时开始新session。
- 完成后的resume会复核绑定快照：文件重新取得表示并校验哈希，表格用目标内最小窗口核当前版本，文档复核固定原生版本；不是强制读取最新文档修订。status不联网，只代表已记录快照。
- 三次无覆盖进展后停止自动推进，按blocking_reason修正范围/预算/权限，必要时新建任务；不凭等待时间清空失败计数。
- display_truncated只表示状态展示取前32项，covered_count/missing_count是总数；完整性基于全部内部记录计算，不把展示截短误作内容完整。

## 状态与权限

操作状态位于本机/tmp/codex-feishu-sessions-<uid>/，目录700、JSON/锁文件600，不接受任意输出路径。只记录规范链接、资源标识、CLI身份、版本/哈希、计划、覆盖区间、下一步与错误类别。没有正文、标题、凭据、认证URL、原始错误日志、cookie或pickle。

同一任务持有非阻塞锁；写入采用独立临时文件、fsync和原子替换。拒绝未知schema/字段、损坏JSON、超限、符号链接、硬链接、FIFO和非私有文件。该目录可能被系统清理，不承诺重启后永久保留；丢失后用新session重新建立证据。它是恢复状态，不是Knowledge Provider归档，不直接编辑文件修复状态。

dry-run不访问状态或凭据；status不创建网络会话。恢复前先核对显式URL和CLI身份，实际读取再校验Wiki底层资源与版本/哈希；变化后原记录保留为失效快照，不合并新内容。

## 结果解释

capabilities分别说明type_supported、read_path_available、access_status/permission_status、format_status、content_returned、coverage_status；存在路径不代表具备权限或支持该文件格式。

session.scope_complete表示该计划内全部范围已读；whole_resource_complete更严格。file的转换text-preview永远不能证明原文件全量；sheet只完成显式目标范围；docx有嵌入内容缺口时不闭环。脱敏窗口不计为原文件完整。

evidence为统一定位：
- resource：规范URL、实际类型/token、工作表；
- snapshot：原生revision或表示SHA256及表示类型；
- locator：文件字符范围及辅助行号、表格实际单元格范围、文档块ID/scope；
- coverage_status、content_redacted、limitations：声明证据边界。

输出审查发现时附上述定位和快照；事实给原文依据，推断说明条件，未读内容列缺口。不要保存或引用临时下载路径作为跨会话证据；不要把metadata-only、capabilities或运行时门禁通过替代业务审查。

## 错误恢复

error.recovery稳定给出retryable、retry_after_seconds、next_action。默认不自动重试，--retries最多2；仅短等待瞬时网络/服务错误在总时限内重试同一bot只读请求。限流默认建议等待60秒，当前调用不阻塞等待后循环。scope/访问拒绝不重复同一命令；文件auto可按已验证契约改用同身份source_file路径一次。

content_mismatch/revision_mismatch/session_mismatch使会话失效；新内容用新任务，不能手改哈希继续。preview_pending说明转换仍在生成，不等于格式不支持。认证和授权配置由管理员处理，不自动登录、申请权限或切换身份。
