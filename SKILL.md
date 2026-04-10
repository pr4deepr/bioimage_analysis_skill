---
name: bioimage-analysis
description: >
  Use when users mention: cell segmentation, nucleus detection, object
  measurement, scikit-image, Cellpose, StarDist, napari, FIJI, image
  quantification, fluorescence analysis, calcium imaging, voltage imaging,
  functional imaging, F/F0, dF/F, GCaMP, drug response, microscopy images,
  or any task involving identifying and measuring objects in biological images.
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

## When to Route Elsewhere

| User needs | Better tool |
|---|---|
| High-throughput phenotypic screens (100s of conditions) | CellProfiler |
| Whole-slide pathology with annotations | QuPath |
| 3D stitching, registration, multi-view fusion | BigStitcher / FIJI |
| Calcium imaging with motion correction + spike inference | suite2p or CaImAn |
| Custom DL model training from scratch | nnUNetv2 CLI directly |

## User Interaction

- Gauge user level from context. "Segment nuclei using StarDist" → minimal questions. "I have microscopy images" → more guidance needed.
- Question budget: up to 3 focused questions about (1) biological question, (2) what's in the image, (3) how results will be used. Never ask technical implementation questions.
- Report results in scientific language matching the user's domain.

## How to Use `bioimage_utils.py`

The functions in `bioimage_utils.py` are **reference code in this skill repo**,
not an installed package. Read the function, then inline its logic in your
script. `from bioimage_utils import ...` in the cookbooks is shorthand — in
practice, adapt the logic directly.

## Workflow

### 1. Assess
Read the image, scan directory for context (custom models, configs, other images). Check the active Python environment inline — run `which python` or `where python`, then check installed packages with a quick `python -c "import ..."`. For multi-channel images, identify which channel to segment (e.g., DAPI/Hoechst for nuclei, membrane marker for cells) — this is a common source of errors. Call `pick_segmentation_tool()` then `validate_model_for_version()` from `bioimage_utils.py` to select the approach. For large files, call `estimate_memory()` — if data doesn't fit in RAM, follow the large data guidance in `segmentation.md` and use the tiled/chunked pipelines in `cookbook-pipeline.md`.

**Environment rule — look before you install:**
Never `pip install` or `conda install` without first searching ALL existing environments. Follow `references/environment.md` Steps 1-3: (1) try `conda env list`, (2) if conda not on PATH, glob common locations (`~/.conda/envs/`, `~/miniconda3/envs/`, `~/miniforge3/envs/`, `~/mambaforge/envs/`), (3) glob `site-packages/` in each candidate for the package. `.conda/envs/` is easy to miss — always check it. Only install if no env has the package.

### 2. Connect Viewer
Check STATE.md for napari status. napari-mcp must be **registered as an MCP server in Claude Code** (not just launched as a subprocess). Use `claude mcp list` to check, `claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp` to register. Verify with `ToolSearch` for napari tools. If MCP unavailable, launch napari directly with data pre-loaded as fallback. Reference `references/visualization.md` for the full setup flow.

### 3. Execute
Run pipeline step by step. Use `clean_labels()` from `bioimage_utils.py` for post-processing. After every visual step: push to napari or show matplotlib. Present results as preliminary — "Here's a first pass, does this look right?" Reference `references/segmentation.md` for version-specific code and `references/cookbook-pipeline.md` for complete pipeline examples.

### 4. Iterate
Adjust and re-run based on feedback. If not working after 2-3 tries: try a different tool, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning. Don't over-tune — if parameters need drastic per-image adjustment, the approach is wrong.

**When stuck, search [forum.image.sc](https://forum.image.sc).** This is the primary community forum for bioimage analysis — actively monitored by developers of Cellpose, StarDist, napari, QuPath, CellProfiler, and other tools. Search for similar modalities, error messages, or workflows. Suggest users post there for expert advice on genuinely difficult problems.

### 5. Measure & Export
Check for measurement pitfalls (edge objects, saturation, missing calibration — see `detect_measurement_pitfalls()` in `bioimage_utils.py`). Reference `references/measurements.md` for extraction patterns. Connect back to biology — answering the biological question is the endpoint, not raw measurements. Reference `references/quality-control.md` for validation.

**Output organization**: Save all outputs to a single `analysis/` subfolder
with step-prefixed filenames: `01_raw_preview.png`, `02_labels.tif`,
`02_overlay.png`, `03_qc_histogram.png`, `04_measurements.csv`. Tell the
user what was saved and where.

## Slash Commands

| Command    | Behavior                                                    |
|------------|-------------------------------------------------------------|
| `/bio`     | Start bioimage analysis — assess image, propose pipeline, execute after approval |
| `/bio:qc`  | Run QC checklist on current segmentation results            |

## Reference Files

```
SKILL.md (this file — workflow, rules, references)
├── bioimage_utils.py — decision logic + utilities (hub)
├── segmentation.md — tool selection, version-specific code, large data
├── timeseries-functional.md — functional timelapse (calcium, voltage, pH)
├── cookbook-pipeline.md — 5 end-to-end pipelines
├── measurements.md — what to measure, pitfalls, temporal
├── environment.md — env search, version gotchas, GPU
├── preprocessing.md — when and how to preprocess
├── quality-control.md — validation checklist
└── visualization.md — napari-mcp and matplotlib
```
