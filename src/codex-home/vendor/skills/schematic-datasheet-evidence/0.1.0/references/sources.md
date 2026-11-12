# 参考来源与采纳边界

本候选为本地原创流程，未复制或执行第三方脚本，未安装依赖、启用MCP或访问外部模型。以下URL于2026-11-10在线核读；main是检索时的浮动参考，未固定exact commit，因此本清单不是受管导入回执。主线程采纳具体代码前须另行固定commit、许可证、依赖及安全审查。

| 来源 | 本候选吸收的原则 | 边界 |
| --- | --- | --- |
| https://github.com/yamadashy/pdfvision/tree/main/skills/pdfvision | 先检查读取异常，搜索坐标后看完整局部区域 | warnings缺失不保证正确；尚未安装或以F20验证 |
| https://github.com/settchan2003-design/kicad-schematic-review-skill | 每物理pin的规格合同、事实与判断分离 | 其解析脚本自称approximate pin-net mapping，不作权威网表 |
| https://github.com/ugeugeHigh/codex-skills-for-kicad/tree/main/kicad-codex-skills-public/kicad-schematic-review | 渲染、ERC、XML网表互补 | KiCad专用，不能直接处理当前未知SCH/DSN格式 |
| https://github.com/aklofas/kicad-happy/tree/main/skills/datasheets | 结构化规格、hash、类型及消费者信任边界 | 完整度评分不证明每个事实正确；不采纳其模型或运行资产 |
| https://github.com/Faradworks/Pinscope | 从原生网表建立器件邻域，对照手册页出发现 | 有API依赖及AGPL许可边界；仅借鉴架构 |
| https://pymupdf.readthedocs.io/en/latest/recipes-text.html | 旋转文字需要方向和quad，不能只看bbox顺序 | 几何定位不证明连线 |
| https://github.com/jsvine/pdfplumber | 字符/线条信息与可视化调试 | 表格/字符抽取不是电气拓扑解析 |
| https://github.com/D4NGYY/schematic-extractor | 明确适用密度、公布限制和低置信度 | 作者报告混合方案F1约0.56，非通用保证，不作权威CAD网表 |

本地助手只调用现有Poppler pdftotext，以stdlib解析XML并输出文字坐标。它不匹配引脚、不追线、不推断参数或电气能力；适用范围与第三方项目准确率分开。
