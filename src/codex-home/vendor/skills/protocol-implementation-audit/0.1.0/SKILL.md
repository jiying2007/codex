---
name: protocol-implementation-audit
description: Use when the user asks Codex to compare a protocol document, command specification, register table, binary layout, message schema, or interface contract against firmware/application implementation, logs, or test feedback to find field, unit, endian, scaling, state-machine, or compatibility mismatches.
version: 0.1.0
last_updated: 2026-06-15
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Protocol Implementation Audit

Use this skill to verify whether an implementation matches a protocol or interface document.

## Inputs

Accept any combination of:

- protocol documents, `.docx` exports, PDFs, Markdown specs, command lists, register tables, or message schemas;
- implementation paths for firmware, drivers, application modules, SDK APIs, or test tools;
- logs, captures, user feedback, calibration data, or measured values;
- old and new architecture paths when a protocol is being migrated.

## Workflow

1. Establish the contract:
   - identify source-of-truth document version, implementation revision, target device/profile, and compatibility assumptions;
   - convert document content into a field table instead of relying on prose memory.
2. Map implementation to contract:
   - trace command IDs, frame layout, units, scaling, signedness, endian, CRC/checksum, timeouts, retries, state transitions, and error codes;
   - include both encode and decode directions when they exist.
3. Check runtime evidence:
   - compare logs or captured values against expected field ranges and units;
   - flag mismatches between code comments, constants, tests, and observed behavior.
4. Classify findings:
   - `bug`: implementation contradicts the contract;
   - `spec-gap`: document is ambiguous or missing;
   - `compat-risk`: change may break upstream/downstream users;
   - `test-gap`: no evidence proves the mapping.
5. Plan the fix:
   - propose minimal code, spec, test, or migration updates;
   - preserve public protocol compatibility unless the user explicitly approves a breaking change.

## Output

Return:

- contract-to-code mapping table;
- findings with severity and evidence;
- compatibility and migration risks;
- recommended patch/test/spec updates;
- unresolved questions and missing artifacts.

## Guardrails

- Do not infer protocol values from unrelated chips or projects when official material exists.
- Do not silently change wire format, scaling, persistence layout, or backward compatibility.
- Do not treat a passing build as protocol validation; require logs, tests, captures, or explicit reasoning over encode/decode paths.
- Quote only short excerpts from proprietary documents and prefer file/section references.
