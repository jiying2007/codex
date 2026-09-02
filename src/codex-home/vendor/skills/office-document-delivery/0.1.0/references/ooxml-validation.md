# OOXML Validation

Use package checks after generating `.pptx`, `.xlsx`, or `.docx` files.

1. Run `unzip -t <file>` and treat a non-zero exit as invalid output.
2. Check required package parts: `[Content_Types].xml`, `_rels/.rels`, and the relevant `ppt/`, `xl/`, or `word/` tree.
3. Verify user-visible invariants from XML or a trusted library: requested title, required sheets/slides, expected weight totals or formulas, and explicit `待内部核对` markers.
4. Record package validity separately from visual rendering and business/brand approval.

Do not place a template, private source deck, customer material, or knowledge-base export in this Skill.
