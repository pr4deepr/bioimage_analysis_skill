# Quality Control Checklist

Run through these checks after segmentation, before trusting any measurements.
Present them to the user in order — each check catches a different failure mode.

## 1. Visual Overlay

Overlay segmentation masks on the raw image. Do boundaries match the objects?

- Check at least 5-10 images per condition
- Look specifically for: over-segmentation (one cell split into many), under-segmentation
  (multiple cells merged), boundary misalignment (mask shifted from actual cell edge)
- In Python: use napari (add labels layer over image) or matplotlib contour overlay on
  the raw image. In FIJI: use Image > Overlay > Add Image or the ROI Manager.

```python
# matplotlib overlay
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(10, 10))
ax.imshow(image, cmap='gray')
ax.contour(labels > 0, colors='cyan', linewidths=0.5)
ax.set_title(f'Segmentation overlay — {labels.max()} objects')
ax.axis('off')
plt.tight_layout()
```

> napari: See cookbook-visualization.md § Add segmentation overlay

## 2. Object Count Sanity Check

Does the automated count match manual count in a few representative fields?

- Pick 3-5 images with varying density
- Count manually (or use FIJI multi-point tool)
- Compare. If automated count is consistently >20% off, the segmentation needs tuning.
- Under-counting usually means objects are being merged or missed
- Over-counting usually means debris/noise is being detected or objects are being split

```python
n_objects = labels.max()
print(f"Automated count: {n_objects}")
# Compare with manual count from a few representative fields
```

## 3. Size Distribution

Plot a histogram of object areas across all images.

What to look for:
- **Bimodal peak**: likely merged objects (large peak) alongside correctly segmented ones,
  or two genuine biological populations. Inspect the large objects to determine which.
- **Spike at very small values**: debris, noise, or fragmented segmentation artifacts.
  Set a minimum area filter (e.g., exclude objects < 50% of expected cell area).
- **Suspiciously uniform sizes**: possible over-segmentation artifact where a watershed
  or similar method is splitting objects into equal-sized pieces.
- **Long right tail**: a few very large objects are almost always merged clusters. Check them.

```python
from skimage.measure import regionprops
import matplotlib.pyplot as plt
areas = [p.area * pixel_size**2 for p in regionprops(labels)]
fig, ax = plt.subplots()
ax.hist(areas, bins=50, edgecolor='black')
ax.set_xlabel('Area (µm²)')
ax.set_ylabel('Count')
ax.set_title('Object size distribution')
plt.tight_layout()
```

## 4. Edge Case Images

Check the images with the highest and lowest object counts in your dataset.

- Highest-count images: often high-density fields where segmentation struggles with
  touching objects. Verify objects are actually separated correctly.
- Lowest-count images: may be out-of-focus, have unusual staining, or contain mostly
  background. Verify the low count is real and not a segmentation failure.
- These extremes are where failures concentrate — fixing them often improves the whole dataset.

```python
# After processing all images, find extremes for inspection
# counts = {fname: label_img.max() for fname, label_img in results.items()}
# sorted_by_count = sorted(counts.items(), key=lambda x: x[1])
# Check lowest 3: sorted_by_count[:3]
# Check highest 3: sorted_by_count[-3:]
```

## 5. Measurement Distributions

Plot distributions of your key measurements across all objects.

- **Values at floor/ceiling**: if >5% of measurements are at the minimum or maximum
  possible value, something is wrong. Common causes: intensity saturation, zero-area
  objects from segmentation artifacts, or touching-border objects with truncated measurements.
- **Unexpected outliers**: extreme values may be real biology or segmentation errors.
  Inspect the source images for the top/bottom 1% of any measurement.
- **Condition-specific artifacts**: plot distributions separately per condition. If one
  condition has a wildly different distribution shape (not just shifted mean), check whether
  imaging conditions differed (focus, exposure, staining intensity).

```python
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].hist(areas, bins=50)
axes[0].set_title('Area distribution')
axes[0].set_xlabel('Area (µm²)')
axes[1].hist(mean_intensities, bins=50)
axes[1].set_title('Mean intensity')
axes[1].set_xlabel('Intensity (a.u.)')
axes[2].hist(eccentricities, bins=50)
axes[2].set_title('Eccentricity')
axes[2].set_xlabel('Eccentricity')
plt.tight_layout()
```

## 6. Batch Effects (if applicable)

If data spans multiple plates, slides, or imaging sessions:

- Compare measurement distributions across batches for control conditions
- If controls differ across batches, you have a batch effect that will confound your analysis
- Common causes: different exposure times, lamp intensity drift, staining variability
- Mitigation: normalize measurements per-batch (z-score within batch), or include batch
  as a covariate in statistical models

```python
import pandas as pd
import matplotlib.pyplot as plt
control_data = df[df['condition'] == 'control']
fig, ax = plt.subplots()
control_data.boxplot(column='area_um2', by='batch', ax=ax)
ax.set_title('Area by batch (controls only)')
ax.set_ylabel('Area (µm²)')
plt.tight_layout()
```

