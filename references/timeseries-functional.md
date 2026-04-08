# Time-Series Functional Imaging

Analysis of timelapse data where the biological signal is a *change in
fluorescence over time* — calcium indicators, voltage sensors, pH reporters,
FRET-based probes, or any drug/stimulus-response experiment with a fluorescent
readout.

Calcium imaging is the primary worked example below (validated on real data).
The same workflow applies to other indicator types with adjusted parameters.

## Parameter Differences by Indicator Type

| Indicator type | Typical dF/F | Frame rate | Smoothing window | min_fold_change |
|---|---|---|---|---|
| Calcium (GCaMP6s) | 50-500% | 1-30 Hz | 11-31 frames | 1.05-1.10 |
| Calcium (chemical, Fluo-4) | 20-200% | 1-10 Hz | 11-31 frames | 1.05-1.10 |
| Voltage (ASAP, Voltron) | 1-5% | 100-1000 Hz | 3-7 frames | 1.01-1.02 |
| pH (pHluorin) | 10-50% | 0.1-1 Hz | 5-15 frames | 1.03-1.05 |
| FRET (CFP/YFP) | 5-30% | 0.1-5 Hz | 7-21 frames | 1.02-1.05 |

For **ratiometric indicators** (Fura-2 340/380, FRET donor/acceptor): compute
the ratio image per frame first, then apply this workflow to the ratio
timeseries.

---

## Segmentation Strategy

Choose based on whether cells are visible in single frames:

**1. Cells visible in individual frames** (bright labeling, high SNR):
Use Cellpose or StarDist on a max or mean time projection. This is standard
segmentation — see `segmentation.md` for tool selection and parameters.

```python
import numpy as np
stack = ...  # shape (T, Y, X)
max_proj = np.max(stack, axis=0)
# or mean_proj = np.mean(stack, axis=0)
# Then segment max_proj with Cellpose/StarDist as usual
```

**2. Cells only visible through activity** (dim baseline, sparse, low SNR):
Standard segmentation fails because there's nothing to segment in any single
frame. Use a normalized activity map instead — see Activity-Based Segmentation
below.

**3. Frame-to-frame motion present**: Register first, then segment.
- Rigid translation: `skimage.registration.phase_cross_correlation`
- Non-rigid / large shifts: suite2p, CaImAn
- Always check registration quality before proceeding

---

## Activity-Based Segmentation

When cells are only visible through their temporal activity (common in calcium
imaging of dim cells like enteric glia, sparse neuronal populations, etc.).

**Why standard approaches fail:**
- **Otsu thresholding** assumes bimodal intensity — fails when active cells are
  a tiny fraction of pixels (background dominates the histogram)
- **Raw std projection** scales with absolute brightness — a bright inactive cell
  has higher std than a dim active cell due to shot noise
- **Max projection** works for very bright transients but misses subtle responders

**The normalized activity map** is brightness-independent:

```python
from bioimage_utils import compute_activity_map

result = compute_activity_map(stack, baseline_frames=slice(0, 200))
activity_map = result["activity_map"]  # std(F/F0) * (max(F/F0) - 1)
f0 = result["f0"]                      # baseline mean, needed for traces later
```

**Segment the activity map** with percentile threshold + watershed:

```python
import numpy as np
from scipy import ndimage as ndi
from skimage.filters import gaussian
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from skimage.measure import label

# Smooth to reduce spurious peaks
smoothed = gaussian(activity_map, sigma=2)

# Percentile threshold — 65th is a reasonable starting point
# Lower = more ROIs (risk of noise), higher = fewer (risk of missing dim cells)
thresh = np.percentile(smoothed[smoothed > 0], 65)
binary = smoothed > thresh

# Watershed to split touching ROIs
distance = ndi.distance_transform_edt(binary)
coords = peak_local_max(distance, min_distance=5, labels=binary)
seed_mask = np.zeros(distance.shape, dtype=bool)
seed_mask[tuple(coords.T)] = True
markers = label(seed_mask)
labels = watershed(-distance, markers, mask=binary)

# Size filter — remove debris and oversized merged regions
from skimage.measure import regionprops
areas = [r.area for r in regionprops(labels)]
if areas:
    median_area = np.median(areas)
    for r in regionprops(labels):
        if r.area < 15 or r.area > median_area * 10:
            labels[labels == r.label] = 0
    labels = label(labels > 0)  # relabel
```

---

## Stimulus / Drug Detection (optional)

Not all experiments have a stimulus — skip for spontaneous activity recordings.

