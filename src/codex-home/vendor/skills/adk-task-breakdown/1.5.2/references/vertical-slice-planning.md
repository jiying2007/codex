# Tracer-bullet 纵向任务切片

从最小可观察行为切片，不按“配置→框架→联调”分层：

1. **最小可运行结果**：明确入口、真实业务/设备动作、预期与运行验证；必要准备收进消费它们的同一 slice。
2. **准确文件地图**：读取仓库再标可能修改的文件和接口；未知标为待查，不编造路径/签名。
3. **依赖**：只有确实阻塞下游 slice 的 contract 或数据迁移才形成前置依赖；让测试可独立运行。共享 schema/root config 按一个 owner 串行。
4. **交付判定**：每片须有实际测试/演示路径和失败反馈，不能只声称“文档完成/准备就绪”。
5. **风险对照**：同目标对比纵向与按模块分工的集成次数、写冲突、上下文恢复及测试开销。

若设备不可连接，用 SIL/Mock 设计最小接口验证并写出真机缺口，不能把替代验证写成完整交付。

## 跨公共契约重构的例外

仅当全局重命名、类型或接口迁移不能沿普通纵向切片独立落地时：

1. **Expand**：新增契约同时保持真实旧消费者可用；列出临时兼容的 owner、退出条件和删除任务，不留下永久双入口。
2. **Migrate**：读取调用点，按真实消费者批次迁移；共享契约由唯一 owner 串行修改。每批验证新旧消费者的外部结果，不能用搜索命中代替执行。
3. **Contract**：所有消费者迁移后，检索旧入口、运行集成与受影响回归，再移除兼容。涉及外部消费者时还须有版本/部署证据；本地零引用不足以证明可删除。

若批次仍不能独立通过，由唯一集成分支承载依赖，明确中间失败和最后的集成任务；不得逐批声称整体通过。此拆分不授予真实数据迁移、删除或发布权限。

### 可执行反例：字段重命名

保存为临时 `migration.py`，运行 `python3 migration.py safe`。五阶段都运行临时 API 的两个消费者，各输出 `Ada`；`direct`/`early` 因旧消费者失败退出 1。只验证本地契约，未测试外部部署。

<!-- adk-example: contract-migration -->
```python
import json
from pathlib import Path
import subprocess
import sys
import tempfile

states = {
    "before": ({"name": "Ada"}, "name", "name"),
    "expand": ({"name": "Ada", "display_name": "Ada"}, "name", "name"),
    "migrate-a": ({"name": "Ada", "display_name": "Ada"}, "display_name", "name"),
    "migrate-b": ({"name": "Ada", "display_name": "Ada"}, "display_name", "display_name"),
    "contract": ({"display_name": "Ada"}, "display_name", "display_name"),
    "direct": ({"display_name": "Ada"}, "name", "name"),
    "early": ({"display_name": "Ada"}, "display_name", "name"),
}
paths = {
    "safe": ["before", "expand", "migrate-a", "migrate-b", "contract"],
    "direct": ["before", "direct"],
    "early": ["before", "expand", "migrate-a", "early"],
}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    for stage in paths[sys.argv[1]]:
        payload, *keys = states[stage]
        (root / "profile_api.py").write_text("def profile():\n    return " + repr(payload))
        results = []
        for index, key in enumerate(keys):
            consumer = root / f"consumer_{index}.py"
            consumer.write_text("from profile_api import profile\nprint(profile()[" + repr(key) + "])")
            run = subprocess.run([sys.executable, "-B", str(consumer)], capture_output=True, text=True)
            results.append({"exit": run.returncode, "value": run.stdout.strip(), "error": run.stderr})
        print(json.dumps({"stage": stage, "consumers": results}))
        if any(result["exit"] or result["value"] != "Ada" for result in results):
            raise SystemExit(1)
```