---

## Automated QC Checks

Run these programmatically after every segmentation. They catch common failures
without requiring manual inspection. **Flag issues to the user; don't silently
proceed.**

```python
import numpy as np
from skimage.measure import regionprops

def run_qc_checks(labels, image=None, pixel_size_um=None):
    """Run automated QC checks on segmentation results.

    Returns a dict of check_name -> {passed: bool, message: str, value: any}.
    Any failed check should be shown to the user before proceeding.
    """
    results = {}
    props = regionprops(labels, intensity_image=image)
    areas = np.array([p.area for p in props])
    n_objects = len(props)

    # Check 1: Did we find any objects at all?
    results["object_count"] = {
        "passed": n_objects > 0,
        "message": f"Found {n_objects} objects" if n_objects > 0
                   else "No objects found — segmentation likely failed",
        "value": n_objects,
    }
    if n_objects == 0:
        return results  # no point running other checks

    # Check 2: Size outliers — objects >5x or <0.2x the median area
    median_area = np.median(areas)
    too_large = np.sum(areas > 5 * median_area)
    too_small = np.sum(areas < 0.2 * median_area)
    outlier_frac = (too_large + too_small) / n_objects
    results["size_outliers"] = {
        "passed": outlier_frac < 0.10,
        "message": f"{too_large} oversized + {too_small} undersized objects "
                   f"({outlier_frac:.0%} of total, median area={median_area:.0f} px)",
        "value": {"too_large": int(too_large), "too_small": int(too_small),
                  "median_area": float(median_area)},
    }

    # Check 3: Border objects — what fraction touches the image edge?
    h, w = labels.shape
    border_labels = set()
    border_labels.update(np.unique(labels[0, :]))    # top
    border_labels.update(np.unique(labels[-1, :]))   # bottom
    border_labels.update(np.unique(labels[:, 0]))    # left
    border_labels.update(np.unique(labels[:, -1]))   # right
    border_labels.discard(0)
    border_frac = len(border_labels) / n_objects
    results["border_objects"] = {
        "passed": border_frac < 0.30,
        "message": f"{len(border_labels)} objects touch the border ({border_frac:.0%})",
        "value": {"count": len(border_labels), "fraction": float(border_frac)},
    }

    # Check 4: Area coefficient of variation — suspiciously uniform?
    area_cv = np.std(areas) / np.mean(areas) if np.mean(areas) > 0 else 0
    results["area_variation"] = {
        "passed": area_cv > 0.05,  # very low CV suggests over-segmentation artifact
        "message": f"Area CV = {area_cv:.2f}" +
                   (" (suspiciously uniform — possible over-segmentation)" if area_cv <= 0.05 else ""),
        "value": float(area_cv),
    }

    # Check 5: Intensity sanity (if image provided)
    if image is not None:
        intensities = np.array([p.mean_intensity for p in props])
        # Check for saturated objects (mean intensity near max possible value)
        max_possible = np.iinfo(image.dtype).max if np.issubdtype(image.dtype, np.integer) else image.max()
        saturated = np.sum(intensities > 0.95 * max_possible)
        sat_frac = saturated / n_objects
        results["saturation"] = {
            "passed": sat_frac < 0.05,
            "message": f"{saturated} objects appear saturated ({sat_frac:.0%})" if saturated > 0
                       else "No saturated objects detected",
            "value": {"count": int(saturated), "fraction": float(sat_frac)},
        }

    return results


def print_qc_report(qc_results):
    """Format QC results for display to the user."""
    all_passed = all(r["passed"] for r in qc_results.values())
    lines = []
    for name, result in qc_results.items():
        status = "PASS" if result["passed"] else "WARN"
        lines.append(f"  [{status}] {name}: {result['message']}")
    header = "QC: all checks passed" if all_passed else "QC: issues found — review before proceeding"
    return header + "\n" + "\n".join(lines)
```

**Usage:** Run `run_qc_checks()` after every segmentation. If any check fails,
show the report to the user and ask whether to proceed, adjust parameters, or
try a different approach. Never skip QC silently.

---

## Quick Reference: Common Problems and Diagnosis

| Symptom | Likely cause | Fix |
|---|---|---|
| Too many small objects | Debris detection | Add minimum area filter |
| Too few objects | Threshold too stringent | Lower threshold or switch to adaptive |
| Objects merged together | Threshold too permissive, or no watershed | Add watershed, use instance segmentation (Cellpose/StarDist) |
| Jagged boundaries | Low resolution or aggressive thresholding | Smooth image first, or use model-based segmentation |
| Counts vary wildly between similar images | Inconsistent illumination | Flat-field correction, or use adaptive thresholding |
| Intensity measurements unreliable | No background subtraction | Subtract local background before measuring |
