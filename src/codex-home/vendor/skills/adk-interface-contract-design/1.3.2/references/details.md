---
name: adk-interface-contract-design
description: 定义模块/API/消息接口契约
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "设计接口"
  - "API设计"
  - "接口契约"
non_triggers:
  - 纯内部重命名
inputs:
  - 调用方与被调方约束
outputs:
  - 接口契约草案
constraints:
  - 必须明确输入、输出、错误码
---

# adk-interface-contract-design

## Goal
- 输出稳定、可验证的接口契约，降低跨模块返工。
- 确保嵌入式组件间接口（HAL/驱动/协议栈）有明确的版本化契约。

## Prerequisites
- 明确调用链 owner、版本策略和兼容窗口。
- 确定输入输出数据源与错误语义边界。
- 了解目标平台约束（内存对齐、字节序、对齐要求）。

## Workflow
1. **定义接口清单**：请求、响应、错误码、幂等语义。
   ```c
   /* 嵌入式接口契约示例 */
   typedef struct {
       uint32_t magic;        /* 0xCAFEBABE */
       uint16_t version;      /* 接口版本 */
       uint16_t cmd;          /* 命令码 */
       uint32_t payload_len;  /* 负载长度 */
       uint8_t  payload[];    /* 柔性数组 */
   } __attribute__((packed)) iface_msg_t;

   /* 错误码定义 */
   typedef enum {
       IFACE_OK          =  0,
       IFACE_ERR_PARAM   = -1,  /* 参数非法 */
       IFACE_ERR_TIMEOUT = -2,  /* 超时 */
       IFACE_ERR_BUSY    = -3,  /* 忙 */
       IFACE_ERR_NOMEM   = -4,  /* 内存不足 */
       IFACE_ERR_PROTO   = -5,  /* 协议错误 */
   } iface_err_t;
   ```
2. **版本协商机制**：接口版本兼容性自动检测。
   ```c
   /* 版本协商 */
   #define IFACE_VERSION_MAJOR  2
   #define IFACE_VERSION_MINOR  1
   #define IFACE_VERSION_MAKE(maj, min) (((maj) << 8) | (min))
   #define IFACE_VERSION_CUR    IFACE_VERSION_MAKE(2, 1)

   bool iface_version_compatible(uint16_t remote_ver) {
       uint8_t remote_major = remote_ver >> 8;
       return (remote_major == IFACE_VERSION_MAJOR);
   }
   ```
3. **错误码设计规范**：统一错误码空间，避免冲突。
   ```bash
   # 检查错误码定义一致性
   rg -n "IFACE_ERR_|ERR_" include/ src/ | sort
   # 检查是否有重复错误码值
   rg -o "= -[0-9]+" include/ | sort | uniq -d
   ```
4. **约束异常行为**：超时、限流、重试、降级策略。
   ```c
   /* 超时与重试配置 */
   #define IFACE_TIMEOUT_MS     1000
   #define IFACE_MAX_RETRIES    3
   #define IFACE_RETRY_DELAY_MS 100
   ```
5. **生成契约用例**：正常、边界、异常三类样例。
   ```bash
   # 编译契约测试
   gcc -I include/ -o iface_test tests/iface_contract.c -lcomponent
   # 运行契约验证
   ./iface_test --suite contract
   ```
6. **同步消费者影响**：列出受影响模块与改造顺序。

## Commands
```bash
# 接口定义扫描
rg -n "interface|api|contract|schema" <module_path>
rg -n "typedef.*\(" include/<module>/*.h

# 错误码一致性检查
rg -n "= -[0-9]+" include/<module>/errors.h | sort -t= -k2 -n

# 版本信息检查
rg -n "VERSION|version|COMPAT" include/<module>/

# 废弃接口扫描
rg -n "TODO.*compat|deprecated|DEPRECATED" <module_path>

# 契约测试
gcc -I include/ -Wall -Werror -o contract_test tests/contract.c && ./contract_test

# 结构体对齐检查（嵌入式关键）
pahole --class_name=iface_msg_t <module>.o

# 字节序验证
python3 -c "import struct; print(struct.pack('<I', 0xCAFEBABE).hex())"
```

## Evidence Template
```md
- Interface Definition:
  - Name: ____
  - Version: ____
  - Owner: ____
- Input/Output Spec:
  | Field | Type | Size | Description |
  |-------|------|------|-------------|
  | magic | uint32_t | 4B | 0xCAFEBABE |
  | version | uint16_t | 2B | 接口版本 |
- Error Codes:
  | Code | Value | Meaning | Recovery |
  |------|-------|---------|----------|
  | IFACE_OK | 0 | 成功 | - |
  | IFACE_ERR_TIMEOUT | -2 | 超时 | 重试 |
- Version Compatibility: [major 兼容 / minor 向后兼容]
- Deprecation Plan: [废弃周期与迁移路径]
- Validation Cases:
  - [ ] 正常路径: ____
  - [ ] 边界条件: ____
  - [ ] 异常路径: ____
- Struct Alignment: [packed/aligned, padding bytes]
```

## Failure Handling
- 若调用方未确认兼容策略，结论置为 `needs-fix`。
- 若错误语义不一致，先冻结接口变更并回到设计讨论。
- 若结构体对齐不符合目标平台要求，添加 `__attribute__((packed))` 或调整字段顺序。
- 若版本协商失败，回退到最低公共版本并记录兼容降级。

## Quality Gate
- 契约必须包含输入/输出/错误码/超时语义。
- 必须给出版本兼容与迁移方案。
- 必须附至少 3 条验证用例（正常/边界/异常）。
- 嵌入式接口必须验证结构体大小与对齐（`pahole` 或 `sizeof` 断言）。
- 错误码必须覆盖所有可恢复与不可恢复场景。

---

## 合理化借口拦截

| 借口 | 现实 | 正确做法 |
|------|------|---------|
| "接口很简单不需要契约" | 无契约的接口是集成阶段的定时炸弹 | 按 SKILL.md 至少定义输入/输出/错误码/超时语义 |
| "先写代码后面再补接口文档" | 后补的文档永远追不上代码的真实行为 | 先设计契约再实现，契约即测试依据 |
| "我们口头对齐过了" | 口头对齐在跨模块联调时毫无约束力 | 产出版本化的接口契约并附验证用例 |
