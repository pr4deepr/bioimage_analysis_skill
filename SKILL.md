---
name: bioimage-analysis
description: >
  Guide users through image segmentation and measurement for biological
  microscopy data. Covers classical (scikit-image, FIJI) and deep learning
  (Cellpose, StarDist, nnUNetv2) approaches. Use this skill when users mention:
  cell segmentation, nucleus detection, object measurement, scikit-image,
  Cellpose, StarDist, napari, FIJI, image quantification, morphological
  measurements, intensity measurements, fluorescence analysis, or any task
  involving identifying and measuring objects in microscopy images. Even if the
  user just says "I have microscopy images and need to analyze them", use this skill.
commands:
  - name: bio
    description: Start bioimage analysis workflow
  - name: bio:plan
    description: Assess image and create analysis plan
  - name: bio:run
    description: Execute existing analysis plan
  - name: bio:qc
    description: Run QC checklist on segmentation results
  - name: bio:measure
    description: Extract measurements from labels
  - name: bio:status
    description: Show current analysis state
---

# Bioimage Analysis

Four rules:
1. **Look first, then propose.** Assess the image and context before running anything.
2. **Check the active env, never blind-install.** Before installing any package, check the active Python environment first (glob `site-packages/`). Only scan other envs if the active one is missing tools. Only install as a last resort. See `references/environment.md`.
3. **Close the feedback loop.** Every step that produces output: show it with matplotlib, run automated QC (`references/quality-control.md`), then ask the user to evaluate. Never say "check the output."
4. **Ask focused questions, then execute.** Up to 2-3 questions to understand the biological question and data. Infer everything else from context. Never ask technical implementation questions.

## User Interaction

- Gauge user level from context: terminology, file paths, how they describe their problem
- "Segment nuclei using StarDist" → minimal questions, they know what they want
- "I have microscopy images" → more guidance needed
- Question budget: up to 3 focused questions, then execute
- Priority: (1) biological question, (2) what's in the image, (3) how results will be used
- Never ask: technical implementation, environment, or "would you like me to..." questions
- Adapt: biology terms → run directly, explain in scientific terms. Code terms → show code
- Report results in scientific language matching the user's domain

## Visualization

**matplotlib is the default viewer.** Always available, zero setup, publication-quality.

**napari-mcp is opt-in.** Only set up if the user explicitly wants interactive viewing or already has napari running. Offer once, early: "I'll use matplotlib for visuals. If you'd like interactive napari, I can help set that up." Then move on.

See `references/cookbook-visualization.md` for all display patterns.

## State Files

- **ANALYSIS.md**: Always create — the analysis plan and record of what was done
- **STATE.md**: Only for multi-session analyses or when the user wants to resume later. Not needed for single-session work.

See `references/state-templates.md` for formats.

## On Activation

1. If `.bioimage-analysis/STATE.md` exists → read it, offer to continue
2. Otherwise → start fresh, no scanning needed yet
3. Check environment only when you're about to run code (not upfront)
4. Start talking immediately — ask about the biology, not the setup

## Workflow

### 1. Assess
Read the image, scan directory for context (custom models, configs, other images). Write ANALYSIS.md with the plan. Reference `references/cookbook-io.md` for reading patterns.

Use the segmentation decision tree (`references/segmentation.md`) to pick the approach. Don't present all options to the user — pick the best match and propose it.

### 2. Check Environment (just-in-time)
Before running segmentation code, check the active env for the needed package. See `references/environment.md` — Quick Path first, Broader Scan only if needed. This takes milliseconds, not a background worker.

### 3. Execute
Run the pipeline step by step. After every visual step: show matplotlib output, run automated QC checks, present results as preliminary — "Here's a first pass, does this look right?" Reference `references/cookbook-segmentation.md` and `references/cookbook-pipeline.md` for complete patterns.

### 4. Iterate
Adjust and re-run based on feedback. If not working after 2-3 tries: try a different tool, search forum.image.sc, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning. Don't over-tune — if parameters need drastic per-image adjustment, the approach is wrong.

### 5. Measure & Export
Save organized outputs (labels, QC overlays, CSV tables). Reference `references/cookbook-measurements.md` for extraction patterns. Connect back to biology — answering the biological question is the endpoint, not raw measurements. Run automated QC checks before exporting — see `references/quality-control.md`.

## Slash Commands

| Command        | Behavior                                                    |
|----------------|-------------------------------------------------------------|
| `/bio`         | Start bioimage analysis — assess image and propose pipeline |
| `/bio:plan`    | Assess image, check environment, write ANALYSIS.md          |
| `/bio:run`     | Execute pipeline from ANALYSIS.md                           |
| `/bio:qc`      | Run automated + visual QC on current segmentation           |
| `/bio:measure` | Extract measurements from label masks                       |
| `/bio:status`  | Show current analysis state                                 |

## Reference Files

- `references/environment.md` — env checking, version gotchas, tool reference
- `references/state-templates.md` — ANALYSIS.md and STATE.md formats
- `references/segmentation.md` — decision tree, approaches, post-processing
- `references/measurements.md` — what to measure, biological meaning, pitfalls
- `references/preprocessing.md` — illumination, background, noise, normalization
- `references/quality-control.md` — automated QC checks + manual checklist
- `references/cookbook-io.md` — reading images, metadata, directory scanning
- `references/cookbook-segmentation.md` — segmentation code patterns and tool usage
- `references/cookbook-visualization.md` — matplotlib (default) and napari display patterns
- `references/cookbook-measurements.md` — measurement extraction and export code
- `references/cookbook-pipeline.md` — complete end-to-end pipeline examples
