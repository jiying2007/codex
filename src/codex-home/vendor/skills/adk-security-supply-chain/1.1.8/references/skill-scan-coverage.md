# 第三方 Skill 安全扫描证据与误报复核（按需）

**适用**：`adoption preflight` 或 `install / runtime readiness`，而非单纯只读方法分析。扫描工具和模型均须经现有运行时授权，不自动安装/执行不可信目标的 scripts、hooks、postinstall 或远程代码。

1. 冻结来源：`candidate_source@commit/tag`、`skill_path`、LICENSE、依赖 lock 与可用的 target `SECURITY_MODEL.md@digest`。政策可能过期：逐项核真实符号/调用者和可访问入口，未核对不能给 `confirmed-safe`。
2. 列覆盖：`inspected/omitted/unavailable` 按 `SKILL.md / references / scripts / assets / symlink / hooks / MCP schema / install action / tool declarations / hidden/binary` 分类；扫描器不能读到的文件需说明原因和 owner，不以 0 findings 宣称 100% 覆盖。
3. 逐条扫描发现：`finding_id / pattern / source_symbol / input_trust / reachable_sink / affected_principal / resource / consequence / evidence / confidence / verdict`。对 prompt injection、数据外传、权限扩大、依赖污染、工具滥用与过度代理权分别找实际通路。没有可影响的 principal/resource/outcome 时标 `unverified` 或有反证的 `false-positive`，不凭关键词评分。
4. 独立判断：严重度、置信度、扫描覆盖率和真实利用条件分别报告；critical/high `confirmed` 阻断安装直到修复或正式授权的风险接受。不能因为 LLM 语义检查高分、无 CVE 或静态规则零命中就授予工具权限。
5. 回滚：记录 `tool_version / policy_rev / source_sha / allowed_scope / deny_path / sandbox / rollback`。源码审查合格只提供晋级候选；执行权限仍由宿主 policy 和 owner 控制。

本参考沿用已有 `adk-security-supply-chain` 的外部资产审查责任，不构成新 Skill 或第二套安全扫描引擎。

## Generated serialization

仅在候选资产涉及凭证对象或整对象输出时使用本节，沿用上方 scope/权限；不执行不可信候选代码。

1. 从字段类型、配置来源与调用方识别 credential holder，再追踪 serializer 到日志、trace、响应、缓存或队列 sink；字段名只是线索，零关键词命中不能证明安全。改动任一端都查当前 diff 外的另一端及嵌套对象。
2. 区分每条输出路径：Python `repr=False` 仅排除 repr，`asdict` 仍递归包含字段；其他模型、JSON 或原始属性读取须核该版本的实际语义，不能推断受相同保护。未证明凭证到 sink 可达时标 `unverified`，不把字段存在直接判成已泄漏。
3. 按实际输出合同显式选择允许的非敏感字段，用合成 sentinel 验证敏感值缺席、必要字段保留。允许字段本身也须确认不含凭证；此方法不是任意对象的通用脱敏库，不修改输入对象来掩盖泄漏。
4. 只在已授权的隔离 fixture 中运行可信复现，使用 sink 的真实 serializer；报告记录路径、符号、通路、结论及未知项，不回显凭证值或原始整对象。不把示例运行当成第三方资产已通过审查。

以下为 Python 标准库合成反例；保存为 `serialization_example.py` 后用 `python3 -I serialization_example.py` 执行。坏输出仅留内存，stdout 只有布尔结论；无 Python 时记录 `not-run`，不自动安装。

```python
from dataclasses import asdict, dataclass, field
import json

@dataclass
class CredentialHolder:
    endpoint: str
    credential: str = field(repr=False)

@dataclass
class Event:
    component: str
    client: CredentialHolder
    status: str

def public_event(event):
    # This fixture's public fields are known safe, not arbitrary user input.
    return {"component": event.component,
            "client": {"endpoint": event.client.endpoint},
            "status": event.status}

if __name__ == "__main__":
    sentinel = "SYNTHETIC_SERIALIZATION_ONLY"
    holder = CredentialHolder("https://example.invalid", sentinel)
    event = Event("fixture", holder, "ready")
    direct = json.dumps(asdict(holder))
    nested = json.dumps(asdict(event))
    public = public_event(event)
    checks = {
        "repr_excluded": sentinel not in repr(holder),
        "direct_leak_observed": sentinel in direct,
        "nested_leak_observed": sentinel in nested,
        "allowlist_excluded": sentinel not in json.dumps(public),
        "public_fields_preserved": public == {
            "component": event.component,
            "client": {"endpoint": holder.endpoint}, "status": event.status},
    }
    if not all(checks.values()):
        raise RuntimeError("synthetic serialization checks failed")
    print(json.dumps(checks, sort_keys=True))
```
