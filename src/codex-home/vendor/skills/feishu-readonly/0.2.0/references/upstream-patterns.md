# 上游设计参考与采纳边界

核验日期：2026-10-15。仅吸收机制与验证原则，没有导入这些项目的实现代码或新增运行时依赖。官方CLI仍固定为manifest登记的v1.0.97及二进制SHA；upstream main可能已改变参数、路径规则或身份流程，不视为本机命令契约。

| 来源 | 核验材料 | 采用方式 |
|---|---|---|
| larksuite/cli | https://github.com/larksuite/cli/blob/main/skills/lark-drive/references/lark-drive-workflow-knowledge-organize-discovery.md | 显式续页状态、稳定资源去重、分页未完成不宣称完整；本地不扩大为目录抓取 |
| Scrapy | https://docs.scrapy.org/en/latest/topics/jobs.html | 一个任务一个隔离状态、恢复队列与去重；本地使用严格JSON，不采用pickle或cookie缓存 |
| rclone | https://rclone.org/commands/rclone_check/ | 传输成功与内容校验分开，缺失/不一致独立报告；本地哈希仅证明下载表示一致，不冒充远端原文件哈希 |
| Unstructured | https://docs.unstructured.io/open-source/concepts/document-elements | 资源、快照与位置元数据跟随证据；不引入其解析/OCR依赖或推导未验证页码 |

这些是设计依据，不能证明具体飞书资源可访问或已完整读取。上游身份切换、授权请求、云写、递归扫描及全权限建议不进入本地只读fallback。

验证分层：
- Host单测：覆盖并集、缺口、重叠、状态绑定/损坏/并发、受控JSON、错误恢复与证据定位。
- 已授权真实对象：原用户提供的Wiki及其同一底层文件，可验证源文件预览与恢复；不为了补矩阵猜测其他私有资源。
- 原生docx/表格、多维表格、PDF/Office转换预览各自需要真实授权对象回执；模拟测试不能替代服务端资格。
- 不支持的格式/缺版本/缺可靠块清单保留缺口，不将候选实现写成全格式支持。
