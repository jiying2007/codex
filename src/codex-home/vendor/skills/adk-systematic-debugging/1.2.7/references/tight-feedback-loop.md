# 困难故障的最短反馈回路

只读/获准隔离实验；生产设备、危险写入与认证保持授权边界。

1. 重跑/clean/rebuild **前**保全易失的输入、日志、dump/截图，记来源/hash/受控路径；缺原件的归因仍是假设。
2. 选会因缺陷变红的最小错误码、断言、响应、日志事件或计数器。优先单次本地复现；偶现记失败数/N、置信边界，固定种子/时间/网络/并发/文件条件；一次绿不证明修复。
3. 缩减输入、二分、状态捕获、只读插桩或对照配置，一次一因子。双麦/MCU/异步核时间线、调度、IRQ/状态顺序、资源 owner 与晚到完成。无法原机复现，用受控模拟/静态断言标 `proxy evidence`。

## Git 二分
隔离仓校准同一性质的 known-good/bad；包装器/测试器置于切换树外。受信 probe 只输出 good、bad 或 untestable，exit 0，故障非零。编译回归的编译失败是 bad；妨碍其他性质测试的修订才 untestable，未知/环境故障中止。

<!-- adk-example: bisect-probe -->
```bash
bisect_probe() {
  local verdict
  verdict=$("$@") || return 128
  case "$verdict" in
    good) return 0 ;;
    bad) return 1 ;;
    untestable) return 125 ;;
    *) return 128 ;;
  esac
}
bisect_probe "$@"
```

用 `git bisect run bash <包装器> <probe>`。留 `git bisect log`/候选，停留 HEAD 不是结论；skip 多候选保持未定位。无稳定信号不二分。[Git 2.52](https://git-scm.com/docs/git-bisect/2.52.0)。
