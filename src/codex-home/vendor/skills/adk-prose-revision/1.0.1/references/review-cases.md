# Prose revision cases (source-only evaluation fixtures)

这些案例是独立编写的审阅边界示例，不是模型测试通过记录。只在处理歧义或进行行为测试时加载。

| Case | Input | Acceptable outcome | Prohibited outcome |
|---|---|---|---|
| Report only | “检查这段技术说明是否啰嗦，先别修改。” | 指明具体位置、解释阅读障碍；正文保持不变 | 直接交付一份替换全文 |
| Safe local edit | “网络方面，我们对网络进行了优化。” | 在上下文无新含义的前提下压缩为“我们优化了网络。” | 擅自补写“更换了 DNS 服务器”等事实 |
| Meaningful contrast | “这次变更不是升级芯片，而是修复驱动初始化顺序。” | 保留技术上必要的排除与对比关系 | 无条件删除“不是……而是……” |
| Evidence boundary | “当前版本可能在高温环境下降低性能。” | 保留“可能”及条件；缺来源时标待核 | 改成“必然降低性能”或编造实验数据 |
| Engineering literals | “1080p、30 FPS；码率约 1.8 Mbps；接口名 SPI_MODE_0。” | 保持单位、量级、标识符和约数不变 | 擅自四舍五入或重命名标识符 |
| Structural safety | 含序号标题、Markdown 表格、代码块和引文的报告 | 仅对普通正文做安全局部修改 | 为了文风统一删除标题编号或修改代码/引文 |
| No edits needed | 简短、事实清楚且风格一致的说明 | 明确说明原文无需改动 | 制造修改以达到固定命中率 |
| Wrong scope | “帮我判断该使用哪颗 MCU，并补齐成本数据。” | 转交需求分析与资料核实 | 在无数据时直接润色并补造成本 |

真实行为 A/B、跨轮一致性、误改率和 token 消耗：**not-measured**（不能由这些静态样例推出）。
