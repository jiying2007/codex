# OKR只读读取

适用于用户明确提供的租户OKR页面：
https://<tenant>.feishu.cn/okr/user/<网页用户ID>/?okrId=<用户周期候选ID>&periodId=<租户周期候选ID>

## 入口与映射

先inspect核验周期，再catalog查看目标ID，read读取目标与KR正文：

~~~bash
rtk bash ~/codex/scripts/feishu-read.sh inspect --url '<OKR链接>'
rtk bash ~/codex/scripts/feishu-read.sh catalog --url '<同一链接>' --max-chars 25000
rtk bash ~/codex/scripts/feishu-read.sh read --url '<同一链接>' --max-chars 25000
rtk bash ~/codex/scripts/feishu-read.sh read --url '<同一链接>' --okr-objective-id '<catalog返回的目标ID>' --max-chars 25000
~~~

网页ID只作为候选输入。默认以网页用户数字尝试API的user_id类型，查询该用户周期列表；必须由返回的owner.user_id、id和tenant_cycle_id分别核对API用户、okrId、periodId后，才读取目标。列表不匹配时返回okr_mapping_unverified，不能宣称网页ID通用兼容，也不尝试其他人员、其他身份类型或默认当前周期。

若已有经用户确认的API用户标识映射，可同时传--okr-user-id和--okr-user-id-type open_id|union_id|user_id。显式映射仍须通过相同周期双ID核验；不得由聊天身份、姓名或本机路径推断人员。只读入口不搜索通讯录、不获取其他人员数据，也不开放任意cycle-id覆盖链接。

## 内容与覆盖

- inspect仅返回匹配周期元数据；catalog读取目标列表但只输出元数据、不查询KR，目标接口随附的正文不进入catalog输出；read返回结构化富文本content/notes及score/weight等已有字段。
- score是分数，不是完成度。未读取指标或进展记录时，不能据score推导进度。
- 逐页读取周期、目标和每个目标下KR；精确去重，重复实体内容变化则停止合并。缺has_more、游标不前进、父对象不匹配或响应异常都不按完整处理。
- 每个集合最多10页、总计40次请求、1000项/集合、累计响应1 MiB；页大小--okr-page-size默认为100，可减小。仍受既有90秒总时限约束，不开启无限page-all。
- 正文超max-chars返回content_budget_exceeded及有限目标ID提示，不截断正文；先catalog再用--okr-objective-id读取。该选择仅对已验证周期清单中的目标有效。
- coverage.enumeration_complete只表示本次所选层级分页结束；scope_complete表示本次选择的目标/KR富文本均已返回。选单目标不代表整个周期完成。
- OKR v2未提供本入口可冻结的原生版本；snapshot_consistency=not-guaranteed。分页结束、update_time或本地接收时间都不证明一致快照。whole_resource_complete始终false。
- 未读取指标、进展记录、评论、对齐、附件和外链；不递归追踪。evidence按cycle/period/objective/key_result ID定位，并保留未读与快照限制。
- 首版不支持OKR的--session/status/--resume，不把文档版本/文件哈希契约套到OKR上。dry-run只校验输入，不加载凭据或联网。

## 权限与实现边界

transport仍为既有CLI子进程到open.feishu.cn HTTPS；固定bot身份，使用短期应用token。不读Agent可见的凭据/用户登录目录，不登录、不切账号、不改权限、不写云端。

白名单仅增加okr/cycles/list、okr/cycle.objectives/list、okr/objective.key_results/list，均已用固定v1.0.97的help/schema核验为read。未放开okr/*，也未加入创建、编辑、删除、评论等命令。

应用最低只读scope：okr:okr.period:readonly（周期）、okr:okr.content:readonly（目标/KR）。99991672或app_scope_not_applied属于application_scope_missing，由管理员开通并发布后再验证；开通scope不保证资源数据范围。没有权限回执时不得声称已读内容。

依据：固定CLI v1.0.97（manifest source_commit）的schema与内嵌lark-okr参考；官方可浏览说明：
- https://github.com/larksuite/cli/blob/main/skills/lark-okr/references/lark-okr-entities.md
- https://github.com/larksuite/cli/blob/main/skills/lark-okr/references/lark-okr-cycle-list.md
- https://github.com/larksuite/cli/blob/main/skills/lark-okr/references/lark-okr-cycle-detail.md

本地采用原生有界分页接口，以显式检查每个分页结束条件和父子关系；未直接使用隐式聚合shortcut，也未导入上游user身份切换或写能力。
