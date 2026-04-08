# Plan: Add Time-Series Functional Imaging Support

## Context

A real calcium imaging dataset was analyzed using this skill. The workflow revealed several gaps: no functional imaging pipeline, no F/F0 guidance, segmentation failures on low-contrast sparse data, and missing decision logic for time-series functional data. The lessons learned apply not just to calcium imaging but to any functional fluorescence timelapse — voltage imaging, pH imaging, FRET reporters, ROS indicators, and generic drug-response experiments.

## What the real analysis showed

1. **Otsu thresholding failed** on sparse, low-contrast calcium imaging data (only 2 cells detected). Percentile-based thresholds worked much better.
2. **Std projection scaled with brightness**, missing dim but active cells (enteric glial cells). A **normalized activity map** (pixel-wise `std(F/F0) * (max(F/F0) - 1)`) was brightness-independent and captured 87 ROIs vs 33.
3. **Drug addition detection** used frame-to-frame mean intensity jumps to find pipetting artifacts.
4. **Response classification** used baseline_mean + 5*std AND absolute 1.1 threshold — but this was possibly too strict, missing weak responders (F/F0 1.05-1.10).
5. **Over-segmentation** (87 ROIs) partially offset by strict response threshold (9 responders) — fragile tradeoff.

## Changes

### 1. New file: `references/timeseries-functional.md` (~170 lines)

Generalized reference for functional time-series imaging. Calcium imaging is the primary worked example (validated by real use), with explicit notes where other indicator types differ.

- **When this applies**: any timelapse where the biological signal is a *change in fluorescence over time* — calcium (GCaMP, Fluo-4), voltage (ArcLight, ASAP, Voltron), pH (pHluorin, BCECF), ROS, FRET-based reporters, or any drug-response experiment with a fluorescent readout
- **Parameter differences by indicator type** (mini-table):

  | Indicator type | Typical dF/F | Frame rate | Smoothing window | min_fold_change |
  |---|---|---|---|---|
  | Calcium (GCaMP6s) | 50–500% | 1–30 Hz | 11–31 frames | 1.05–1.10 |
  | Calcium (chemical, Fluo-4) | 20–200% | 1–10 Hz | 11–31 frames | 1.05–1.10 |
  | Voltage (ASAP, Voltron) | 1–5% | 100–1000 Hz | 3–7 frames | 1.01–1.02 |
  | pH (pHluorin) | 10–50% | 0.1–1 Hz | 5–15 frames | 1.03–1.05 |
  | FRET (CFP/YFP) | 5–30% | 0.1–5 Hz | 7–21 frames | 1.02–1.05 |

- **Segmentation strategy decision tree**:
  - **If cells are visible in a single frame** (bright labeling, high SNR): use Cellpose/StarDist on a max or mean time projection — standard segmentation works
  - **If cells are only visible through their activity** (dim, sparse, low baseline): use activity-based segmentation with normalized activity map
  - **If there is frame-to-frame motion**: register first (phase cross-correlation for translation, or suite2p/CaImAn for non-rigid), THEN segment
- **Activity-based segmentation** (for when standard segmentation fails):
  - Why Otsu fails on sparse functional data (bimodal assumption violated)
  - Why raw std projection misses dim cells (brightness bias)
  - The normalized activity map: `std(F/F0) * (max(F/F0) - 1)`
  - Percentile threshold (e.g., 65th) + watershed + size filtering
- **Stimulus/drug detection** (optional step — not all experiments have a stimulus):
  - Frame-to-frame mean intensity difference approach, concrete code snippet
  - Warning about multiple artifact candidates requiring user confirmation
  - For spontaneous activity recordings, skip this step and analyze all frames
- **F/F0 and dF/F0 calculation**: definitions, when to use each, baseline period selection
- **Photobleaching correction**: exponential fit to pre-stimulus baseline, or running median of background region
- **Trace smoothing**: Savitzky-Golay filter for peak detection — window and polyorder depend on indicator kinetics and frame rate (reference the parameter table)
- **Response classification**: threshold strategies (baseline + N*std, absolute minimum), return raw z-scores so user can adjust, note that defaults are calibrated for calcium — voltage imaging needs much tighter thresholds
- **Ratiometric note**: for dual-wavelength indicators (Fura-2 340/380, FRET donor/acceptor), compute the ratio image per frame first, then apply this workflow to the ratio timeseries
- **Common pitfalls**: motion artifacts, pipetting artifacts creating multiple candidates, over-segmentation from activity maps, applying calcium-appropriate thresholds to voltage data (signal is 100x smaller)
- **Complete pipeline code** (~60 lines) embedded in this file, using calcium imaging as the example. Not in cookbook-pipeline.md since this is a different workflow pattern (trace-based, not segmentation-measurement)

### 2. Update `references/segmentation.md` (~20 lines)

Two additions:

