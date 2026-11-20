# 接口参考

## 有方向的版本/能力检查

本例需 `2.1`/`ASYNC_CANCEL`，仅限已验证的同 major 新 minor 保留旧能力策略，否则用显式支持矩阵。验证解码版本/能力，禁凭版本推断能力；16 位 major/minor 非完整 SemVer，wire 布局/字节序/ABI/取消/错误语义另验。

```c
#include <stdbool.h>
#include <stdint.h>

/* Validate both components in 0..255 before encoding. */
#define IFACE_VERSION_MAKE(major, minor) \
    ((uint16_t)(((uint16_t)(major) << 8) | (uint16_t)(minor)))
#define IFACE_CAP_ASYNC_CANCEL (UINT32_C(1) << 0)

bool iface_version_compatible(uint16_t remote_ver, uint32_t remote_caps)
{
    const uint8_t major = (uint8_t)(remote_ver >> 8);
    const uint8_t minor = (uint8_t)(remote_ver & UINT16_C(0xff));
    return major == 2 && minor >= 1 &&
           (remote_caps & IFACE_CAP_ASYNC_CANCEL) == IFACE_CAP_ASYNC_CANCEL;
}
```

`2.1`/`2.2` 且有必需能力才通过；`2.0`/缺能力/跨 major 拒绝。`3.0` 不证明支持 `2.x`；本地 `2.1..2.2`/对端 `2.0` 无交集，禁降级。记录双方身份、支持集合来源、选择/拒绝依据及验证。

[SemVer](https://semver.org/) 的公共 API/最低依赖承诺不证明 wire/ABI。

## Schema 方言与闭合

固定消费者 `$schema`/dialect、validator 版本/支持子集。同层 `properties` 用 `additionalProperties:false`；`allOf/$ref` 不提前封闭可扩展子 schema，仅实测支持 2019-09/2020-12 的组合边界用 `unevaluatedProperties:false`。旧 draft/窄子集同层展开，无法表达则 `needs-fix`，禁止放宽。

两例须接受 `{"id":1,"mode":"safe"}`，拒绝未知字段、缺 id/mode、错类型/枚举。以消费者 validator 实测；Draft7 忽略 `unevaluatedProperties`，不能仅换关键字。

```json
{"$schema":"http://json-schema.org/draft-07/schema#","type":"object",
 "properties":{"id":{"type":"integer"},"mode":{"enum":["safe","fast"]}},
 "required":["id","mode"],"additionalProperties":false}
```

```json
{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object",
 "allOf":[{"properties":{"id":{"type":"integer"}},"required":["id"]},
          {"properties":{"mode":{"enum":["safe","fast"]}},"required":["mode"]}],
 "unevaluatedProperties":false}
```

## Commands
```bash
rg -n "interface|api|contract|schema" <module_path>
rg -n "typedef.*\(" include/<module>/*.h
rg -n "VERSION|version|COMPAT" include/<module>/
rg -n "TODO.*compat|deprecated|DEPRECATED" <module_path>
pahole --class_name=iface_msg_t <module>.o
```
契约测试用真实入口；host 打包不证明目标协议字节序。
