# Embedded Knowledge Base 会话收尾

- 日期：2026-05-17
- 仓库：`~/embedded/knowledge`
- 远端：`ssh://git@192.168.1.4:10022/embedded/knowledge.git`
- 当前提交：`a2ee7f7 chore: 建立知识库质量基线`
- 提交形态：单一根提交，`git rev-list --count HEAD = 1`

## 本次目标

将原项目中的 `docs`、`tools` 相关技术沉淀独立为团队共享知识库，并对仓库结构、规范、脚本、技能、验证门禁和长期维护边界做一次全盘治理。

## 已完成工作

1. 建立 `~/embedded/knowledge` 作为团队共享知识库本地路径，并关联远端 `embedded/knowledge.git`。
2. 清理原项目内 `docs`、`tools` 知识库内容迁移后的残留，明确知识库不再内嵌在业务项目根目录。
3. 建立仓库边界：允许维护 `docs`、`tools`、`scripts`、`profiles`、`.githooks`、CI 模板和少量根文件；禁止恢复 `docs/project`、`docs/specs`、`docs/plans`、`docs/reports`、`docs/superpowers` 等漂移目录。
4. 增补治理文档、结构规范、贡献规范、发布指南、迁移映射、质量基线和本地工作流说明。
5. 建立脚本质量门禁：命名、schema、链接、归档 manifest、AGENT/SKILL 一致性、仓库形态、shellcheck、shfmt、密钥扫描、文档 lint、skills dry-run、artifact 检查、工具可用性检查。
6. 增补团队研发知识内容：嵌入式 Linux 性能排查、Sigmastar 媒体链路排查、YOLO AI vision 部署与排障、运行时基线采集脚本。
7. 增补 Codex / Agent / Skill 相关资产：技能模板、agent 模板、新技能脚本、嵌入式排障类 skill、YOLO vision triage skill。
8. 安装并验证推荐工具：`shellcheck`、`ripgrep`、`fd-find`、`tmux`、`direnv`、`shfmt v3.13.1`、`yq v4.53.2`。
9. 将远端强制整理为单一根提交，并同步本地 `~/embedded/knowledge` 到远端状态。
10. 清理测试生成的 `__pycache__` 等忽略产物，最终工作区保持干净。

## 关键决策

1. 团队共用路径采用 `~/embedded/knowledge`，避免绑定某个业务项目目录。
2. 知识库作为独立 Git 仓库演进，业务项目只引用或链接，不再直接承载长期研发知识沉淀。
3. 当前阶段允许单一提交重建基线，远端历史已覆盖为 `a2ee7f7`。
4. 仓库长期治理优先级为：边界清晰、低冗余、可验证、可迭代、脚本化门禁。
5. 会话归档与记忆整理只生成归档和审计报告，不静默写入长期 memory。

## 验证证据

完成阶段已执行 `rtk bash scripts/check-all.sh`，结果包括：

- Python 测试：`32 tests OK`
- 命名检查：`checked 46 files`
- Schema 检查：`checked 43 documents`
- 链接检查：`checked 43 documents`
- Archive manifest：通过
- AGENT/SKILL 一致性：`agents=3, skills=8`
- Repository shape：通过
- Shellcheck：`checked 27 scripts`
- Shfmt：`checked 27 scripts`
- Secret scan：通过
- Docs lint：通过
- Skills dry-run：`linked 8 skills`
- Artifact check：通过
- Tools check strict：`missing=0`

归档阶段再次确认：

- `git status --short --branch`：`## main...origin/main`
- `git rev-list --count HEAD`：`1`
- `git log --oneline --decorate --max-count=3`：`a2ee7f7 (HEAD -> main, origin/main, origin/HEAD) chore: 建立知识库质量基线`
- `find . -type d -name "__pycache__"`：无输出
- `git status --short --ignored`：无输出

## 当前风险与未决项

1. 远端历史已覆盖，已有旧克隆的成员需要重新克隆，或执行明确的 fetch/reset 同步流程。
2. 服务端 pre-receive hook 如需强制门禁，还需要 Git 服务管理员部署。
3. CI runner 需要具备 `rtk`、`bash`、`python3`、`shellcheck`、`shfmt` 等基础能力。
4. NAS artifact 物理路径校验依赖 `KNOWLEDGE_ARTIFACT_NAS_ROOT`，未配置时只能做 manifest 级检查。
5. 知识库内容后续需要持续用 `scripts/check-all.sh` 作为合并前门禁，避免重新漂移。

## 建议后续动作

1. 团队成员统一同步到 `a2ee7f7`，旧 clone 不再基于历史分叉继续提交。
2. 在 Git 服务端部署 server hook 或至少启用 CI 必过策略。
3. 每次新增文档、工具、skill 后执行 `rtk bash scripts/check-all.sh`。
4. 需要发布稳定版本时使用仓库内 release 流程生成 tag 与 release note。

## 记忆整理边界

本次归档只作为会话证据与交接材料，不等同于长期 memory。以下信息不应进入长期 memory 或 memory candidate：个人工作区绝对路径、临时阶段性仓库组织方式、一次性执行过程细节、低复用的环境偶发现象。可沉淀的长期信息应仅限于可复用规则：知识库独立仓库边界、质量门禁、归档 report-only 策略、禁止把低质量环境噪音写入记忆。