Detect drug addition or stimulus onset from pipetting artifacts (sudden
intensity jumps across the whole field):

```python
import numpy as np

frame_means = np.mean(stack, axis=(1, 2))
diffs = np.abs(np.diff(frame_means))
threshold = np.median(diffs) + 5 * np.std(diffs)
candidate_frames = np.where(diffs > threshold)[0]
# candidate_frames may contain multiple artifacts (pipetting, focus drift, etc.)
# Present ALL candidates to the user — don't assume the first one is the stimulus
```

**Warning**: Multiple artifact frames are common. Always ask the user to confirm
which frame is the actual stimulus. The analysis showed frames 2, 683, 834, 985,
987, 1440, 1666 as candidates — only 683 was the real drug addition.

---

## F/F0 and dF/F0

- **F/F0** = F(t) / F0 — ratio to baseline. Value of 1.0 = no change. Used when
  the user wants to see fold-change (e.g., "2x increase").
- **dF/F0** = (F(t) - F0) / F0 = F/F0 - 1 — fractional change. Value of 0 = no
  change. Used in most neuroscience publications.
- **F0** = mean fluorescence during baseline period (pre-stimulus or first N
  frames if no stimulus).

```python
import numpy as np

# Per-ROI trace extraction
n_rois = labels.max()
traces = np.zeros((n_rois, stack.shape[0]))
for i in range(n_rois):
    mask = labels == (i + 1)
    traces[i] = np.mean(stack[:, mask], axis=1)

# F/F0
baseline_end = 683  # frame of stimulus (or use first 10% if no stimulus)
f0_per_roi = np.mean(traces[:, :baseline_end], axis=1, keepdims=True)
ff0 = traces / f0_per_roi

# dF/F0
dff0 = ff0 - 1.0
```

---

## Photobleaching Correction

Fluorescence intensity decays over time due to photobleaching. If uncorrected,
it biases F/F0 traces downward and can mask real responses.

**Simple approach** — normalize by background region:

```python
# background_trace = mean intensity of a region with no cells, per frame
corrected = traces / background_trace[np.newaxis, :]
```

**Exponential fit** — fit decay to pre-stimulus baseline:

```python
from scipy.optimize import curve_fit

def exp_decay(t, a, b, c):
    return a * np.exp(-b * t) + c

for i in range(n_rois):
    baseline = traces[i, :baseline_end]
    t = np.arange(len(baseline))
    popt, _ = curve_fit(exp_decay, t, baseline, p0=[baseline[0], 0.001, baseline[-1]], maxfev=5000)
    correction = exp_decay(np.arange(traces.shape[1]), *popt)
    traces[i] = traces[i] / correction * correction[0]
```

---

## Response Classification

Use `classify_responses()` from `bioimage_utils.py`:

```python
from bioimage_utils import classify_responses

result = classify_responses(
    ff0,                          # shape (n_rois, n_frames)
    baseline_frames=slice(0, 683),
    n_std=3,                      # permissive default
    min_fold_change=1.05,         # 5% increase minimum
    smoothing_window=31,          # Savitzky-Golay for noisy traces
)

print(f"{result['n_responding']}/{ff0.shape[0]} responding "
      f"({result['fraction_responding']:.1%})")

# Inspect z-scores to decide if threshold is right
# High z-scores (>5) = confident responders
# Borderline (2-4) = check traces visually
```

**Threshold guidance**: start permissive, inspect visually, tighten if needed.
The raw `z_scores` and `peak_ff0` arrays let you adjust after the fact without
re-running.

---

## Common Pitfalls

1. **Applying calcium thresholds to voltage data**: voltage signals are 1-5% dF/F
   vs 50-500% for calcium. A min_fold_change of 1.05 would miss all voltage
   responses. Use the parameter table above.
2. **Over-segmentation from activity maps**: the activity map highlights any pixel
   with temporal variance — including noise at image edges, autofluorescent
   debris, and motion artifacts. Always overlay ROIs on the raw data and inspect.
3. **Multiple pipetting artifacts**: don't assume the first intensity jump is the
   stimulus. Present all candidates and ask the user.
4. **Photobleaching masking responses**: if baseline period spans significant
   bleaching, F0 is overestimated and all F/F0 values are biased low. Correct
   bleaching before computing F/F0, or use a short stable baseline window.
5. **Frame rate assumption**: F/F0 values don't depend on frame rate, but time
   axes, smoothing windows, and response kinetics do. Always confirm frame rate
   from metadata or ask the user.
