---
name: embedded-diagnostic-harness
description: "Use for embedded diagnostic harness work involving prog_tool, diag commands, strict/env suites, HIL/SIL evidence, expected return codes, invoke_ret/code semantics, API/HDI/component diagnostics, and production diagnostic CLI validation."
version: 1.0.0
last_updated: 2026-05-20
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Diagnostic Harness

Use this skill when logs, commands, or requirements revolve around embedded diagnostic CLIs and validation suites.

## Workflow

1. Identify the diagnostic surface:
   - command discovery;
   - suite taxonomy such as `strict`, `env`, `all`;
   - domains such as core, HDI, API, app, performance, OTA, storage, media, network.
2. Separate strict behavior from environment-dependent behavior.
3. Build an expected-result matrix:
   - command name;
   - mode;
   - required preconditions;
   - expected `code`;
   - expected `invoke_ret`;
   - pass/fail rule;
   - known hardware or service dependency.
4. Parse logs by summary and failing signatures first. Do not paste long repeated memory or hardware-stat blocks.
5. Fix harness semantics before fixing product code when false failures are caused by expected error codes or missing environment.
6. Validate with focused suites before `run all`.
7. Record HIL/SIL/manual evidence and residual hardware dependencies.

## Rules

- Do not treat every non-zero device return as a failure without checking expected semantics.
- Do not hide real initialization errors by weakening strict suites.
- Keep strict suites deterministic; move board/environment-dependent checks to env suites.
- Preserve production-friendly usage text and stable CLI behavior.

## Output

Include:

- command/suite matrix changes;
- failures reclassified as expected or real;
- validation command summaries;
- remaining hardware or service dependencies.
