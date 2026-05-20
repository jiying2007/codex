# Sigmastar 双屏动画实现分析（2026-05-14）

## 背景

- 项目：`sdk/verify/xcrz_sigmastar_demo`
- 模块：`modules/sensor/display`
- 目标：梳理当前双屏动画实现的架构、调用链、同步机制与风险点。
- 方法：只读代码分析，不修改实现。

## 结论概览

当前实现采用“单显示线程驱动 + 双 framebuffer (`/dev/fb0`/`/dev/fb1`) + 场景包装层”的方式：

1. `DisplayMain` 线程周期处理请求并驱动 `update/tick`。
2. `DisplayManager` 维护左右两个 `lv_disp`，分别 flush 到两块屏幕。
3. 各场景（Eye/Network/OTA）在左右屏分别建对象并用相同参数同步执行动画。

## 主调用链

1. 控制消息入口：`display_control.cpp`。
2. 请求汇总与线程驱动：`display_main_cpp.cpp`。
3. 场景注册与切换：`display_manager.cpp` + `display_manager_cpp.cpp`。
4. 动画实现主体：`scene_eye.cpp`、`scene_network.cpp`、`scene_ota.cpp`。

## 双屏同步机制

### 1) 渲染层

- `DisplayManager::init()` 分别初始化 `/dev/fb0` 与 `/dev/fb1`，注册两个 `lv_disp`。
- `generic_flush()` 将 LVGL 绘制结果写入对应 framebuffer，实现左右屏独立刷新。

### 2) 场景层

- Eye：左右眼对象独立创建，移动/眨眼/表情动画使用一致的目标参数。
- Network：通过 `create_dual_screen_ui(...)` 同时构建左右 UI，连接/成功/失败动画并行。
- OTA：下载/安装/成功/失败均成对创建左右对象并同步触发动画，进度数字左右同构更新。

## 关键行为观察

1. `DisplayMain` 约 16ms 一帧驱动（约 60FPS），将外部请求串行化处理。
2. Eye 场景动画状态机规模较大，存在大量全局状态对象（`g_*_state`）协同。
3. 场景切换目前以 `exit()->deinit()` 为主，切换时倾向于销毁重建，而非简单 show/hide。
4. 资源加载由 `resource_manager.cpp` 统一处理，PNG 转换为 LVGL 需要的颜色格式。

## 风险与改进优先级

### 高优先级

1. `DisplayControl` 线程退出风险：
   - `threadEntry()` 使用 `while(true)` + `poll(-1)`，`stop()` 后可能无法自然退出。
2. 显示设备初始化健壮性：
   - `open` 判定使用 `<= 0`，对 fd=0 存在误判可能；部分分配失败路径检查不完整。

### 中优先级

1. OTA 状态边界检查可读性问题：
   - `scene_ota_set_state()` 使用 `POWER_STATE_MAX` 作为上限，语义不一致。
2. 场景切换开销较大：
   - 频繁 `deinit/init` 可能增加抖动与资源压力。
3. 能力开关未完全生效：
   - `blink_enabled` / `expression_enabled` 相关判断存在注释代码。

### 低优先级

1. 部分接口留空：
   - 如 OTA 状态文本、update 留空，后续扩展需要补齐。

## 证据索引（文件:行）

- `modules/sensor/display/display_main_cpp.cpp:93`
- `modules/sensor/display/display_main_cpp.cpp:108`
- `modules/sensor/display/display_manager.cpp:15`
- `modules/sensor/display/display_manager_cpp.cpp:39`
- `modules/sensor/display/display_manager_cpp.cpp:239`
- `modules/sensor/display/scene_eye.cpp:2203`
- `modules/sensor/display/scene_eye.cpp:2790`
- `modules/sensor/display/scene_eye.cpp:2928`
- `modules/sensor/display/scene_eye.cpp:3112`
- `modules/sensor/display/scene_eye.cpp:5662`
- `modules/sensor/display/scene_network.cpp:201`
- `modules/sensor/display/scene_network.cpp:378`
- `modules/sensor/display/scene_network.cpp:494`
- `modules/sensor/display/scene_ota.cpp:517`
- `modules/sensor/display/scene_ota.cpp:592`
- `modules/sensor/display/scene_ota.cpp:249`
- `modules/sensor/display/display_control.cpp:46`

## 适用范围

- 适用于当前仓库 `modules/sensor/display` 的现状评审。
- 不包含硬件时序实测数据，不替代实机性能与稳定性验证。

## 后续建议

1. 先修复 `DisplayControl` 可停止性，再做功能增强。
2. 收敛场景生命周期策略，减少不必要的反复重建。
3. 为 OTA/Network 增补状态与异常路径测试。

