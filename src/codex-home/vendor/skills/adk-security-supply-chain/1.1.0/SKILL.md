---
name: adk-security-supply-chain
description: 第三方技能、脚本与参考资产引入前的安全和供应链审查
version: 1.1.0
last_updated: 2026-07-07
triggers:
  - "供应链审查"
  - "第三方引入"
  - "安全审查"
  - "MCP 安全"
  - "工具调用策略"
non_triggers:
  - 仅读取参考仓库做背景调研
  - 修改本仓已有文档且不引入外部资产
inputs:
  - 候选资产路径、许可证、脚本清单、外部依赖、安装范围、运行态权限
outputs:
  - 安全审查结论、阻塞项、允许范围、MCP/plugin readiness、tool-call policy、回滚要求
constraints:
  - 未知许可证或敏感信息风险未处理前不得进入 core
  - 可执行脚本必须说明用途与验证命令
  - MCP/server/API relay 未声明信任边界前不得启用工具调用
  - slash command、MCP server 或 permission profile 进入运行态前必须有控制面审计和拒绝路径
---

# adk-security-supply-chain

## Goal
- 防止第三方资产未经审查进入生产运行环境。
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
8. 运行态信任边界审查：确认 base URL、relay、MCP server、hooks、sandbox 和 approval policy。
9. 工具调用策略审查：为读文件、写文件、命令执行、网络访问、凭证读取列出 allow/deny 条件。
10. MCP/plugin readiness：核对暴露清单、schema/smoke、auth scope、依赖边界和回滚步骤。
11. Runtime Control Plane Audit：若候选资产暴露 slash command、MCP server、hook、permission profile 或外部 connector，记录 `slash_command_runtime_audit`、`mcp_runtime_contract`、`permission_profile_decision`、`approval_boundary`、`deny_path_test` 和 `rollback_path`。
12. 安装范围审查：确认仅进入 core/optional/profile/plugin 中的最小范围。
13. 回滚审查：给出移除方式和安装回退点。

## Runtime Boundary Checklist
- Provider/API relay：默认只允许官方或已审查端点；非标准 base URL 必须有 owner、用途、凭证边界和关闭方式。
- MCP server：必须声明 command、args、cwd、env、网络目标、读写路径和工具集合。
- Tool call：LLM 返回的调用请求视为不可信输入，执行前由本地 policy 确定允许或拒绝。
- Hooks：只允许做 secret scan、validator、lint/test gate 和审计记录，不得静默修改运行配置。
- Audit log：高风险调用至少记录 tool、args 摘要、cwd、policy decision、exit code。

## MCP / Plugin Readiness
- MCP 必须有 tool/resource/prompt 暴露清单、输入输出 schema、runtime MCP list 或 inspector/smoke 证据。
- OAuth/API token 必须声明最小 scope、凭证来源、轮换和撤销方式。
- 从 skill 晋级 plugin 时，必须声明 plugin manifest、owner、version、license、profile 绑定和 rollback。
- 缺少 deny-path guard test、隐藏工具或运行态清单漂移时，结论为 `needs-fix`。

## Commands
```bash
rg -n "api[_-]?key|token|secret|password|PRIVATE KEY" <candidate_path>
find <candidate_path> -type f -perm -111
bash scripts/devkit.sh validate --strict
rg -n "license|LICENSE" <candidate_path> | head -20
rg -n "curl|wget|fetch|http|https" <candidate_path>
rg -n "writeFile|fs\.write|os\.path|open\(" <candidate_path>
rg -n "BASE_URL|base_url|mcp|hook|approval|sandbox" <candidate_path>
syft <candidate_path> -o spdx-json > sbom.spdx.json
grype sbom:sbom.spdx.json --output table
trivy fs --security-checks vuln <candidate_path>
gpg --verify <signature_file> <artifact_file>
sha256sum -c <checksum_file>
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
- verification_command_safety:
  - command_id:
  - source:
  - trust_level:
  - unsafe_shell_tokens:
  - mutates_state:
  - network_required:
  - review_status:
- Runtime Trust Boundary:
- Runtime Control Plane Audit:
  - slash_command_runtime_audit:
  - mcp_runtime_contract:
  - permission_profile_decision:
  - approval_boundary:
  - deny_path_test:
  - rollback_path:
- MCP/Plugin Readiness:
- Tool-call Policy:
- Guard Test:
- Install Scope:
- Rollback Path:
- Final Decision:
```

## Failure Handling
- 存在明文凭证、未知许可证或不可解释脚本时，结论为 `reject` 或 `needs-fix`。
- CVE 扫描发现高危漏洞（CVSS >= 7.0）时，必须等待修复或给出缓解方案。
- 签名验证失败时，必须确认资产完整性后再继续审查。
- SBOM 生成失败时，手动列出依赖并记录审查范围限制。
- 非标准 base URL 或 MCP server 无 owner/用途/权限边界时，结论为 `needs-fix`。
- 高风险工具缺少 guard test 或拒绝样例时，不得进入生产 profile。
- MCP/plugin 缺少暴露清单、scope、smoke 或 rollback 时，不得进入生产 profile。

## Quality Gate
- 进入 `core` 前必须完成安全与供应链审查，包括 SBOM 和 CVE 扫描。
- 进入 `optional/profile` 前必须有最小安装范围与回滚路径。
- 所有可执行脚本必须说明用途，禁止引入用途不明的脚本。
- 敏感信息扫描必须覆盖所有文件类型，包括二进制和配置文件。
- 签名验证结果必须记录在审查报告中，未签名资产必须标注风险等级。
- 涉及 MCP、hooks、provider relay 或命令执行时，必须附 tool-call policy 和至少一个 deny-path 验证。
- MCP/plugin 进入生产 profile 前必须附加载结果、暴露清单一致性和禁用回滚证据。
- slash command、MCP runtime 或 permission profile 缺少控制面审计、approval boundary 或 deny-path test 时，不得进入生产 profile。
