---
name: patent-disclosure-normalization
description: Use when the user asks to create, normalize, review, or archive patent disclosure documents, claim drafts, invention-point extraction, technical-effect mapping, or patent-disclosure-skill compatibility outputs from code, product ideas, diagrams, or research notes.
version: 0.1.0
last_updated: 2026-05-31
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Patent Disclosure Normalization

Use this skill to convert technical material into consistent patent-disclosure working drafts.

## Inputs

Accept any combination of:

- code or architecture notes;
- product behavior descriptions;
- UI, animation, device, firmware, or algorithm details;
- prior drafts of disclosures or claims;
- external patent-disclosure templates.

## Workflow

1. Establish scope:
   - invention title;
   - technical field;
   - source artifacts;
   - target output: disclosure, claims draft, normalization report, or archive note.
2. Extract invention points:
   - problem;
   - constraints;
   - technical solution;
   - key components and data flow;
   - beneficial effects;
   - alternatives and embodiments.
3. Separate evidence from drafting:
   - quote or reference only the minimal local source identifiers needed;
   - mark assumptions and missing measurements;
   - do not invent experimental results.
4. Normalize outputs:
   - one disclosure per invention unless the user asks for a bundle;
   - claims are separate from disclosure narrative;
   - maintain a trace table from source artifact to claim/supporting paragraph.
5. Archive only sanitized reusable notes under the approved archive path when requested.

## Guardrails

- This is drafting support, not legal advice.
- Do not expose confidential product details outside local files or user-approved destinations.
- Do not overwrite existing disclosure drafts without reading them first.
- Do not remove historical patent artifacts unless the user explicitly asks and the repository policy allows it.

## Output

Provide:

- invention-point table;
- normalized document list;
- assumptions and missing evidence;
- changed files or archive paths;
- validation performed, such as template compliance or filename checks.
