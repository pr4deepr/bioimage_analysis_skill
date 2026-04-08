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
  - name: bio:qc
    description: Run QC checklist on segmentation results
---

# Bioimage Analysis

Five rules:
1. **Look first, then propose.** Assess the image and context before running anything.
2. **Find environments, never blind-install.** Before installing any package, check existing conda/mamba envs for it (glob `site-packages/`, not `conda list`). Only install if no env has it — and into the right env. See `references/environment.md` Steps 1-3.
3. **Close the feedback loop.** Every step that produces output: show it visually (napari preferred, matplotlib always available), assess it yourself, ask user to evaluate before proceeding. Never say "check the output."
4. **Ask focused questions, then execute.** Up to 2-3 questions to understand the biological question and data. Infer everything else from context. Never ask technical implementation questions.
5. **Show results in the best available viewer.** napari preferred when available (visual feedback loop is core). matplotlib is a first-class alternative with equal code quality — used whenever napari is unavailable. Offer napari setup once if available but not connected.

## User Interaction

- Gauge user level from context: terminology, file paths, how they describe their problem
- "Segment nuclei using StarDist" → minimal questions, they know what they want
- "I have microscopy images" → more guidance needed
- Question budget: up to 3 focused questions, then propose the plan
- Priority: (1) biological question, (2) what's in the image, (3) how results will be used
- Never ask: technical implementation, environment, or "would you like me to..." questions
- Adapt: biology terms → run directly, explain in scientific terms. Code terms → show code
- Report results in scientific language matching the user's domain

## Workflow

### 1. Assess
Read the image, scan directory for context (custom models, configs, other images). Check the active Python environment inline — run `which python` or `where python`, then check installed packages with a quick `python -c "import ..."`. For multi-channel images, identify which channel to segment (e.g., DAPI/Hoechst for nuclei, membrane marker for cells) — this is a common source of errors. Call `pick_segmentation_tool()` then `validate_model_for_version()` from `bioimage_utils.py` to select the approach. For large files, call `estimate_memory()` — if data doesn't fit in RAM, follow the large data guidance in `segmentation.md` and use the tiled/chunked pipelines in `cookbook-pipeline.md`.

**Environment rule — look before you install:**
Never `pip install` or `conda install` a package without first checking existing environments. Follow `references/environment.md` Steps 1-3: list conda envs, pick candidates by name, then glob `site-packages/` for the package folder. This filesystem check takes milliseconds. Only install if no existing env has the package — and install into the correct env, not whatever happens to be active. This applies to every tool (Cellpose, StarDist, napari-mcp, etc.).

### 2. Connect Viewer
Check STATE.md for napari status. napari-mcp must be **registered as an MCP server in Claude Code** (not just launched as a subprocess). Use `claude mcp list` to check, `claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp` to register. Verify with `ToolSearch` for napari tools. If MCP unavailable, launch napari directly with data pre-loaded as fallback. Reference `references/cookbook-visualization.md` for the full setup flow.

### 3. Execute
Run pipeline step by step. Use `clean_labels()` from `bioimage_utils.py` for post-processing. After every visual step: push to napari or show matplotlib. Present results as preliminary — "Here's a first pass, does this look right?" Reference `references/segmentation.md` for version-specific code and `references/cookbook-pipeline.md` for complete pipeline examples.

### 4. Iterate
Adjust and re-run based on feedback. If not working after 2-3 tries: try a different tool, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning. Don't over-tune — if parameters need drastic per-image adjustment, the approach is wrong.

**When stuck, search [forum.image.sc](https://forum.image.sc).** This is the primary community forum for bioimage analysis — actively monitored by developers of Cellpose, StarDist, napari, QuPath, CellProfiler, and other tools. Search for similar modalities, error messages, or workflows. Suggest users post there for expert advice on genuinely difficult problems.

### 5. Measure & Export
Call `detect_measurement_pitfalls()` from `bioimage_utils.py` before extracting measurements — it checks for edge objects, saturation, missing calibration, and other issues. Save organized outputs (labels, QC overlays, CSV tables). Reference `references/measurements.md` for extraction patterns and pitfalls. Connect back to biology — answering the biological question is the endpoint, not raw measurements. Reference `references/quality-control.md` for validation.

## Slash Commands

| Command    | Behavior                                                    |
|------------|-------------------------------------------------------------|
| `/bio`     | Start bioimage analysis — assess image, propose pipeline, execute after approval |
| `/bio:qc`  | Run QC checklist on current segmentation results            |

## Reference Files

```
SKILL.md (entrypoint — defines workflow, references all files below)
├── bioimage_utils.py — callable logic (hub, used by most files)
│   pick_segmentation_tool, validate_model_for_version, clean_labels,
│   detect_measurement_pitfalls, extract_measurements, estimate_memory,
│   ResultsManager
├── segmentation.md — approaches, version-specific code, large data
│   → uses bioimage_utils.py, references cookbook-pipeline.md
├── cookbook-pipeline.md — 5 end-to-end pipelines
│   → uses bioimage_utils.py, references segmentation.md
├── measurements.md — what to measure, pitfalls
│   → uses bioimage_utils.py
├── environment.md — version gotchas, GPU, napari-mcp
│   → uses bioimage_utils.py
├── preprocessing.md — when and how to preprocess (self-contained)
├── quality-control.md — validation checklist (self-contained)
└── visualization.md — napari-mcp and matplotlib (self-contained)
```
