# 终态验证记录

## 已有证据
- 目标 Ubuntu 主机 旧现场 HEAD 19a697c81b45666b8794171182c968e256725771，systemd active、UMask=0077、NoNewPrivileges=yes、PrivateTmp=yes、Codex 0.171.0；/help、/status、/wi help/list/add 现场正常。用户提供的本地 smoke 工作项状态 proposed，未调用模型。
- #81 候选 ba6f13ab 全部 CI 通过；合并 a72071fb674c5126226e4732a30ed061ce95673f。
- #82 候选 19c14f23b851875a7b4ff1f15c6ae8009100673a：Full Regression 45319808217、Runtime Binding Contract 45319808143、Profile Context Contract 45319808287 均成功。用户现场原始嵌套失败 setting up uid map: Read-only file system；加入 --unshare-pid 和 --proc /proc，setpriv --no-new-privs 测试 returncode=0, nested_shell_ok=True。合并 76305a78fc3483cc23054c2387b274f4b238a4bf。现场探针不是新版服务/模型验收。
- 生产仍须统一部署两个修复；合并后独立 CI 回执待复核。

## 新验收矩阵
ACC-01..06,11：真实链接样例、畸形/伪域名/多工单/重复事件、话题隔离、仓库映射/权限、无 API 文本答复。无模型集成测试+真实 Feishu 文本。
ACC-07..14：权限正反例、原生 exact resume、独立身份与凭据 mask、编辑 worktree、queue crash/cancel/restart 和政策漂移；实际主机无模型 probe 后才使用批准计费。
ACC-15..17,20：真实需求/缺陷、文档与跨仓研发，真实代码及精确 PR/CI、测试/QA；不能用 mock 或历史提交代替。
ACC-18..19：生产可达路径、迁移/恢复、单 consumer；删除冗余后完整回归。
每次记录精确 SHA、运行链接、实际结果、未通过和外部阻塞；未观察不宣称 PASS。禁止使用共享模型额度。
