# Readiness Matrix

| Layer | Required evidence | Result | Gap / owner |
|---|---|---|---|
| Source/SIL | revision, tests, build, static analysis | pass/fail | — |
| Product dependencies | target ABI/architecture and dependency audit | pass/fail | — |
| Deployment identity | package digest/version/config equals tested source | pass/fail | — |
| Board/HIL | target-board scenario and failure-path evidence | pass/fail | — |
| External ownership | required product map, hardware, approval | pass/blocked | owner |

Use only layers required by the claim, but name omitted layers and why. A product-ready claim requires all applicable rows to pass.
