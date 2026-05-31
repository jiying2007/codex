# Patent Disclosure Skill And Three-Patent Portfolio Archive

## Source

- Project: `xcrz_sigmastar_demo/examples/lvgl`
- Date: 2026-05-30
- Skill reference: `https://github.com/handsomestWei/patent-disclosure-skill`
- Local reference clone: `/tmp/patent-disclosure-skill`
- Archive purpose: preserve the reusable patent disclosure workflow, generated artifacts, validation evidence, and quality improvement recommendations for the retained three patent candidates after removing the safe OTA candidate from the active portfolio.

## Skill Handling Decision

The third-party `patent-disclosure-skill` was read and used as a workflow/template reference. It was not installed into live Codex skill paths and was not promoted into `~/.codex`.

Referenced workflow files:

1. `SKILL.md`
2. `prompts/disclosure_builder.md`
3. `prompts/template_reference.md`
4. `prompts/disclosure_self_check.md`
5. `prompts/iteration_context.md`
6. `prompts/merger.md`
7. `prompts/prior_art_search.md`
8. `tools/README.md`

Temporary local toolchain used:

1. Python venv: `/tmp/patent_skill_venv`
2. Node tools: `/tmp/patent-disclosure-skill/tools/node_modules`
3. Playwright Chromium installed for CNIPA script attempts.
4. `matplotlib==3.7.5` was used because local Python is 3.8.10.
5. `mmdc` was validated with a minimal mermaid sample.

Security/supply-chain notes:

1. The third-party skill was not imported into the Codex live runtime.
2. `npm install` in the temporary skill tools directory reported 6 moderate and 1 high audit findings; the tooling was used only for local conversion and was not adopted as a project dependency.
3. CNIPA script dependencies were installed, but three search attempts timed out around 120 seconds; public Web/Google Patents/Linux MTD/AOSP sources remain the fallback prior-art sources.

## Patent Artifacts

All artifacts are under:

```text
outputs/patent_disclosure/
```

### 1. Multi-source Eye Animation

- Disclosure Markdown: `一种多源创作输入驱动的端侧轻量化眼神动画生成显示方法及系统_20260530154742.md`
- Disclosure Word: `一种多源创作输入驱动的端侧轻量化眼神动画生成显示方法及系统_20260530154742.docx`
- Claims Markdown: `权利要求书_一种多源创作输入驱动的端侧轻量化眼神动画生成显示方法及系统_20260530154742.md`
- Claims Word: `权利要求书_一种多源创作输入驱动的端侧轻量化眼神动画生成显示方法及系统_20260530154742.docx`
- Figure/formula assets: `figures_eye/`

Quality status: strongest as a product-facing platform patent. It covers multi-source creation, constrained AI/mobile input, video-as-reference, parameter-domain conversion, binary runtime assets, quality gates, embedded display playback, and telemetry feedback.

Recommended improvements:

1. Add CNIPA/Google Patents prior-art set focused on Chinese robot expression/display patents.
2. Add a short binary file field table for `animbin` in the claims support section.
3. Add measured resource deltas, such as Flash/RAM/frame-time savings versus video or PNG sequence playback.
4. Consider splitting into two filing families if budget allows: generation pipeline and device-side lightweight playback.

### 2. Multi-sensor Production Test, Calibration, And Diagnostic Closure

- Disclosure Markdown: `一种宠物机器人多传感器产测标定与诊断命令闭环方法及系统_20260530204854.md`
- Disclosure Word: `一种宠物机器人多传感器产测标定与诊断命令闭环方法及系统_20260530204854.docx`
- Claims Markdown: `权利要求书_一种宠物机器人多传感器产测标定与诊断命令闭环方法及系统_20260530204854.md`
- Claims Word: `权利要求书_一种宠物机器人多传感器产测标定与诊断命令闭环方法及系统_20260530204854.docx`
- Figure/formula assets: `figures_multisensor/`

Quality status: strong engineering patent candidate. The novelty is in combining production-mode isolation, diagnostic command profile routing, multi-sensor calibration state machine, PCBA status publishing, factory persistence, and automatic failure handling.

Recommended improvements:

1. Add more concrete command examples and result schema examples.
2. Add factory data version/CRC structure to support persistence claims.
3. Strengthen dependent claims around profile isolation and provider lifecycle.
4. Collect production-line evidence: time saved, retest reduction, false failure reduction, or traceability improvements.

### 3. Edge-side Multimodal Companion Behavior Orchestration

- Disclosure Markdown: `一种宠物机器人端侧多模态陪伴行为自动编排方法及系统_20260530204854.md`
- Disclosure Word: `一种宠物机器人端侧多模态陪伴行为自动编排方法及系统_20260530204854.docx`
- Claims Markdown: `权利要求书_一种宠物机器人端侧多模态陪伴行为自动编排方法及系统_20260530204854.md`
- Claims Word: `权利要求书_一种宠物机器人端侧多模态陪伴行为自动编排方法及系统_20260530204854.docx`
- Figure/formula assets: `figures_behavior/`

Quality status: strong product-experience patent candidate. The differentiator is edge-side behavior orchestration with multimodal blackboard state, pet-friendly constraints, VAD/audio resource coupling, AI/mobile intent sandboxing, and feedback optimization.

Recommended improvements:

1. Strengthen novelty over remote pet interaction devices and emotional pet-expression robots.
2. Add explicit behavior conflict matrix or priority table to support arbitration claims.
3. Add examples of unsafe AI/mobile intent rejection and conversion into safe templates.
4. Add evidence from actual task configuration values and behavior logs where available.

## Cross-portfolio Quality Assessment

Overall quality: good enough for attorney review and first-round patentability discussion. The active portfolio now keeps three candidates: eye animation, multi-sensor production test/calibration, and edge-side multimodal companion behavior orchestration.

Main remaining gaps:

1. CNIPA prior-art search timed out; a later manual CNIPA search should be done before filing.
2. Claims are currently method-focused. Attorney should consider adding system/device/computer-readable-medium claim sets.
3. The strongest filing order is likely:
   - Eye animation platform.
   - Multimodal companion orchestration.
   - Multi-sensor production test/calibration.
4. The safe OTA filing was removed from the active portfolio because its prior-art density is higher and the current product-facing patent value is lower than the retained three candidates.
5. The eye animation filing may be split if budget allows because generation pipeline and device-side playback can each support a distinct invention.

## Validation Evidence

1. Three retained disclosure Word files were generated.
2. Three retained claims Word files were generated.
3. Mermaid diagrams and formulas were rendered to PNG for the disclosure documents.
4. The safe OTA Markdown, Word, and `figures_ota/` artifacts were removed from the active delivery directory.
5. Historical residual files for the three pet-robot patents were removed.

## Next Actions

1. Perform CNIPA manual or browser-assisted prior-art review.
2. Ask patent counsel to convert each claims draft into formal method/system/device/media claim sets.
3. Add implementation evidence tables for measured resource savings, production-line yield/time, and behavior engagement metrics.
4. Decide whether to split the eye animation patent into two filings.
