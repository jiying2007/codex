# disk-space-triage

Linux 宿主机磁盘及所有可见 UID 占用分析，提供有证据边界的清理建议。

Origin: local-chronicle-derived
Lifecycle: iterative-local

来源：历史脏工作区和嵌套仓保护经验，以及 2026-11-10 的磁盘满、5 天保护、权限缺口和分批回收实践。历史容量不作为当前事实。

描述“分析 /tmp 所在磁盘各用户占用及删除建议”，或显式使用 `disk-space-triage`。

```bash
rtk bash /home/leiwenjun/codex/scripts/disk-usage.sh --path /tmp --filesystem --processes
# 已获跨用户只读授权，且 sudo 非交互认证可用时
rtk bash /home/leiwenjun/codex/scripts/disk-usage.sh --path /tmp --filesystem --sudo --processes
```

边界见 [SKILL.md](SKILL.md)。源码受管不等于 live 已安装；技能与当前 checkout 的 CLI 配套。

预防策略：根分区维持至少 10 GiB 日常缓冲；新建大型临时构建和验证任务时，核实独立数据分区后使用任务专用目录与单命令 `TMPDIR`，并核实项目实际构建输出参数。已有近期目录和运行中的任务按原边界保留，不全局替换 `/tmp`。
