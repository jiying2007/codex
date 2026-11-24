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

## 本次代码候选：G1 无模型链接入口
新增 sources/service 与现有 Bot 消息处理及现有 Bot SQLite 集成；链接来源和消息摘要、根话题按租户/chat/actor 持久化，严格解析、重复/权限、多个主工单拒绝、项目映射与 `/repo`，不会把识别的链接传给普通模型入口。现有独立 RunStore 仅迁移期间保留；未实现正文读取、真实模型执行、原生续接及完整 DB 迁移。测试候选与现场分别记账。

## 本次 G2 实质代码候选
现有 Bot SQLite 同一原子 create_agent_task 发布接口新增远程 context/event/policy/source 绑定；明确操作在管理员开启且独立模型身份、用户、仓库、模式授权满足时排队。Worker 复核绑定及原输入，复用 CodexRunner persistent CLI 与 exact prior native thread，记录实际回执；未成功/UNKNOWN 不猜测续接。同话题精确取消；普通旧聊天入口在工程模式开启时不绕过独立身份。独立执行不挂载个人 CODEX_HOME 为可写，已知个人凭据路径掩蔽，read 不可写仓库；仍需主机实际隔离、计费及 provider 授权验证。本候选不调用真实模型，不宣称真实研发成功；完整迁移和交付仍待实施。
