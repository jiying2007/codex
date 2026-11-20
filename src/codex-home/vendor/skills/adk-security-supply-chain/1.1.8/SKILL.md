---
name: adk-security-supply-chain
description: "用于第三方 Skill、脚本、依赖和参考资产引入前的来源、权限与供应链审查；不用于自动安装不可信包或把静态扫描当安全认证。"
version: 1.1.8
last_updated: 2026-11-20
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
- 防止第三方资产未经审查进入生产运行环境；建立可追溯的供应链安全审查流程，确保每个引入决策有据可查。

## Prerequisites
- 已明确候选资产来源、版本或 commit，以及安装范围：`core`、`optional`、`profile` 或 `reject`。

## Scope Gate（只选择适用的审查层）
- **source-only intake**：仅引用第三方方法、没有导入脚本/依赖或启动工具，不执行 SBOM/CVE/签名器；核来源、许可未知、指令注入与当前权限，输出 `unverified` 的候选，不推断运行安全。纯背景研究仍由外部方法分析 Skill 负责。
- **adoption preflight**：准备引入第三方 Skill/脚本/MCP 时，先只读核来源、可执行路径和权限；缺证明固定 `needs-fix`，不得自动安装工具验证。需扫描时绑定可信 `SECURITY_MODEL.md` 的不变量，以 `source-to-sink` 证据区分 `confirmed / false-positive / unverified`，覆盖状态 `inspected / omitted / unavailable`；细节延迟读取 `references/skill-scan-coverage.md`。
- **install / runtime readiness**：有实际安装或启用授权时，必须完成适用的 SBOM、CVE、签名/完整性、secret、permission/deny-path、tool schema、scope、回滚；不可运行或未知项不得用工具未报错代替通过。

## Workflow
1. 按 Scope Gate 决定需要哪些审查和安装/运行权限；完整工作流只对真实引入/启用候选执行，避免为只读方法研究重复装扫描器。
2. 来源审查：确认仓库可达性、维护状态、版本锚点。
3. 许可证审查：确认 LICENSE 与使用范围。
4. SBOM 生成：生成软件物料清单，记录所有直接与间接依赖。
5. CVE 扫描：检查已知漏洞，评估影响范围与修复状态。
6. 脚本审查：列出可执行脚本、危险命令、网络访问和写入路径。
7. 敏感信息审查：检查密钥、token、个人路径和内部域名；涉及凭证对象或整对象输出时，按 `references/skill-scan-coverage.md` 的 Generated serialization 检查。
8. 签名验证：验证资产完整性与发布者身份。
9. 运行态信任边界审查：确认 base URL、relay、MCP server、hooks、sandbox 和 approval policy。
10. 工具调用策略审查：为读文件、写文件、命令执行、网络访问、凭证读取列出 allow/deny 条件。
11. MCP/plugin readiness：核对暴露清单、schema/smoke、auth scope、依赖边界和回滚步骤。
12. Runtime Control Plane Audit：若候选资产暴露 slash command、MCP server、hook、permission profile 或外部 connector，记录 `slash_command_runtime_audit`、`mcp_runtime_contract`、`permission_profile_decision`、`approval_boundary`、`deny_path_test` 和 `rollback_path`。
13. 安装范围审查：确认仅进入 core/optional/profile/plugin 中的最小范围。
14. 回滚审查：给出移除方式和安装回退点。

上述后续编号按原顺序执行所需步骤；不同候选可跳过不适用的工具扫描，但必须注明 `not-scanned / reason / owner`，不能把跳过项算作成功。

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
`devkit.sh` 仅在已核 ADK 源码根且 helper 可读、确需维护 ADK 资产时运行。纯 Skill 消费使用目标项目已有验证入口；缺失记 `not-run` 与限制，不安装扫描器、不伪报通过。以下工具仅在适用且已授权时运行；`rg` 仅列路径，后续内容/路径先脱敏。保留退出码：0 有候选、1 无匹配、2 扫描错误。

```bash
rg --hidden --no-ignore -l --glob "!**/.git/**" "api[_-]?key|token|secret|password|PRIVATE KEY" <candidate_path>
find <candidate_path> -type f -perm -111
bash scripts/devkit.sh validate --strict
rg -l "license|LICENSE" <candidate_path>
rg -l "curl|wget|fetch|http|https" <candidate_path>
rg -l "writeFile|fs\.write|os\.path|open\(" <candidate_path>
rg -l "BASE_URL|base_url|mcp|hook|approval|sandbox" <candidate_path>
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
- Security Scan: security_model / invariant_ids / inspected / omitted / unavailable / source-to-sink / confirmed / false-positive / unverified:
- External Dependencies:
- Secret Scan: coverage / excluded / not-scanned / candidate-paths / redaction
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
- 敏感信息扫描应声明 hidden／ignored／binary／encrypted 等覆盖情况和排除项；未支持的类型标记 not-scanned，不得以普通 rg 零命中宣称全面无秘密。
- 签名验证结果必须记录在审查报告中，未签名资产必须标注风险等级。
- 涉及 MCP、hooks、provider relay 或命令执行时，必须附 tool-call policy 和至少一个 deny-path 验证。
- MCP/plugin 进入生产 profile 前必须附加载结果、暴露清单一致性和禁用回滚证据。
- slash command、MCP runtime 或 permission profile 缺少控制面审计、approval boundary 或 deny-path test 时，不得进入生产 profile。
