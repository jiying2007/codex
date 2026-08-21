# Activity Facts v2 Contract

Require `schema_version=2` and `kind=knowledge-hub.activity-facts-v2`.

Required fields: `status`, `period_kind`, `scope`, `detail`, `timezone`, `period.start/end`, `subject`, `project_id`, `summary`, `work_items[]`, `registry_activity[]`, `git_activity[]`, `source_coverage`, `warnings[]`, and `privacy`.

All privacy flags must show no raw session/log, credentials, absolute workspace paths, identity inference, memory write, or external write. Return `needs-fix` for a missing or unsafe flag.

Only `work-activity-item` schema v2 is valid. Require explicit `item_id`, `subject_id`, `activity_date`, `title`, `status`, `verification`, and `raw_content_stored=false`. A verified done item requires at least one bounded evidence reference.
