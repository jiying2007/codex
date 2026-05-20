---
name: archive-governance
description: "用于 docs/archive 归档治理：归档检查、归档修复、归档迁移、归档不合规、文件名规范、元数据/meta v2、项目/会话/工作流登记、未关闭归档会话检查、替代/废弃记录和 memory_action 边界；兼容 archive-check、archive-search 等命令名。"
version: 1.0.0
last_updated: 2026-05-20
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Archive Governance

Use this skill for governance of `~/codex/docs/archive`, not for writing a single summary note.

日常中文触发词包括：归档治理、归档检查、归档门禁、归档修复、归档迁移、归档不合规、归档元数据修复、归档文件名规范、归档索引治理、归档未关闭会话检查。

## When To Use

- `docs/archive` drift, conflicts, redundancy, bad filenames, or stale metadata.
- 归档目录、文件名、元数据、项目/会话/工作流登记、hash 或状态字段不合规。
- 归档检查、未关闭归档会话、替代/废弃记录或 memory promotion policy.
- `archive-search`, `archive-check`, `meta v2` 等命令名或技术名词被明确提到。

Prefer `knowledge-archive` for creating a new note, and `memory-curator` for deciding whether material belongs in memory.
Use direct archive search for read-only historical lookup; escalate to this skill only when archive index, metadata, status, or naming needs governance.

## Workflow

1. Inspect `docs/archive/README.md` and `docs/archive/_registry/`.
2. Run or plan `rtk bash scripts/archive-check.sh` before broad edits.
3. Classify each issue:
   - missing/invalid meta;
   - bad filename;
   - registry reference missing;
   - hash mismatch;
   - stale duplicate;
   - project-specific content promoted too broadly;
   - sensitive/raw runtime material.
4. Repair with the smallest durable change:
   - normalize filenames to `YYYYMMDD-HHMMSS-slug.md`;
   - update `*.meta.json` and `content_sha256`;
   - add registry entries when a project/workstream/session is durable;
   - mark near duplicates `superseded` before deleting anything.
5. Validate search behavior with targeted `archive-search` queries for affected project/session/workstream.
6. Run `archive-check` and the relevant repo check before final delivery.

## Rules

- Do not archive raw sessions, logs, caches, auth files, or private runtime state.
- Do not promote project-specific facts into global memory without review.
- Do not delete historical material unless the user explicitly asked for deletion or the file is a generated invalid duplicate with safe replacement.
- Keep archive content sanitized and useful for recovery, audit, or future engineering decisions.

## Evidence Template

```md
status: pass | needs-fix | BLOCKED
changed:
- <path>
checks:
- rtk bash scripts/archive-check.sh: <result>
- rtk bash scripts/archive-search.sh "<query>" --json: <result>
remaining:
- <risk or none>
```
