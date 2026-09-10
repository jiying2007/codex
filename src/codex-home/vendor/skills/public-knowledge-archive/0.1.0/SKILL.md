---
name: public-knowledge-archive
description: Archive user-specified public websites or knowledge bases with an explicit allowlist, robots.txt checks, bounded discovery, content hashes, provenance index, local classification, and incremental refresh. Use for 归档公开知识库、归档公开语雀、公开资料增量归档、public knowledge archive; never use for private pages, login-required content, bypassing verification, or unrestricted crawling.
version: 0.1.0
last_updated: 2026-09-03
---

# Public Knowledge Archive

Archive only public pages that the user explicitly identifies. This skill is independent from `browser-reader`; it must not change browser-reader, agent-browser, credential, cookie, or authentication policy.

## Required boundary

- Require explicit `--source` URLs and `--allow-domain` values for every run.
- Public-only: no login, authentication header, cookie, browser-profile import, CAPTCHA bypass, source-site write, or private-page access.
- Respect `robots.txt`; if unavailable or disallowed, record `blocked-robots` and do not archive the page.
- Default to `--max-pages 20 --max-depth 1`; never exceed 100 pages or depth 2 in one run.
- Archive output must be outside Codex source/runtime directories. Do not put public page bodies in skills, manifests, session logs, memories, or credentials.
- Preserve provenance: canonical URL, final URL, retrieval time, content SHA-256, category, public status, depth, and local path.

## Workflow

1. Confirm the user has named the public source and category. If the target is not explicit, ask for the URL; do not discover arbitrary sites.
2. Select the narrowest domain allowlist. For the current public Yuque sources, use only `yuque.com`.
3. Use the archive tool with `--dry-run` first for an unfamiliar site or an expanded source set.
4. Review records. Stop on `access-gated`, `dynamic-shell`, `blocked-robots`, `blocked-domain`, `blocked-redirect`, or `unsupported-content`; do not retry using a different identity or bypass.
5. Run without `--dry-run` only after the bounded plan is acceptable. Keep the default limits unless the user explicitly asks for a bounded increase.
6. For repeated runs, use the same output directory. Content hashes make unchanged pages index-only; use `--refresh` only when a fresh body write is required.
7. Report archive path, record counts by status, source URLs, limits, and any blocked pages. Do not claim private or gated content was archived.

## Tool

Run from any working directory:

```bash
rtk python3 ~/codex/tools/codex_assets/public_knowledge_archive.py \
  --source "https://www.yuque.com/aiui/zzoolv" \
  --source "https://www.yuque.com/caixueyang/kb" \
  --allow-domain yuque.com \
  --output-dir /path/to/public-archive/yuque-aiui \
  --category yuque-public-aiui \
  --max-pages 20 \
  --max-depth 1 \
  --dry-run
```

Read [references/archive-contract.md](references/archive-contract.md) before changing limits, output layout, or allowlist behavior.

## Failure handling

- `access-gated`: record only the gate status and URL; request a public share link or user-provided export. Do not log in.
- `dynamic-shell`: the public HTTP response contains only a JavaScript shell, not usable page content. Request a public export/index or use an explicitly authorized single-page rendered read; do not archive the shell title as a document.
- `blocked-robots`: report the restriction; do not archive or use alternate fetch methods.
- `blocked-domain` / `blocked-redirect`: keep the source boundary; require the user to explicitly add a narrow additional domain before a new run.
- `unsupported-content`: record metadata only. Ask for an explicit archive format/workflow for PDFs, binaries, or media.
- `fetch-error`: retain the error record and retry only on a later bounded run; do not rotate IPs, identities, or headers.

## Output contract

```text
<output-dir>/
  latest-run.json        # bounded run summary
  index.jsonl            # append-only provenance index
  pages/<stable>.md      # public text with source and SHA-256 metadata
```

The archive is a local reference cache, not a statement that the archived source is complete, licensed for redistribution, current, or product-verified.
