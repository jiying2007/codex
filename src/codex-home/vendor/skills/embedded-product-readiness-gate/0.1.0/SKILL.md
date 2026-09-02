---
name: embedded-product-readiness-gate
description: "Use when assessing whether embedded firmware, application, integration, or release work is source-ready, product-ready, or blocked; especially for cross-builds, platform migrations, plugin ABI, product dependencies, deployment identity, board HIL, or external-owner gates. Prevent Host/SIL or coverage results from being overstated as product delivery."
version: 0.1.0
last_updated: 2026-09-02
origin: local-chronicle-derived
lifecycle: iterative-local
---

# Embedded Product Readiness Gate

Classify readiness from evidence, not from the strongest available test result.

## Evidence Layers

Evaluate every applicable layer independently:

1. **Source/SIL** — reviewed source, unit/integration tests, static checks, Host build, and coverage.
2. **Product dependencies** — target architecture, ABI, third-party libraries, product configuration, and licensing/owner acceptance where applicable.
3. **Deployment identity** — target binary/image/package is bound to the tested commit, digest, version, and configuration.
4. **Board/HIL** — real target board, peripherals, timing, power, acoustic/mechanical conditions, and failure-path behavior.
5. **External ownership** — required product map, hardware, library, approval, or operator evidence is available and accepted.

## Workflow

1. Freeze the claim being evaluated and list its required evidence layers.
2. Map each evidence item to one layer, command/source, timestamp or revision, result, and gap. Do not let one layer satisfy another.
3. Verify architecture and ABI before accepting a cross-build as a product dependency result.
4. Verify deployment identity before interpreting HIL logs. Treat stale device binaries, unknown images, or unbound artifacts as `needs-fix` or `blocked`.
5. Produce the narrowest truthful result:
   - `source-ready` when only layer 1 is complete;
   - `integration-ready` when layers 1–3 are complete but HIL/owner evidence remains;
   - `product-ready` only when all required layers pass;
   - `blocked` when an external dependency or owner is missing;
   - `needs-fix` when any observed layer fails or evidence conflicts.
6. State the next evidence-producing action and its owner; do not substitute historical probes for the missing layer.

## Output

Return an evidence matrix, explicit readiness label, blockers, and smallest next validation action. Read `references/readiness-matrix.md` for the minimum template.

## Guardrails

- Do not call cross-build, Host tests, coverage, or a simulator result board/HIL evidence.
- Do not call an artifact deployed without revision/digest/config binding product evidence.
- Do not silently downgrade missing plugins, ABI mismatches, or target libraries.
- Do not convert an external-owner gap into an engineering pass.