a) **General Otsu limitation** (in Classical Approaches section): Otsu assumes a bimodal intensity distribution. It fails when foreground is a small fraction of the image (sparse colonies, rare cell types, functional imaging data). Use percentile-based thresholds or adaptive methods instead.

b) **Functional timelapse note** (in Decision Tree section): For time-lapse functional imaging (calcium, voltage, pH, etc.), segmentation approach depends on cell visibility. If cells are visible in individual frames, use Cellpose/StarDist on a max/mean time projection. If cells are only visible through activity, use activity-based segmentation. If there is motion, register first. Reference `timeseries-functional.md`.

### 3. Update `references/bioimage_utils.py` — new functions (~100 lines)

Add two functions:

- `compute_activity_map(stack, baseline_frames)`: compute normalized activity map from a time-lapse stack. Returns brightness-independent activity image. **Includes RAM check** via `estimate_memory()` — warns if stack is too large and suggests frame-by-frame computation. Accepts numpy array (caller handles loading). Docstring notes this works for any functional indicator, not just calcium.

- `classify_responses(traces, baseline_frames, n_std=3, min_fold_change=1.05)`: classify ROIs as responding/non-responding. Returns dict with: responding mask, per-ROI peak F/F0, per-ROI z-scores (so user can adjust threshold after the fact), threshold used, and baseline stats. **Defaults are deliberately permissive** (`n_std=3, min_fold_change=1.05`) — calibrated for calcium imaging. Docstring notes: for voltage imaging use `min_fold_change=1.01`; for pH/FRET use `min_fold_change=1.02`.

### 4. Update `pick_segmentation_tool()` in `bioimage_utils.py` (~15 lines)

Add `"functional_timelapse"` as a valid modality (plus `"calcium_imaging"` as an alias that maps to it). When selected:
- Primary recommendation: Cellpose/StarDist on max/mean time projection (works when cells are visible in single frames)
- Notes: "If cells are dim and only visible through activity, use `compute_activity_map()` + percentile threshold instead. See `references/timeseries-functional.md`."
- Additional note: "If there is frame-to-frame motion, register the stack first (skimage phase_cross_correlation for rigid, or suite2p/CaImAn for non-rigid)."

### 5. Update `SKILL.md` — trigger keywords + file tree (~5 lines)

- Add broad functional imaging keywords to the description trigger list: "calcium imaging", "voltage imaging", "functional imaging", "timelapse response", "F/F0", "dF/F", "GCaMP", "calcium indicator", "drug response", "stimulus response"
- Add `timeseries-functional.md` to the reference file tree

### 6. Update `references/preprocessing.md` — two additions (~8 lines)

a) Photobleaching row in "When to Apply What" table:
- Problem: Intensity decay over time in timelapse | Solution: Photobleaching correction | Tool: Exponential fit or frame-wise background normalization

b) Registration row:
- Problem: Frame-to-frame motion in timelapse | Solution: Image registration | Tool: `skimage.registration.phase_cross_correlation` for rigid translation; suite2p or CaImAn for non-rigid

### 7. Update `references/measurements.md` — temporal measurements (~12 lines)

Add a "Temporal / Functional" section:
- F/F0 peak amplitude, time to peak, response duration, event frequency
- Note: these are extracted from per-ROI traces over time, not from single-frame regionprops
- Parameter interpretation depends on indicator type — reference the parameter table in `timeseries-functional.md`
- Reference `classify_responses()` from `bioimage_utils.py`

## Files modified (summary)

| File | Change | Lines added |
|---|---|---|
| `references/timeseries-functional.md` | **NEW** (reference + pipeline) | ~170 |
| `references/segmentation.md` | Otsu limitation + functional timelapse note | ~20 |
| `references/bioimage_utils.py` | `compute_activity_map`, `classify_responses`, update `pick_segmentation_tool` | ~115 |
| `SKILL.md` | Trigger keywords + file tree | ~5 |
| `references/preprocessing.md` | Photobleaching + registration rows | ~8 |
| `references/measurements.md` | Temporal measurements section | ~12 |
| **Total** | | **~330** |

## What we're NOT doing

- Not adding full ratiometric pipeline — one-line note to compute ratio first, then use the standard workflow
- Not adding spike detection algorithms (MLspike, CASCADE) — ML tools beyond this skill's scope
- Not implementing motion correction — reference existing tools (suite2p, CaImAn, skimage phase_cross_correlation) and tell user to register before analysis
- Not adding the pipeline to cookbook-pipeline.md — functional imaging is a different workflow pattern (trace-based), so it belongs in its own reference file
- Not claiming to have validated this workflow beyond calcium imaging — calcium is the worked example, other indicator types get parameter guidance and caveats

## Order of implementation

1. `bioimage_utils.py` — add functions first (other files reference them)
2. `timeseries-functional.md` — new reference file with embedded pipeline
3. `segmentation.md` — Otsu limitation + functional timelapse note
4. `SKILL.md` — triggers and file tree
5. `preprocessing.md` — photobleaching + registration rows
6. `measurements.md` — temporal section
