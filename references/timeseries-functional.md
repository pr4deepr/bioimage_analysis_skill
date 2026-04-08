# Time-Series Functional Imaging

For timelapse data where the signal is a *change in fluorescence over time* —
calcium indicators, voltage sensors, pH reporters, FRET probes, or any
drug/stimulus-response experiment. Calcium imaging is the worked example
(validated on real data). Same workflow applies to other indicators with
adjusted parameters.

## Segmentation Decision Tree

| Condition | Approach |
|---|---|
| Cells visible in single frames (bright, high SNR) | Cellpose/StarDist on max or mean time projection — standard segmentation |
| Cells only visible through activity (dim, sparse) | `compute_activity_map()` + percentile threshold + watershed |
| Frame-to-frame motion present | Register first (`skimage.registration.phase_cross_correlation` for rigid; suite2p/CaImAn for non-rigid), then segment |

## Why Standard Segmentation Fails on Dim Functional Data

- **Otsu** assumes bimodal intensity — fails when active cells are a tiny
  fraction of pixels (background dominates the histogram)
- **Raw std projection** scales with absolute brightness — a bright inactive
  cell has higher std than a dim active cell due to shot noise
- **Max projection** catches bright transients but misses subtle responders

The normalized activity map (`compute_activity_map()` in `bioimage_utils.py`)
is brightness-independent: `std(F/F0) * (max(F/F0) - 1)`. A dim cell with
20% change scores the same as a bright cell with 20% change. Segment the
activity map with percentile threshold + watershed (same pattern as
`segmentation.md` Classical Approaches).

## Stimulus / Drug Detection

Not all experiments have a stimulus — skip for spontaneous activity recordings.

```python
import numpy as np

frame_means = np.mean(stack, axis=(1, 2))
diffs = np.abs(np.diff(frame_means))
threshold = np.median(diffs) + 5 * np.std(diffs)
candidate_frames = np.where(diffs > threshold)[0]
# Present ALL candidates to user — don't assume the first one is the stimulus
```

**Warning**: Multiple artifact frames are common (pipetting, focus drift).
Always ask the user to confirm which frame is the actual stimulus.

## F/F0 vs dF/F0

- **F/F0** = F(t) / F0 — fold-change (1.0 = no change)
- **dF/F0** = F/F0 - 1 — fractional change (0 = no change), standard in neuroscience
- **F0** = mean of baseline period. `compute_activity_map()` returns this as `f0`

Correct **photobleaching** before computing F/F0: normalize by background
region intensity per frame, or fit exponential decay to pre-stimulus baseline.

## Response Classification

Use `classify_responses()` from `bioimage_utils.py`. Start permissive
(defaults: `n_std=3, min_fold_change=1.05`), inspect z-scores, tighten if
needed. For voltage imaging use `min_fold_change=1.01`; for pH/FRET 1.02-1.05.

## Parameter Guidance by Indicator Type

| Indicator | Typical dF/F | Smoothing window | min_fold_change |
|---|---|---|---|
| Calcium (GCaMP, Fluo-4) | 20-500% | 11-31 frames | 1.05-1.10 |
| Voltage (ASAP, Voltron) | 1-5% | 3-7 frames | 1.01-1.02 |
| pH (pHluorin) | 10-50% | 5-15 frames | 1.03-1.05 |
| FRET (CFP/YFP) | 5-30% | 7-21 frames | 1.02-1.05 |

Non-calcium rows are estimated, not validated. For **ratiometric indicators**
(Fura-2, FRET): compute ratio image per frame first, then apply this workflow.

## Common Pitfalls

1. **Calcium thresholds on voltage data**: voltage signals are 1-5% dF/F vs
   50-500% for calcium — a `min_fold_change=1.05` misses all voltage responses
2. **Over-segmentation from activity maps**: highlights any temporal variance
   including noise and motion artifacts — always overlay ROIs on raw data
3. **Multiple pipetting artifacts**: don't assume the first intensity jump is
   the stimulus — present all candidates, ask the user
4. **Photobleaching masking responses**: if baseline spans significant bleaching,
   F0 is overestimated and F/F0 is biased low — correct bleaching first
5. **Frame rate assumption**: F/F0 doesn't depend on frame rate, but time axes,
   smoothing windows, and response kinetics do — confirm from metadata
