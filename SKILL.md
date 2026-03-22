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
3. **Close the feedback loop.** Every step that produces output: save to `analysis/` folder, auto-open it (the user's default image viewer opens automatically), run automated QC (`references/quality-control.md`), then ask the user to evaluate. Never say "check the output."
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

## Visualization & Results

**Save + auto-open.** Every visual output is saved and auto-opened in the user's default image viewer. This gives interactive feedback (zoom, pan, inspect) without any MCP setup.

**Organized by run.** Use `ResultsManager` from `references/cookbook-results.md` to create structured output: `analysis/run_001_stardist_nuclei/01_raw/`, `02_segmentation/`, etc. Each run gets an HTML manifest with thumbnails, parameters, QC status — auto-opens in the browser. Multiple iterations create separate runs so the user can compare.

**napari-mcp is opt-in.** Only set up if the user explicitly asks or needs interactive annotation.

See `references/cookbook-visualization.md` for display patterns and `references/cookbook-results.md` for the results manager.

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
Initialize `ResultsManager("analysis", "short_description")` to create a run folder. Run the pipeline step by step, using `results.save_figure()` / `results.save_image()` / `results.save_csv()` to route outputs to the right step folders. After every visual step: the image auto-opens, run automated QC checks, present results as preliminary — "Here's a first pass, does this look right?" Reference `references/cookbook-pipeline.md` for complete patterns.

### 4. Iterate
Adjust and re-run based on feedback — each iteration creates a **new run folder** so the user can compare. If not working after 2-3 tries: try a different tool, search forum.image.sc, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning.

### 5. Measure & Export
Save outputs via `ResultsManager`. Call `results.write_manifest()` at the end — it generates an HTML summary with thumbnails, parameters, QC status and auto-opens in the browser. This is the user's entry point for reviewing results. Connect back to biology — answering the biological question is the endpoint, not raw measurements.

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
- `references/cookbook-visualization.md` — matplotlib display patterns, auto-open, napari opt-in
- `references/cookbook-measurements.md` — measurement extraction and export code
- `references/cookbook-results.md` — ResultsManager: run folders, step folders, HTML manifest
- `references/cookbook-pipeline.md` — complete end-to-end pipeline examples using ResultsManager
