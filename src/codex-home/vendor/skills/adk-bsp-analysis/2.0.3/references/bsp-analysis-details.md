# BSP Analysis Details

按需加载；不要在每次 BSP 任务中默认复制本文件。

## Search patterns
```bash
rg -n "module_init|builtin_platform_driver|of_match_table|compatible|probe" <bsp-dir>
rg -n "clk_|reset_|pinctrl|gpio|irq|dma|ioremap|readl|writel" <bsp-dir>
rg -n "TODO|FIXME|HACK|workaround|errata|WA" <bsp-dir>
git log --oneline -- <target-path>
git blame -L <start>,<end> <target-file>
```

命令只是候选 evidence collector；实际仓库/RTOS/bootloader 不匹配时应换用等价工具，不把命令本身当结论。

## Evidence depth
- L1：结构摘要、关键入口、结论。
- L2：相关 call/resource graph 与 history 摘要。
- L3：关键源码位置、hardware section、commit/patch evidence。
- raw：仅对争议/高风险结论保留原始日志或文档 pointer，不默认搬入主上下文。

## Typical resource graph
按问题相关性选择：
`boot/init -> registration -> match/probe -> resource acquisition -> clock/reset/power -> pinctrl/GPIO -> IRQ/DMA -> data path -> error/recovery`。

不要因为 checklist 存在就假设所有节点都适用。

## Hardware claims
- 寄存器、bit、时序：引用 datasheet/reference manual/errata 章节。
- source 与手册冲突：同时保留两方 evidence，并标记 `needs-evidence`。
- vendor workaround：追到引入 commit/issue/comment，区分 silicon errata、board workaround、legacy compatibility。

## History questions
1. 该逻辑何时引入？
2. 修复的是硬件限制、上游差异还是历史 bug？
3. 当前 target 是否仍需要？
4. 移除/迁移会影响哪些 consumer？
5. 有无回归或 field evidence 支撑？
