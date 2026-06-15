---
name: embedded-log-triage
description: Use when the user asks Codex to analyze embedded serial logs, boot logs, dmesg output, reset traces, stress-test logs, OTA/prog logs, or pasted device logs to find anomalies, form hypotheses, propose next probes, or decide whether a firmware/SOC/MCU behavior is stable enough to proceed.
version: 0.1.0
last_updated: 2026-06-15
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Log Triage

Use this skill to turn raw embedded logs into a compact diagnosis and next-action plan.

## Inputs

Accept any combination of:

- pasted serial, bootloader, app, dmesg, watchdog, OTA, or prog logs;
- log file paths such as `Serial_*.log`;
- known-good logs for comparison;
- test conditions, loop count, reset count, firmware version, branch, board, or power-cycle method;
- related source paths or protocol documents.

## Workflow

1. Preserve evidence boundaries:
   - identify exact log source, timestamp range, firmware/version hints, board context, and whether logs are complete or truncated;
   - sanitize credentials, IPs, tokens, and private paths in user-facing summaries when not essential.
2. Build a timeline:
   - separate bootloader, kernel, driver, app, OTA/prog, and test-harness phases;
   - mark resets, retries, long gaps, repeated markers, CRC/hash changes, watchdog events, mount/partition errors, and state transitions.
3. Compare against expectations:
   - use known-good logs, project memories, README/runbook, source code, and protocol docs when available;
   - distinguish hard evidence from inference.
4. Rank hypotheses:
   - prioritize by evidence strength, blast radius, and whether the next probe can falsify it;
   - call out hardware/power/timing explanations only when the log supports them or the user supplied test evidence.
5. Produce next probes:
   - propose the smallest instrumentation, command, register dump, counter, or stress condition needed next;
   - avoid broad rewrites until the log points to a specific failing phase.
6. Close with a decision:
   - stable / needs more data / unsafe to release / safe to submit with stated residual risk.

## Output

Return a concise report with:

- source summary;
- timeline and anomaly table;
- likely root-cause hypotheses with confidence;
- next probes or patch plan;
- release/commit risk decision;
- missing evidence.

## Guardrails

- Do not claim root cause from a single ambiguous marker.
- Do not paste long raw logs back to the user; quote only short identifiers or lines needed as evidence.
- Do not modify production scripts or firmware before the failing phase is identified unless the user explicitly requests an implementation.
- For destructive recovery, flash erase, partition wipe, force push, or NAS publish actions, require explicit user instruction and normal approval gates.
