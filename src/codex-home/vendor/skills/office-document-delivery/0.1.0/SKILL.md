---
name: office-document-delivery
description: "Use when Codex needs to create or revise local PPTX, XLSX, DOCX, or companion Markdown deliverables such as training decks, presenter notes, OKR workbooks, and review materials. Preserve source files, keep unverified external facts explicit, and validate the resulting Office package before delivery."
version: 0.1.0
last_updated: 2026-09-02
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Office Document Delivery

Create usable office deliverables, not outlines. Keep source materials intact and make factual uncertainty visible.

## Workflow

1. Establish the output boundary: identify source files, requested deliverables, destination, required language, and whether replacement is explicitly allowed. Default to a new version beside the source.
2. Extract only confirmed source facts. Separate confirmed content, user-provided assumptions, and material that needs internal review. Never fill inaccessible knowledge-base content with plausible inventions.
3. Produce the full deliverable set: presentation/workbook/document plus a Markdown speaker script or change note when it materially helps use or review.
4. Validate structure and content:
   - run `unzip -t` for each generated OOXML package;
   - inspect package/XML structure when the office GUI is unavailable or unreliable;
   - check required titles, sheets, slide count, weights/formulas, and explicit review markers;
   - preserve the source and report generated paths separately.
5. State validation boundaries: package validity is not visual-layout or business-fact approval. Request human review for branding, private knowledge bases, or unavailable source material.

## Tooling Choice

- Use an existing approved template when supplied; do not invent brand assets or visual claims.
- Use a reliable local document library or direct OOXML edits when GUI automation is unavailable. Do not claim visual rendering passed unless it was actually inspected.
- Read `references/ooxml-validation.md` for package-level checks and factual-boundary rules.

## Output

Return generated paths, preserved-source paths, compact validation evidence, facts marked for review, and remaining human-review items.

## Guardrails

- Do not overwrite source files unless explicitly authorized.
- Do not persist credentials, private exports, or raw knowledge-base content in the Skill.
- Do not state that a deck is commercially, legally, or brand approved based only on package validation.
