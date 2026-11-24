# adk-code-simplification — 补充参考资料

此参考文件只提供可选背景、示例和检查提示；当前能力流程、权限、回退与放行结论以 `../SKILL.md`、Manifest 及运行时门禁为准。示例命令不得被解释为写权限授权。

## 核心原则

1. **Chesterton's Fence**: 简化前先理解为什么要这样写
2. **语义边界优先**：无通用 500 行硬阈值，依据模块职责与可测试性选择简化
3. **DRY 但不过度**：依据重复的业务语义和未来变更成本决定是否抽象，不设固定次数
4. **可读性优先**: 清晰 > 简短
5. **测试先行**: 简化前确保有测试覆盖

## 代码异味识别

| 异味 | 表现 | 简化模式 |
|------|------|---------|
| 长函数 | 职责不清、多层嵌套 | 提取函数 |
| 深层嵌套 | 嵌套妨碍理解 | 卫语句/早期返回 |
| 复杂条件 | 条件组合难以测试 | 表驱动/策略模式 |
| 重复代码 | 相同业务规则在多处漂移 | 提取公共函数 |
| 死代码 | 未使用的变量/函数/分支 | 直接删除 |
| 魔法数字 | 硬编码数字无说明 | 提取常量 |
| 过长参数 | 参数职责不清或形成数据泥团 | 参数对象/Builder 模式 |
| 数据泥团 | 总是一起出现的参数 | 提取结构体/类 |

## 简化前后对比

### 提取函数
```c
// Before: 40 行处理函数
void process(data_t *d) {
    // 10 行校验...
    // 15 行转换...
    // 15 行输出...
}

// After: 3 个清晰步骤
void process(data_t *d) {
    if (!validate(d)) return;
    transform(d);
    output(d);
}
```

### 降低嵌套并保留后续处理

普通条件块不能直接改成函数级 `return`：失败分支仍可能需要执行后续工作或资源清理。只有失败本来就应终止函数、且清理路径完整时才使用早返回；以下保留条件块后的 `cleanup()`。

```c
// bool 来自 <stdbool.h>；do_something/cleanup 为既有操作。
void process_before(bool a, bool b, bool c) {
    if (a) {
        if (b) {
            if (c) { do_something(); }
        }
    }
    cleanup();
}

void process_after(bool a, bool b, bool c) {
    if (a && b && c) {
        do_something();
    }
    cleanup();
}
```

### 表驱动替代复杂条件
```c
// Before: 长串 if-else
if (type == A) handle_a();
else if (type == B) handle_b();
else if (type == C) handle_c();

// After: 表驱动
handler_t handlers[] = {{A, handle_a}, {B, handle_b}, {C, handle_c}};
for (int i = 0; i < ARRAY_SIZE(handlers); i++) {
    if (handlers[i].type == type) { handlers[i].fn(); break; }
}
```
