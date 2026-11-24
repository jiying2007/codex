# 测试波动：按需取证

遵守入口权限/统计边界，不执行未审查的测试/生产操作。

## 样本与结果
从原生JUnit/JSON取精确用例ID与逐次环境/结果；名称中的空格、方括号不作正则或shell分词。分开passed/failed/error/skipped/missing，日志命中数/进程非零不等于用例失败数。
记录计划/实际次数与排除理由；缺报告、启动/采集错误、全跳过不算成功，不静默删除不利样本。仅逐轮报告完整且版本/选择器/环境可比时计算失败率并说明假设；否则保留退出码与未知项。

## 有界采样
用已核项目入口的命令数组执行 `run_flaky_samples 10 <新证据目录> "${test_command[@]}"`。runner须有单次超时/取消；次数不限制耗时。它可用每轮FLAKY_SAMPLE_DIR写原生报告，不支持则只取得日志/退出码。无eval，不执行日志命令。

```bash
run_flaky_samples() (
  set -euo pipefail
  (( $# >= 3 )) || { printf 'usage: run_flaky_samples <1-20> <new-directory> <command> [args...]\n' >&2; exit 2; }
  samples=$1
  evidence=$2
  shift 2
  [[ "$samples" =~ ^([1-9]|1[0-9]|20)$ ]] || exit 2
  mkdir -- "$evidence" || exit 2
  evidence=$(cd -- "$evidence" && pwd -P) || exit 2
  printf 'attempt\texit_code\n' > "$evidence/results.tsv" || exit 2
  failed=0
  for ((attempt=1; attempt<=samples; attempt++)); do
    sample_dir="$evidence/run-$attempt"
    mkdir -- "$sample_dir" || exit 2
    exec 3>"$sample_dir/output.log" || exit 2
    result=0
    FLAKY_SAMPLE_DIR="$sample_dir" "$@" >&3 2>&1 || result=$?
    exec 3>&- || exit 2
    printf '%s\t%s\n' "$attempt" "$result" >> "$evidence/results.tsv" || exit 2
    case "$result" in 130|143) exit "$result" ;; esac
    if (( result != 0 )); then failed=1; fi
  done
  printf 'attempts=%s\nrecords=%s\n' "$samples" "$evidence/results.tsv" || exit 2
  exit "$failed"
)
```

0仅表示命令均返回0，仍核报告/选择器；1有普通非零，2参数/采集错误。子命令130/143在日志/TSV落盘后停止并原码退出；不代表父shell/进程组取消传播已验证。保留样本，不append旧日志、不重跑到绿；采集不完整不判稳定。

## 就绪竞争（有证据时）
日志/受控复现确认检查早于完成，才将猜测sleep改为原生event/barrier/condition，等待本次operation ID及明确ready。旧文件/旧响应不算完成，合法0/空结果不用truthiness判失败。需轮询时用monotonic截止期、适当间隔/取消；保留timeout/cancel与清理，不扩大超时掩盖缺陷。

Python host例：生产/取消方在同一cv锁内更新state并notify_all；此例取消优先。Condition.wait_for按monotonic算剩余时间；不要求消费端安装Python，不证明MCU时序。

```python
from math import isfinite

def wait_for_operation(cv, state, operation_id, timeout):
    if timeout is None or not isfinite(timeout) or timeout < 0:
        raise ValueError("a finite nonnegative timeout is required")
    def terminal():
        return state["id"] == operation_id and (
            state["ready"] is True or state["cancelled"] is True)
    with cv:
        if not cv.wait_for(terminal, timeout=timeout):
            raise TimeoutError("operation did not become ready")
        if state["cancelled"] is True:
            raise InterruptedError("operation cancelled")
        return state["result"]
```

以事件控制先后，核未就绪、旧ID、虚假通知、合法0、超时/取消和旧成功路径。debounce/节流/退避/硬时限仍验证过早不得发生、期限内须发生；不能只等最终状态。锁内消费结果，其他并发模型选对应原语。见[Condition](https://docs.python.org/3.11/library/threading.html#condition-objects)。

## 顺序与环境
独跑/suite不同或有共享状态线索时，保存顺序/seed/worker/进程边界，比victim独跑、原suite、前序→victim与反序；同进程场景不拆进程假复现。缩小前序集并查全局/环境/缓存/时钟/资源；多污染者非单调交互不能保证二分定位。仅改变待证伪变量，留逐例报告；新进程全绿不证明原污染修复，隔离修复另核边界/成本/原失败。无顺序线索不强制矩阵。

比版本、脱敏配置/资源；只列环境变量名，值须逐项安全白名单且不记录凭据：

```bash
# environment-names: values are never printed
python3 - <<'PY'
import json, os
print(json.dumps(sorted(name for name in os.environ
                       if any(key in name.upper() for key in ("TEST", "CI", "DEBUG")))))
PY
```

`rg -n 'timeout|race|port already in use|resource busy|connection refused' <test-log-directory>`只定位假设，不做统计。
记录hypothesis/changed variable/expected/observed/raw report/disproved-or-open；重试记原策略/预算/适用错误/停止条件。quarantine保留owner/原状态/解除条件/CI证据，不计PASS；保留原失败和成功路径。
