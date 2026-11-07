# 近三个月技能优化落地

- 用户授权：除 ABI/链接诊断、AEC 实验评测两个新技能外，实施复审清单。
- 范围：Codex 本地资产、团队知识技能/模板、API 项目 DVR 技能；不改业务行为、不接设备、不提交/推送。
- 既有 dirty 属于用户；只做叠加修改，应用前逐路径审查；保留本机模型、trust、权限与认证。
- 验收分母：8 项；结构检查、行为测试、独立审查、受管 live 回读分别留证。

| ID | 交付与退出条件 | 状态 |
| --- | --- | --- |
| A | 挖掘按线程去重、香港时间、语音/电源分流、可选元数据覆盖；边界测试通过 | done：7项测试，元数据子代理仅分列，不宣称索引已关联排除 |
| B | 资产管理流程更新；双目录发现显式来源、同名优先级与负例通过 | done：显式白名单、managed优先、来源/hash及发现回归 |
| C | 周报只读查询和收尾状态经 Provider；写回仍受原采集主体门禁约束 | done：真实只读查询pass，facts合同与2项临时Hub集成通过 |
| D | 构建输入冻结、隔离、增量/clean 和失败恢复进入已有技能及模板 | done：技能1.1.0及合同/指南，团队全门禁通过 |
| E | API 项目 DVR 技能就地落地，覆盖预录/lease/降级及设备验证边界 | done：四文件及项目入口；模块边界检查通过，无业务/HIL声明 |
| F | 多仓保脏同步 workflow、授权边界、回执模板和发现路由可用 | done：workflow/recipe/模板/路由用例通过 |
| G | 原理图/引脚/软件一致性模板、使用入口和风险边界通过文档门禁 | done：schema/links与独立静态语义审查通过 |
| H | 定向回归、fresh review、build/doctor/plan/dry-run/apply/check 与 live 回读 | done：真实apply、六版本回读、零差异/漂移；post-apply完整check退出0，591 tests及四profile smoke通过 |

失败连续两次先更新假设；共享契约变更串行。每批只验证受影响范围，完整收口在 H。发现既有门禁失败时明确归属，不为通过检查清理现场或伪造证据。恢复以此表和实际 diff 为准，历史原文按需读取。

## 收口批次 H：验证路径重规划

实施范围冻结，保持8项验收分母。当前live实际为team-collab，default计划会切profile并删除既有入口；已改为保留实际profile的team-collab构建，同一计划copy44/overwrite8/delete0，config和Agent均保留。此批仅：等待单一完整check，核已冻结apply计划，应用并readback/doctor/diff/drift及最终门禁。不再增加技能或改变业务。

独立审查/root/review_rollout_code：whole-change+targeted复审，blocker/major/minor均0；九类guidance场景通过，非模型或设备验收。源码定向53项、Hub临时集成2项、团队90项与全门禁已有证据；Hub pytest未安装，不把unittest发现0项冒充原pytest套件通过。

原运行预算12M已触发stop，停止新增实现后将剩余批次收窄为上述验证/安装，预算调整为24M、原4h截止不重置。仅覆盖同一目标收口；不清零历史累计，不以最终PASS推导历史预算合规。

## 原线程恢复检查点

- 线程与goal以当前会话Execution Policy journal为准，progress/checkpoint revision3，open_items=0，goal completed，final gate pass。API项目技能已落地，Provider源码锁已更新并真实只读查询通过；无commit/push/设备操作。
- apply计划：`build/skill-rollout-plan.json`，SHA256 `b18ec4f15f7a578b6f6318f5b00e1a42db737f0cfd377bf84e4c8ccf85f2104e`。现有team-collab，copy44/overwrite8/delete0；仅6技能版本、别名、registry和managed state。
- repo/build/plan/dry-run工件已登记。config原hash `bfc4172fd96e78d84ea286b67f7238fd4060ab65d99a900d34092d354df0e68e`；apply后hash不变，配置、Agent、认证、既有dirty保留。原计划真实apply退出0，effective_content_changes52。
- 宿主压缩后准确原线程apply gate通过；doctor零错误零警告、diff和drift为零，六技能版本已回读，重复计划copy0/overwrite0/delete0。post-apply完整check退出0，591项测试与四profile smoke通过。首次扫描误报内部标识，移除后整条检查复跑通过，扫描规则未放宽。8项验收均完成。
- Provider源码/验证结论已ARCHIVED/reviewing，operation `e0cd4cedaf557da316a4b7ceadcb5dd4585f4be73acc8bf6debd37941fbc7dcb`。安装后验证另获ARCHIVED/reviewing回执，operation `6d93ac80c90193fc50bc01c506c6ba457b47617257f02b27742c17c1173441df`，content SHA256 `db2067ad86d870e4a28486693448c0fe3be40d42384a15ba68d270ae2d197ce1`。同一活动receipt `skills-optimization-20261103`已按原hash修订为done，status=pass/applied=true，回执SHA256 `fbdecea88dd06cd939a69da89ca7ec9331fda0ee1e264c1fc6042905f94fbc6b`。不将reviewing候选视为owner批准。
