---
name: adk-security-supply-chain
description: 第三方技能、脚本与参考资产引入前的安全和供应链审查
version: 1.0.0
last_updated: 2026-05-06
triggers:
  - "供应链审查"
  - "第三方引入"
  - "安全审查"
non_triggers:
  - 仅读取参考仓库做背景调研
  - 修改本仓已有文档且不引入外部资产
inputs:
  - 候选资产路径、许可证、脚本清单、外部依赖、安装范围
outputs:
  - 安全审查结论、阻塞项、允许范围、回滚要求
constraints:
  - 未知许可证或敏感信息风险未处理前不得进入 core
  - 可执行脚本必须说明用途与验证命令
---

# adk-security-supply-chain

## Goal
- 防止第三方资产未经审查进入 `~/.codex` 生产运行环境。
- 建立可追溯的供应链安全审查流程，确保每个引入决策有据可查。

## Prerequisites
- 已明确候选资产来源、版本或 commit。
- 已明确安装范围：`core`、`optional`、`profile` 或 `reject`。

## Workflow
1. 来源审查：确认仓库可达性、维护状态、版本锚点。
2. 许可证审查：确认 LICENSE 与使用范围。
3. SBOM 生成：生成软件物料清单，记录所有直接与间接依赖。
4. CVE 扫描：检查已知漏洞，评估影响范围与修复状态。
5. 脚本审查：列出可执行脚本、危险命令、网络访问和写入路径。
6. 敏感信息审查：检查密钥、token、个人路径和内部域名。
7. 签名验证：验证资产完整性与发布者身份。
8. 安装范围审查：确认仅进入 core/optional/profile 中的最小范围。
9. 回滚审查：给出移除方式和安装回退点。

## SBOM 生成
```bash
# 使用 syft 生成 SBOM
syft <candidate_path> -o spdx-json > sbom.spdx.json

# 使用 cyclonedx 生成 SBOM
cyclonedx-bom -o sbom.json

# 列出所有依赖
cat sbom.spdx.json | jq '.packages[] | .name + " " + .versionInfo'
```

## CVE 扫描
```bash
# 使用 grype 扫描已知漏洞
grype sbom:sbom.spdx.json --output table

# 使用 trivy 扫描目录
trivy fs --security-checks vuln <candidate_path>

# 使用 npm audit（Node.js 项目）
npm audit --json | jq '.vulnerabilities'

# 使用 pip-audit（Python 项目）
pip-audit -r <requirements.txt> --format json
```

## 依赖审计
```bash
# 检查依赖树
cat package.json | jq '.dependencies, .devDependencies'

# 检查 lock 文件一致性
npm ci --dry-run 2>&1 | grep "added\|removed\|changed"

# 检查许可证合规
license-checker --summary --production

# 列出可执行文件
find <candidate_path> -type f -perm -111 -exec ls -la {} \;
```

## 签名验证
```bash
# 验证 GPG 签名
gpg --verify <signature_file> <artifact_file>

# 验证 npm 包签名
npm audit signatures

# 验证 Docker 镜像签名
cosign verify <image_digest>

# 检查 checksum
sha256sum -c <checksum_file>
```

## Commands
```bash
# 搜索敏感信息
rg -n "api[_-]?key|token|secret|password|PRIVATE KEY" <candidate_path>

# 列出可执行文件
find <candidate_path> -type f -perm -111

# 验证仓库结构
bash scripts/devkit.sh validate --strict

# 生成审查报告
rg -n "license|LICENSE" <candidate_path> | head -20

# 检查网络访问
rg -n "curl|wget|fetch|http|https" <candidate_path>

# 检查写入路径
rg -n "writeFile|fs\.write|os\.path|open\(" <candidate_path>
```

## Evidence Template
```md
- Source + Version:
- License Decision:
- SBOM Summary:
- CVE Scan Results:
- Executable Scripts:
- External Dependencies:
- Secret Scan:
- Signature Verification:
- Install Scope:
- Rollback Path:
- Final Decision:
```

## Failure Handling
- 存在明文凭证、未知许可证或不可解释脚本时，结论为 `reject` 或 `needs-fix`。
- CVE 扫描发现高危漏洞（CVSS >= 7.0）时，必须等待修复或给出缓解方案。
- 签名验证失败时，必须确认资产完整性后再继续审查。
- SBOM 生成失败时，手动列出依赖并记录审查范围限制。

## Quality Gate
- 进入 `core` 前必须完成安全与供应链审查，包括 SBOM 和 CVE 扫描。
- 进入 `optional/profile` 前必须有最小安装范围与回滚路径。
- 所有可执行脚本必须说明用途，禁止引入用途不明的脚本。
- 敏感信息扫描必须覆盖所有文件类型，包括二进制和配置文件。
- 签名验证结果必须记录在审查报告中，未签名资产必须标注风险等级。
