# 保留本地修改的多仓同步

入口：`multi-repo-safe-sync` workflow；主流程复用`adk-repo-drift-remediation`，需要隔离时再用`adk-worktree-governance`。只读检查不启动同步；同步不授权commit、push、rebase或stash清理。

1. 按实际Git root逐仓盘点HEAD/分支/ref、staged/unstaged/untracked、gitlink与依赖顺序；不猜子仓边界。
2. 使用团队库`docs/templates/multi-repo-sync-record.md`固定逐仓动作、恢复锚点和验收。团队根由已配置的`EMBEDDED_KNOWLEDGE_HOME`或已确认源定位，不复制正文或写个人路径。
3. 按已授权动作逐仓推进，保留有效本地修改；共享合同/锁/生成物串行。冲突、恢复失败或目标ref变化先停止依赖步骤并核对，不能整侧覆盖或重复外部写入。
4. 对照前后摘要、index边界、untracked及冲突决策，运行目标仓定向检查；没有同步的独立仓明确列出。
5. 报告refs、本地改动保留、代码验证、制品和设备证据的各自状态；保留恢复锚点直至明确允许清理。

模板的验收案例逐项执行并留真实结果。结构/路由检查只证明入口可用，不把没有执行的Git场景标为通过。
