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
2. **Close the feedback loop.** Every step that produces output: show it visually (napari preferred, matplotlib always available), assess it yourself, ask user to evaluate before proceeding. Never say "check the output."
3. **Ask focused questions, then execute.** Up to 2-3 questions to understand the biological question and data. Infer everything else from context. Never ask technical implementation questions.
4. **Show results in the best available viewer.** napari preferred when available (visual feedback loop is core). matplotlib is a first-class alternative with equal code quality — used whenever napari is unavailable. Offer napari setup once if available but not connected.

## User Interaction

- Gauge user level from context: terminology, file paths, how they describe their problem
- "Segment nuclei using StarDist" → minimal questions, they know what they want
- "I have microscopy images" → more guidance needed
- Question budget: up to 3 focused questions, then execute
- Priority: (1) biological question, (2) what's in the image, (3) how results will be used
- Never ask: technical implementation, environment, or "would you like me to..." questions
- Adapt: biology terms → run directly, explain in scientific terms. Code terms → show code
- Report results in scientific language matching the user's domain

## Persistent State

STATE.md and ANALYSIS.md live in `.bioimage-analysis/` in the project directory. Check for STATE.md on every activation. See `references/state-templates.md` for formats.

- STATE.md: environment info, viewer status, analysis history. Update after every significant action
- ANALYSIS.md: biological question, data description, pipeline steps, tool choices, parameters
- Each pipeline step uses `step_status: in_progress | completed`
- Validation: if STATE.md is malformed or unreadable, treat as missing and recreate

## On Activation

1. Check for `.bioimage-analysis/STATE.md` — if exists, read it (env, viewer, analysis progress)
2. If no STATE.md: spawn env scanner agent in background (Agent tool, `run_in_background: true`), writes to STATE.md. Main conversation is notified on completion
3. Start talking immediately — don't block on scanning
4. If STATE.md shows napari available but not connected → offer to connect
5. If env info needed before scanner finishes → quick inline check

## Workflow

### 1. Assess
Read the image, scan directory for context (custom models, configs, other images). Find tools — use STATE.md cache if available, else spawn background scanner. Find viewer and write ANALYSIS.md with the plan. Reference `references/cookbook-io.md` for reading patterns.

### 2. Connect Viewer
Check STATE.md for napari status. Install napari-mcp if needed, launch, verify connection. Update STATE.md. Reference `references/cookbook-visualization.md` for launch patterns. Never write standalone viewer scripts. If setup fails, fall back to matplotlib.

### 3. Execute
Read ANALYSIS.md, run pipeline step by step. After every visual step: check viewer_connected, push to napari or show matplotlib. Present results as preliminary — "Here's a first pass, does this look right?" Update STATE.md after each step. Reference `references/cookbook-segmentation.md`.

### 4. Iterate
Adjust and re-run based on feedback. If not working after 2-3 tries: try a different tool, search forum.image.sc, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning. Don't over-tune — if parameters need drastic per-image adjustment, the approach is wrong.

### 5. Measure & Export
Save organized outputs (labels, QC overlays, CSV tables, analysis log). Reference `references/cookbook-measurements.md` for extraction patterns. Connect back to biology — answering the biological question is the endpoint, not raw measurements. Reference `references/quality-control.md` for validation. Check versions before recommending features — see `references/environment.md`.

## Slash Commands

| Command        | Behavior                                                    |
|----------------|-------------------------------------------------------------|
| `/bio`         | Start bioimage analysis — assess image and propose pipeline |
| `/bio:plan`    | Assess image, scan environment, write ANALYSIS.md           |
| `/bio:run`     | Execute pipeline from ANALYSIS.md                           |
| `/bio:qc`      | Run QC checklist on current segmentation results            |
| `/bio:measure` | Extract measurements from label masks                       |
| `/bio:status`  | Show current STATE.md — env, viewer, progress               |

## Reference Files

- `references/environment.md` — env scanning, version checks, napari setup, known gotchas
- `references/state-templates.md` — STATE.md and ANALYSIS.md formats
- `references/segmentation.md` — approaches: threshold, Cellpose, StarDist, nnUNetv2
- `references/measurements.md` — what to measure, biological meaning, pitfalls
- `references/preprocessing.md` — illumination, background, noise, normalization
- `references/quality-control.md` — validation checklist after segmentation
- `references/cookbook-io.md` — reading images, metadata, directory scanning
- `references/cookbook-segmentation.md` — segmentation code patterns and tool usage
- `references/cookbook-visualization.md` — napari and matplotlib display patterns
- `references/cookbook-measurements.md` — measurement extraction and export code
