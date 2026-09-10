---
name: adk-interface-contract-design
description: 定义模块、API、消息和受控生命周期操作的接口契约
version: 1.3.0
last_updated: 2026-09-10
triggers:
  - "设计接口"
  - "API设计"
  - "接口契约"
non_triggers:
  - 纯内部重命名
inputs:
  - 调用方与被调方约束
  - 有状态或异步操作的生命周期约束（如适用）
outputs:
  - 接口或生命周期操作契约草案
constraints:
  - 必须明确输入、输出、错误码
  - 机器消费接口必须声明 strict schema、additionalProperties=false 和 refusal handling
  - 受控生命周期操作必须明确唯一 owner、状态事件和终止语义
---

# adk-interface-contract-design

## Goal
- 输出稳定、可验证的接口契约，降低跨模块返工。
- 确保嵌入式组件间接口（HAL/驱动/协议栈）有明确的版本化契约。


## Prerequisites
- 明确调用链 owner、版本策略和兼容窗口。
- 确定输入输出数据源与错误语义边界。
- 了解目标平台约束（内存对齐、字节序、对齐要求）。
- 若请求会启动、取消或恢复共享资源操作，已识别唯一 owner 与状态可见性。


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
5. **受控生命周期契约（条件性）**：若操作跨越状态或独占资源，冻结 owner、状态、事件、资源、终止和 invariant；其中必须覆盖可见性、取消、超时、恢复、迟到完成与 generation/op-id 隔离。详见 [生命周期操作契约](references/lifecycle-operation-contract.md)。
6. **结构化输出契约**：API、消息、工具或 handoff schema 必须记录 required fields、enum、additionalProperties=false、refusal handling 和 parse-failure 处理。
7. **生成契约用例**：正常、边界、异常三类样例。
   ```bash
   # 编译契约测试

> 详细内容已移至 `references/details.md`。

## Quality Gate
- 契约必须包含输入/输出/错误码/超时语义。
- 机器消费契约必须包含 strict schema、required fields、enum 和 refusal/parse-failure handling。
- 必须给出版本兼容与迁移方案。
- 必须附至少 3 条验证用例（正常/边界/异常）。
- 嵌入式接口必须验证结构体大小与对齐（`pahole` 或 `sizeof` 断言）。
- 错误码必须覆盖所有可恢复与不可恢复场景。
- 受控生命周期操作必须给出 owner × state × event × resource × termination × invariant 矩阵，并明确 generation/op-id、幂等、重试预算与 callback/cleanup 并发边界；缺失时不得进入实现或给出设计通过结论。

---


## Failure Handling
- 若调用方未确认兼容策略，结论置为 `needs-fix`。
- 若错误语义不一致，先冻结接口变更并回到设计讨论。
- 若结构体对齐不符合目标平台要求，添加 `__attribute__((packed))` 或调整字段顺序。
- 若版本协商失败，回退到最低公共版本并记录兼容降级。


## Evidence Template

```md
status: pass | needs-fix | BLOCKED
structured_schema: strict | not_applicable
lifecycle_operation: not_applicable | contract-path
commands:
- <command + exit code>
evidence:
- <path or output summary>
risks:
- <remaining risk or none>
```

## References
- 详细背景、命令、模板、示例和扩展检查项保存在 `references/details.md`。
- 入口文件只保留触发和执行所需的最小上下文，避免默认加载过多 token。

## 合理化借口拦截

- “先实现再补状态语义”不成立：状态、owner 或终止语义不明时先冻结契约。
- “回调最终会完成”不成立：超时、取消和迟到完成必须有可验证处理。
