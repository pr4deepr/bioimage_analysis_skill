# Plan: Incorporate Calcium Imaging Lessons

## Context

A real calcium imaging dataset was analyzed using this skill. The workflow revealed several gaps: no calcium imaging pipeline, no F/F0 guidance, segmentation failures on low-contrast sparse data, and missing decision logic for functional imaging. This plan addresses each gap with targeted changes.

## What the real analysis showed

1. **Otsu thresholding failed** on sparse, low-contrast calcium imaging data (only 2 cells detected). Percentile-based thresholds worked much better.
2. **Std projection scaled with brightness**, missing dim but active cells (enteric glial cells). A **normalized activity map** (pixel-wise `std(F/F0) * (max(F/F0) - 1)`) was brightness-independent and captured 87 ROIs vs 33.
3. **Drug addition detection** used frame-to-frame mean intensity jumps to find pipetting artifacts.
4. **Response classification** used baseline_mean + 5*std AND absolute 1.1 threshold — but this was possibly too strict, missing weak responders (F/F0 1.05-1.10).
5. **Over-segmentation** (87 ROIs) partially offset by strict response threshold (9 responders) — fragile tradeoff.

## Changes

### 1. New file: `references/calcium-imaging.md` (~150 lines)

Dedicated reference for functional calcium imaging analysis. Covers:

- **When this applies**: time-lapse calcium imaging (Fluo-4, GCaMP, Fura-2, etc.)
- **Segmentation strategy decision tree for calcium data**:
  - **If cells are visible in a single frame** (bright labeling, high SNR): use Cellpose/StarDist on a max projection or mean projection — standard segmentation works fine
  - **If cells are only visible through their activity** (dim, sparse, low baseline): use activity-based segmentation with normalized activity map
  - **If there is frame-to-frame motion**: register first (phase cross-correlation for translation, or tools like suite2p/CaImAn for non-rigid), THEN segment
- **Activity-based segmentation** (for when standard segmentation fails):
  - Why Otsu fails on sparse functional data (bimodal assumption violated)
  - Why raw std projection misses dim cells (brightness bias)
  - The normalized activity map approach: `std(F/F0) * (max(F/F0) - 1)`
  - Percentile threshold (e.g., 65th) + watershed + size filtering
- **Stimulus/drug addition detection**: frame-to-frame mean intensity difference approach, concrete code snippet, warning about multiple artifact candidates requiring user confirmation
- **F/F0 and dF/F0 calculation**: definitions, when to use each, baseline period selection
- **Photobleaching correction**: exponential fit to pre-stimulus baseline, or running median of background region
- **Trace smoothing**: Savitzky-Golay filter for peak detection (window, polyorder guidance)
- **Response classification**: threshold strategies (baseline + N*std, absolute minimum), return raw z-scores so user can adjust, caution about being too strict
- **Ratiometric note**: one-liner for Fura-2 — compute 340/380 ratio image first, then apply this workflow to the ratio timeseries
- **Common pitfalls**: motion artifacts, pipetting artifacts creating multiple candidates, over-segmentation from activity maps
- **Complete pipeline code** (~60 lines) embedded in this file (not in cookbook-pipeline.md, since this is a qualitatively different workflow — functional imaging with trace extraction, not the segmentation-measurement pattern the cookbook covers)

### 2. Update `references/segmentation.md` (~20 lines)

Two additions:

a) **General Otsu limitation** (in Classical Approaches section): Otsu assumes a bimodal intensity distribution. It fails when foreground is a small fraction of the image (sparse colonies, rare cell types, calcium imaging data). Use percentile-based thresholds or adaptive methods instead.

b) **Calcium/functional imaging note** (in Decision Tree section): For time-lapse calcium imaging, segmentation approach depends on cell visibility. If cells are visible in individual frames, use Cellpose/StarDist on a max/mean projection. If cells are only visible through activity, use activity-based segmentation. Reference `calcium-imaging.md`.

### 3. Update `references/bioimage_utils.py` — new functions (~90 lines)

Add two functions:

