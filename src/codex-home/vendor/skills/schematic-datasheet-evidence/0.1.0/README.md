# schematic-datasheet-evidence

原理图、规格书及IO表的证据读取与交叉核验，本地原创技能。

- Version: 0.1.0
- Source: local/codex
- Lifecycle: iterative-local
- Target: Codex受管vendor skill与skills激活入口

使用SKILL.md及按需references，定位助手位于tools/codex_assets/pdf_evidence.py，仅依赖现有Poppler pdftotext。通过工具机械测试不代表模型读图准确率；独立人工/CAD真值及行为盲测仍待完成。安装不授予设计签核、设备操作或云端写入权限。工具子进程读取实现当前仅验证POSIX/Linux。

第三方项目仅作为设计参考，未复制或执行其代码，来源边界见references/sources.md。长验证记录留在公开Knowledge Provider或临时交付中，不作为运行技能正文。
