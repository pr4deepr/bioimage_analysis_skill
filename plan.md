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

### 1. New file: `references/calcium-imaging.md` (~120 lines)

Dedicated reference for functional calcium imaging analysis. Covers:

- **When this applies**: time-lapse calcium imaging (Fluo-4, GCaMP, Fura-2, etc.)
- **Activity-based segmentation** (the key insight): why standard segmentation fails on calcium data, and how to use normalized activity maps instead
  - Why Otsu fails on sparse functional data (bimodal assumption violated)
  - Why raw std projection misses dim cells (brightness bias)
  - The normalized activity map approach: `std(F/F0) * (max(F/F0) - 1)`
  - Percentile threshold (e.g., 65th) + watershed + size filtering
- **Baseline detection**: detecting drug/stimulus addition from frame-to-frame intensity artifacts
- **F/F0 and dF/F0 calculation**: definitions, when to use each, baseline period selection
- **Photobleaching correction**: exponential fit to pre-stimulus baseline, or running median of background region
- **Response classification**: threshold strategies (baseline + N*std, absolute minimum), caution about being too strict
- **Common pitfalls specific to calcium imaging**: motion artifacts, pipetting artifacts creating multiple candidates, over-segmentation from activity maps

### 2. New pipeline in `cookbook-pipeline.md`: Pipeline 6 — Calcium Imaging (~90 lines)

Complete runnable pipeline demonstrating:
- Read timelapse TIF stack
- Compute normalized activity map for segmentation
- Percentile threshold + watershed ROI detection
- F/F0 trace extraction with configurable baseline
- Response classification
- Outputs: overlay, traces, heatmap, CSV

### 3. Update `references/segmentation.md` — add calcium imaging pitfall (~15 lines)

Add a section after "Classical Approaches" or in the decision tree:
- **Calcium/functional imaging data**: standard thresholding on mean/max projections fails because signal is transient. Use activity-based segmentation instead (reference calcium-imaging.md).
- Otsu pitfall: explicitly note that Otsu assumes bimodal intensity distribution — fails on sparse data where background dominates.

### 4. Update `references/bioimage_utils.py` — new functions (~80 lines)

Add two functions:
- `compute_activity_map(stack, baseline_frames)`: compute normalized activity map from a time-lapse stack. Returns the brightness-independent activity image.
- `classify_responses(traces, baseline_frames, n_std=5, min_fold_change=1.1)`: classify ROIs as responding/non-responding. Returns dict with responding indices, peak amplitudes, and threshold used.

### 5. Update `SKILL.md` — trigger on calcium imaging terms (~5 lines)

- Add calcium imaging keywords to the description trigger list: "calcium imaging", "calcium transient", "F/F0", "dF/F", "Fluo-4", "GCaMP", "Fura-2", "functional imaging", "calcium indicator"
- Add `calcium-imaging.md` to the reference file tree

### 6. Update `references/preprocessing.md` — photobleaching correction (~5 lines)

Add one row to the "When to Apply What" table:
- Problem: Intensity decay over time in timelapse | Solution: Photobleaching correction | Tool: Exponential fit or frame-wise background normalization

### 7. Update `references/measurements.md` — temporal measurements (~10 lines)

Add a "Temporal / Functional" section:
- F/F0 peak amplitude, time to peak, response duration, event frequency
- Note: these are extracted from traces, not from single-frame regionprops

## Files modified (summary)

| File | Change | Lines added |
|---|---|---|
| `references/calcium-imaging.md` | **NEW** | ~120 |
| `references/cookbook-pipeline.md` | Add Pipeline 6 | ~90 |
| `references/segmentation.md` | Calcium pitfall note | ~15 |
| `references/bioimage_utils.py` | `compute_activity_map`, `classify_responses` | ~80 |
| `SKILL.md` | Trigger keywords + file tree | ~5 |
| `references/preprocessing.md` | Photobleaching row | ~5 |
| `references/measurements.md` | Temporal measurements section | ~10 |
| **Total** | | **~325** |

## What we're NOT doing

- Not adding ratiometric (Fura-2 dual-wavelength) support — too specialized, add when needed
- Not adding spike detection algorithms (MLspike, CASCADE) — those are ML tools beyond this skill's scope
- Not adding motion correction — that's a preprocessing step that needs specialized tools (suite2p, CaImAn)
- Not duplicating the full calcium imaging analysis in the cookbook — just the core pattern that the real analysis converged on

## Order of implementation

1. `bioimage_utils.py` — add functions first (other files reference them)
2. `calcium-imaging.md` — new reference file
3. `cookbook-pipeline.md` — Pipeline 6
4. `segmentation.md` — pitfall note
5. `SKILL.md` — triggers and file tree
6. `preprocessing.md` — photobleaching row
7. `measurements.md` — temporal section