- `compute_activity_map(stack, baseline_frames)`: compute normalized activity map from a time-lapse stack. Returns the brightness-independent activity image. **Includes RAM check** via `estimate_memory()` — warns if stack is too large and suggests frame-by-frame computation. Accepts numpy array (caller loads the stack; for very large data, document that the caller should use dask or load in chunks).

- `classify_responses(traces, baseline_frames, n_std=3, min_fold_change=1.05)`: classify ROIs as responding/non-responding. Returns dict with: responding mask, per-ROI peak F/F0, per-ROI z-scores (so user can adjust threshold after the fact), threshold used, and baseline stats. **Defaults are deliberately permissive** (`n_std=3, min_fold_change=1.05`) — better to include borderline responders and let the user tighten than to silently exclude real responses.

### 4. Update `pick_segmentation_tool()` in `bioimage_utils.py` (~15 lines)

Add `"calcium_imaging"` as a valid modality. When selected:
- Primary recommendation: Cellpose/StarDist on max/mean time projection (works when cells are visible in single frames)
- Notes: "If cells are dim and only visible through activity, use `compute_activity_map()` + percentile threshold instead. See `references/calcium-imaging.md`."
- Additional note: "If there is frame-to-frame motion, register the stack first (skimage phase_cross_correlation for rigid, or suite2p/CaImAn for non-rigid)."

### 5. Update `SKILL.md` — trigger keywords + file tree (~5 lines)

- Add calcium imaging keywords to the description trigger list: "calcium imaging", "calcium transient", "F/F0", "dF/F", "GCaMP", "functional imaging", "calcium indicator"
- Add `calcium-imaging.md` to the reference file tree
- Remove "Fura-2" from triggers (ratiometric is only briefly mentioned, not fully supported — don't trigger on it)

### 6. Update `references/preprocessing.md` — two additions (~8 lines)

a) Photobleaching row in "When to Apply What" table:
- Problem: Intensity decay over time in timelapse | Solution: Photobleaching correction | Tool: Exponential fit or frame-wise background normalization

b) Registration row:
- Problem: Frame-to-frame motion in timelapse | Solution: Image registration | Tool: `skimage.registration.phase_cross_correlation` for rigid translation; suite2p or CaImAn for non-rigid

### 7. Update `references/measurements.md` — temporal measurements (~12 lines)

Add a "Temporal / Functional" section:
- F/F0 peak amplitude, time to peak, response duration, event frequency
- Note: these are extracted from per-ROI traces over time, not from single-frame regionprops
- Reference `classify_responses()` from `bioimage_utils.py`

## Files modified (summary)

| File | Change | Lines added |
|---|---|---|
| `references/calcium-imaging.md` | **NEW** (reference + pipeline) | ~150 |
| `references/segmentation.md` | Otsu limitation + calcium note | ~20 |
| `references/bioimage_utils.py` | `compute_activity_map`, `classify_responses`, update `pick_segmentation_tool` | ~105 |
| `SKILL.md` | Trigger keywords + file tree | ~5 |
| `references/preprocessing.md` | Photobleaching + registration rows | ~8 |
| `references/measurements.md` | Temporal measurements section | ~12 |
| **Total** | | **~300** |

## What we're NOT doing

- Not adding full ratiometric (Fura-2 dual-wavelength) pipeline — one-line note in calcium-imaging.md instead
- Not adding spike detection algorithms (MLspike, CASCADE) — ML tools beyond this skill's scope
- Not implementing motion correction — reference existing tools (suite2p, CaImAn, skimage phase_cross_correlation) and tell user to register before analysis
- Not adding the pipeline to cookbook-pipeline.md — calcium imaging is a different workflow pattern (trace-based, not segmentation-measurement), so it belongs in its own reference file

## Order of implementation

1. `bioimage_utils.py` — add functions first (other files reference them)
2. `calcium-imaging.md` — new reference file with embedded pipeline
3. `segmentation.md` — Otsu limitation + calcium note
4. `SKILL.md` — triggers and file tree
5. `preprocessing.md` — photobleaching + registration rows
6. `measurements.md` — temporal section
