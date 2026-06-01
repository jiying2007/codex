---
name: codex-usage-telemetry
description: Use when the user asks about Codex token usage, usage dashboards, stale `status` data, `usage-tail`, `usage-report`, rate-limit visibility, TUI usage views, or "今天用了多少 token". Prefer local Codex telemetry sources and existing `~/codex/scripts/usage-*.sh` wrappers.
version: 0.1.0
last_updated: 2026-05-31
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Codex Usage Telemetry

Use this skill to answer or improve local Codex usage visibility without relying on slow or stale `status` output.

## Sources

Prefer these local first-party sources:

- `~/.codex/sessions/**/*.jsonl`: near-real-time `token_count` events.
- `~/.codex/state_*.sqlite`: thread and goal-level accumulated usage.
- `~/codex/scripts/usage-report.sh`: stable report wrapper.
- `~/codex/scripts/usage-tail.sh`: live or single-shot terminal view.

Use logs sqlite only for diagnostics. Do not expose raw session messages unless the user explicitly asks and the content is sanitized.

## Workflow

1. Determine scope: current session, today, a date range, a specific thread, or dashboard behavior.
2. Prefer existing wrappers:
   - `rtk bash ~/codex/scripts/usage-report.sh --help`
   - `rtk bash ~/codex/scripts/usage-tail.sh --help`
3. If reporting usage, provide totals plus freshness:
   - total tokens;
   - input/output/reasoning/cache split if available;
   - source file or sqlite table used;
   - latest event timestamp.
4. If improving the tool, preserve the wrapper pattern:
   - shell wrapper locates `ROOT`;
   - wrapper sets `PYTHONPATH`;
   - implementation lives under `tools.codex_assets`;
   - commands are runnable from a non-repo cwd.
5. For UI/TUI changes, keep the first viewport dense and operational:
   - summary, active thread, recent delta, trend, alerts;
   - stable column widths;
   - fallback non-interactive mode for SSH.

## Guardrails

- Do not treat `status` as the telemetry source of truth.
- Do not print raw prompts, secrets, URLs with credentials, cookies, or auth material from session files.
- If sqlite or session files are unavailable, state the missing source and residual risk.
- Use `rtk` for shell commands in this environment.

## Validation

For code changes, run the narrowest useful checks:

- `rtk bash ~/codex/scripts/usage-report.sh --help`
- `rtk bash ~/codex/scripts/usage-tail.sh --help`
- a JSON or non-interactive report mode when available
- `rtk bash ~/codex/scripts/check.sh` when shared tooling is touched
