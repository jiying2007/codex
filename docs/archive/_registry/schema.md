# Archive Registry Schema

Archive v2 uses topic directories for physical layout and registry/meta fields for identity.

## Registry Files

- `projects.json`: project identity, aliases, repo paths, domain, default topics.
- `workstreams.jsonl`: long-running task lines under a project.
- `sessions.jsonl`: resumable session records, archive path, status, next action.
- `topics.json`: allowed topic/kind metadata and default retention.
- `schema.md`: this human-readable contract.

## Meta v2 Required Fields

Required v2 meta fields: `archive_id`, `topic`, `kind`, `scope`, `status`, `governance_status`, `memory_action`, `content_sha256`.

Recommended identity fields: `project_id`, `workstream_id`, `session_id`, `owner`, `next_action`, `source_repo`, `summary`, `tags`.

Project-specific entries must set `project_id` and match `_registry/projects.json`.
Session wraps must set `session_id` and be listed in `_registry/sessions.jsonl`.
Open entries must set `owner` and `next_action`.
Superseded entries must set `superseded_by`.
`destination` and `metadata` must be repository-relative paths so archive material remains portable across checkout locations.

## Physical Layout

Archive bodies must live directly under one topic directory:

```text
docs/archive/<topic>/<archive>.md
docs/archive/<topic>/<archive>.md.meta.json
```

Nested archive body directories such as `docs/archive/<topic>/<subtype>/<name>.md` are not valid. Use `topic`, `kind`, `project_id`, `workstream_id`, `session_id`, `tags`, and registry files for identity instead of directory nesting.

Canonical filenames use `YYYYMMDD-HHMMSS-slug.md`. Date-only filenames are not valid. The slug must not repeat `YYYY-MM-DD`, `YYYYMMDD`, or a second time prefix.

## Project Matching

`archive-note` resolves project identity in this order:

1. Explicit `--project`.
2. `--source-repo`.
3. Source file path.
4. Current working directory.

When multiple registered repo paths match, the longest path wins. This supports sub-repo matching such as `/home/leiwenjun/work/sigmastar` and `/home/leiwenjun/work/sigmastar/pcr02_ssc305_compile`.

## Gates

`archive-check` must pass before final/commit/apply when archive files changed:

- all archive entries have meta v2;
- all archive bodies are direct children of a registered topic;
- all archive filenames follow `YYYYMMDD-HHMMSS-slug.md` without repeated dates or times;
- `archive_id`, `destination`, and `metadata` match the live body/meta path;
- project-specific entries reference a known project;
- session-wrap entries are registered in `sessions.jsonl`;
- `content_sha256` matches the archive body;
- open/superseded entries include required follow-up fields;
- sensitive assignment patterns and credential block markers are absent.
