---
name: windows-gui-release-orchestration
description: Use when the user asks Codex to build, validate, troubleshoot, or release Windows GUI tools, PyInstaller executables, x64 portable EXE or installer artifacts, remote Windows build-machine runs, Authenticode signing gates, SHA256 verification, or cross-platform GUI release bundles for local tooling such as llm_tools, sigmastar-flasher, or ota-packager.
version: 0.1.0
last_updated: 2026-06-15
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Windows GUI Release Orchestration

Use this skill to handle Windows GUI release flows for local tools without rediscovering the build-machine, artifact, and validation boundaries.

## Inputs

Accept any combination of:

- tool name and version;
- repository path and release script path;
- Windows remote build command or log;
- generated EXE, installer, manifest, checksum, or signing status;
- Linux release artifact that must be paired with Windows artifacts;
- user requirement such as x64-only, installer required, smoke-test required, or signing required.

## Workflow

1. Establish release scope:
   - confirm tool name, version, target platform, release mode, and whether this is a dry-run, formal release, or troubleshooting task;
   - default Windows release target to x64 only unless the user explicitly requests x86 as an experimental validation path.
2. Check source and environment boundaries:
   - do not embed build-machine usernames, passwords, SSH keys, certificate passwords, private pip credentials, or local machine secrets in repo files, docs, memory, or final output;
   - prefer existing repository release scripts over ad hoc PowerShell or `cmd.exe` command construction.
3. Build artifacts:
   - produce portable GUI EXE and installer when the formal release baseline requires both;
   - keep CLI/core behavior testable before GUI wrapping;
   - keep source archives free of `.venv-win-*`, caches, and generated dependency environments.
4. Validate artifacts:
   - run the final Windows EXE smoke test, not only PyInstaller build success;
   - verify `release-manifest.json` parses;
   - normalize CRLF in checksum files before Linux-side `sha256sum -c`;
   - record signing state separately from build success.
5. Package and compare:
   - ensure release layout includes Linux artifact, Windows x64 portable artifact, Windows x64 installer artifact, usage docs, checksums, release notes, release manifest, and commit manifest when required by the tool;
   - verify artifact names and version strings are consistent across manifests, filenames, and docs.
6. Troubleshoot:
   - for SSH permission failures, inspect actual Windows user, admin authorized-keys location, file content, and ACLs;
   - for PowerShell or `.bat` argument failures, prefer environment variables or direct PowerShell invocation instead of manually concatenating `cmd.exe /c` strings;
   - for first-run slowness, consider wheelhouse or internal package mirror rather than committing dependency caches.

## Output

Return:

- release scope and target artifact list;
- command plan or observed command summary;
- validation checklist with pass/fail/blocked status;
- artifact manifest/checksum/signing summary;
- troubleshooting findings and next action;
- residual release risk.

## Guardrails

- Do not run remote Windows release, sign binaries, publish artifacts, or overwrite release directories without explicit user approval.
- Do not treat unsigned binaries as signed; keep signing state explicit.
- Do not promote x86 into the default release baseline without user approval and separate validation evidence.
- Do not expose private build-machine identity, credential paths, certificate material, or network secrets in the final answer.
