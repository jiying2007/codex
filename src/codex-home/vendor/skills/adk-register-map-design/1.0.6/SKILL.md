---
name: adk-register-map-design
description: "用于芯片寄存器映射、位域权限和驱动接口文档设计；不用于直接对真实寄存器写入或代替外设时序调试。"
version: 1.0.6
last_updated: 2026-11-20
triggers:
  - "设计寄存器"
  - "寄存器映射"
  - "芯片适配"
non_triggers:
  - 应用层纯逻辑开发
inputs:
  - datasheet 摘要、硬件约束
outputs:
  - 寄存器表与访问规则
constraints:
  - 不得臆造寄存器语义
---

# adk-register-map-design

## Prerequisites
核芯片手册版本/章节、勘误、访问宽度、端序与读写副作用。

## Workflow
1. 建立寄存器清单：地址、访问权限、复位条件/有效位和来源章节；资料未查明与手册明确 undefined 分开记录。
2. 细化位宽、枚举和保留位；既有芯片依手册，自主设计须明确契约。
3. 记录写入顺序、延时、互斥、错误状态与清除机制。
4. 生成宏、掩码和访问序列；W1C／读清／FIFO／保留位不用通用 read-modify-write。

## Commands
```bash
rg -n "#define.*REG_|BIT\(|MASK" <driver_path>
rg -n "TODO.*register|FIXME.*reg" <driver_path>
rg -n "reserved|RESERVED" <header_path>
# ADK 不内置生成器或校验器。目标项目需给出真实工具路径和 datasheet 版本；不可伪造 PASS。
```

## SVD 生成与验证
以下仅为**新设计寄存器 Schema**，不是 SVD 工具输入或实际 MCU 定义。按目标 datasheet/errata 填写并运行真实工具；null 表示尚未查明，不可作发布定义。
```yaml
peripherals:
  - name: EXAMPLE_PERIPHERAL
    base_address: null  # 未查明，不可发布
    registers:
      - name: CONTROL
        offset: null
        size: 32
        access: read-write
        reset_value: null
        fields:
          - name: ENABLE
            bit_offset: 0
            bit_width: 1
            enum: {Disabled: 0, Enabled: 1}
```

## 位域设计规范
| 规则 | 说明 |
|------|------|
| 既有芯片保留位 | 按手册写 0、保留或禁止访问；不假定读 0／写忽略 |
| 自主设计的保留位 | RAZ/WI（读零、写忽略）需明确契约及验证 |
| 读改写原子性 | 多位域共享寄存器需提供原子操作或锁 |
| 写 1 清除／读副作用 | W1C、read-clear、FIFO 等应单独规定访问序列与竞态，不用普通 RMW 模板 |
| 复位语义 | 数值、有效位与复位种类必须匹配 datasheet；undefined 不填假 0 |
| 端序 | 多字节寄存器必须标注字节序 |

## 复位有效位
按实际 POR、外设/软件复位、保留域或引脚条件分别记录，不能共用一个全字数值。SVD 的有效 `resetValue/resetMask` 还须展开继承；`resetMask` 中 1 表示已定义位，0 表示 undefined，不代表这些位读回 0。

先确认整次访问读安全，再对满足复位条件的已定义位检查 `((observed ^ expected) & known_mask) == 0`；掩码不能消除读取本身的副作用。零可检查位记 `not-testable`，不能因恒等于 0 宣称复位通过；write-only、read-clear/FIFO 不用普通 readback。资料未知保留缺口，手册明确的 undefined/条件性结果如实交付，不编造数值。此规则不授予真实复位或 MMIO 读取权限。

依据：[CMSIS-SVD registerPropertiesGroup](https://open-cmsis-pack.github.io/svd-spec/latest/elem_special.html)。

## Evidence Template
```md
- Register Table:
- Bitfield Definition:
- Access Sequence:
- Side Effects:
- Validation Checklist:
```

## Failure Handling
手册冲突或关键复位条件、有效位、时序资料未知时保留 `needs-fix` 并暂停受影响实现；手册明确 undefined 不是资料缺失。

## Quality Gate
映射表应包含权限、复位语义、来源、保留位/副作用与适用的读写/中断/异常验证；undefined 和未验证项不算数值检查通过。
