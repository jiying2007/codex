# llm_tools v1.0.0 Release Memory Review

Date: 2026-05-18
Mode: report-only
Scope:
- /home/leiwenjun/bin/llm_tools
- /home/leiwenjun/bin/llm_tools/sigmastar-flasher
- /home/leiwenjun/bin/llm_tools/ota-packager

## Sources Checked

- /home/leiwenjun/.codex/memories/projects/llm_tools.md
- /home/leiwenjun/.codex/memories/projects/sigmastar_flasher.md
- /home/leiwenjun/.codex/memories/projects/ota_packager.md
- /home/leiwenjun/bin/llm_tools/releases/sigmastar-flasher/v1.0.0
- /home/leiwenjun/bin/llm_tools/releases/ota-packager/v1.0.0
- git logs of llm_tools, sigmastar-flasher, and ota-packager

## Current Git Snapshot

- llm_tools master: f6a2b19 fix(release): 限定签名状态仅记录可执行文件
- sigmastar-flasher master/tag v1.0.0: ef89aa1 chore(release): 切换首发版本到1.0.0
- ota-packager master/tag v1.0.0: b380c85 chore(release): 切换首发版本到1.0.0

## High-Signal Durable Facts

1. `llm_tools` is the mother repository for embedded tooling governance, tool registration, release orchestration, and cross-repository scripts.
2. The three repositories now use normal iterative Git workflow unless the user explicitly requests history rewriting.
3. Both `sigmastar-flasher` and `ota-packager` completed first formal release version `v1.0.0`.
4. Release layout is tool-first, then version-first: `releases/<tool>/v1.0.0/`.
5. Each formal tool release should include Linux artifact, Windows x64 portable artifact, Windows x64 installer artifact, `docs/usage-guide.md`, `docs/usage-guide.html`, `docs/usage-guide.pdf`, checksums, release notes, release manifest, and commit manifest.
6. Production/non-technical users should receive `usage-guide.pdf` first; `usage-guide.html` is the fallback readable format; Markdown is mainly for developers and source control.
7. Windows x64 is the authoritative Windows release baseline. Windows x86 remains experimental and must be explicitly requested and separately validated.
8. Authenticode signing support exists in the release chain, but unsigned artifacts may be produced when no certificate is configured. For strong production release, require certificate configuration and `WIN_SIGN_MODE=required`.
9. `release-manifest.json` should record Authenticode state only for executable files, not config files.
10. Release logs, checksums, machine-private paths, certificate secrets, and private package index credentials belong in archive or secure environment configuration, not long-term memory.

## Memory Drift Found

### llm_tools.md

Current memory lacks the current first-release baseline:
- `v1.0.0` is now the first formal release version.
- Formal release directories now include PDF/HTML/MD usage guides.
- Formal Windows release includes portable and installer artifacts under each tool/version directory.
- Authenticode status should be limited to executable artifacts.

### sigmastar_flasher.md

Current memory says Windows authoritative target is x64 EXE and x64 installer is optional. This is stale for formal GUI release packaging:
- Formal Windows release now includes x64 portable EXE and x64 installer.
- Production usage guide should point to release `docs/usage-guide.pdf` first.
- `sigmastar-flasher-gui` is the user-facing GUI artifact name.

### ota_packager.md

Current memory says Windows authoritative target is x64 GUI EXE. This is incomplete for formal release packaging:
- Formal Windows release now includes x64 GUI portable EXE and x64 installer.
- Release usage guide is a tool-user document and is separate from OTA business package output.
- Production usage guide should point to release `docs/usage-guide.pdf` first.

## Recommended Actions

- write-to-memory: update the three project memory files with short durable release facts.
- archive-only: keep full release file lists, hashes, logs, and commit details in release/archive material.
- drop-or-review: do not store private builder state, signing secrets, PyPI credentials, SSH details, or one-off command logs in memory.
- no-agents-change: current AGENTS rules already cover tool governance and memory curation boundaries; no immediate AGENTS promotion is required.

## Suggested Memory Updates

### /home/leiwenjun/.codex/memories/projects/llm_tools.md

- Update `last_updated` to `2026-05-18`.
- Add that first formal version is `v1.0.0`.
- Add formal release layout: `releases/<tool>/v<version>/` with Linux, Windows portable, Windows installer, usage-guide PDF/HTML/MD, manifests, checksums, release notes, and commit manifest.
- Add Authenticode state applies only to executable artifacts; require `WIN_SIGN_MODE=required` plus certificate for signed production releases.

### /home/leiwenjun/.codex/memories/projects/sigmastar_flasher.md

- Update `last_updated` to `2026-05-18`.
- Replace optional installer wording with formal Windows release baseline: x64 portable EXE plus x64 installer.
- Add release docs preference: PDF first for production users, HTML fallback, Markdown for developers.

### /home/leiwenjun/.codex/memories/projects/ota_packager.md

- Update `last_updated` to `2026-05-18`.
- Add formal Windows release baseline: x64 GUI portable EXE plus x64 installer.
- Add release docs preference: PDF first for production users, HTML fallback, Markdown for developers.
- Keep OTA `.tar.gz` business package output separate from tool release artifacts.

## Decision

Report generated only. No files under `~/.codex/memories` or project `AGENTS.md` were modified in this step.
