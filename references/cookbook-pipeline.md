# End-to-End Pipeline Cookbook

Complete, runnable pipelines that wire together reading, segmentation, QC,
measurement, and export. Use these as templates — adapt parameters to your data.

---

## Pipeline 1: Fluorescence Nuclei (single image)

The most common case: segment nuclei in a DAPI/Hoechst image, measure, export.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from skimage.measure import regionprops_table, label as relabel
from skimage.segmentation import clear_border

# ──────────────────────────────────────────────
# 1. READ
# ──────────────────────────────────────────────
image = tifffile.imread("nuclei.tif")
print(f"Image: {image.shape}, {image.dtype}, range [{image.min()}-{image.max()}]")

pixel_size_um = 0.325  # from metadata — adjust for your microscope

# ──────────────────────────────────────────────
# 2. SEGMENT (StarDist — best default for round nuclei)
# ──────────────────────────────────────────────
from stardist.models import StarDist2D
from csbdeep.utils import normalize

image_norm = normalize(image, pmin=1, pmax=99.8)
model = StarDist2D.from_pretrained("2D_versatile_fluo")
labels, details = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)
print(f"Segmented: {labels.max()} objects")

# ──────────────────────────────────────────────
# 3. POST-PROCESS
# ──────────────────────────────────────────────
# Remove border objects (incomplete measurements)
labels = clear_border(labels)
labels = relabel(labels > 0, connectivity=1)

# Remove small debris (< 50% of median area)
from skimage.measure import regionprops
areas = [p.area for p in regionprops(labels)]
if areas:
    min_area = int(np.median(areas) * 0.3)
    for region in regionprops(labels):
        if region.area < min_area:
            labels[labels == region.label] = 0
    labels = relabel(labels > 0, connectivity=1)
print(f"After cleanup: {labels.max()} objects")

# ──────────────────────────────────────────────
# 4. QC — automated checks
# ──────────────────────────────────────────────
# (paste run_qc_checks from quality-control.md, or import if saved as module)
# qc = run_qc_checks(labels, image, pixel_size_um)
# print(print_qc_report(qc))

# QC — visual overlay
fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} nuclei")
plt.tight_layout()
plt.savefig("analysis/qc_overlay.png", dpi=150, bbox_inches="tight")
plt.show()

# ──────────────────────────────────────────────
# 5. MEASURE
# ──────────────────────────────────────────────
props = pd.DataFrame(regionprops_table(
    labels, intensity_image=image,
    properties=("label", "area", "eccentricity", "solidity",
                "mean_intensity", "max_intensity"),
))
props["area_um2"] = props["area"] * (pixel_size_um ** 2)
props["integrated_intensity_au"] = props["mean_intensity"] * props["area"]
props = props.rename(columns={
    "mean_intensity": "mean_intensity_au",
    "max_intensity": "max_intensity_au",
})

# ──────────────────────────────────────────────
# 6. EXPORT
# ──────────────────────────────────────────────
import os
os.makedirs("analysis", exist_ok=True)

tifffile.imwrite("analysis/labels.tif", labels.astype(np.int32), compression="zlib")
props.to_csv("analysis/measurements.csv", index=False)

# Summary
print(f"\nResults: {len(props)} nuclei")
print(f"  Median area: {props['area_um2'].median():.1f} µm²")
print(f"  Median intensity: {props['mean_intensity_au'].median():.1f} a.u.")
print(f"  Saved: analysis/labels.tif, analysis/measurements.csv")
```

---

## Pipeline 2: Cellpose for Irregular Cells (single image)

For cells with irregular shapes, cytoplasm stains, or touching objects.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from skimage.measure import regionprops_table, regionprops, label as relabel
from skimage.segmentation import clear_border

# ──────────────────────────────────────────────
# 1. READ
# ──────────────────────────────────────────────
image = tifffile.imread("cells.tif")
print(f"Image: {image.shape}, {image.dtype}")

pixel_size_um = 0.65

# ──────────────────────────────────────────────
# 2. SEGMENT (Cellpose)
# ──────────────────────────────────────────────
from cellpose import models

model = models.Cellpose(model_type="cyto3", gpu=True)
# Set diameter from manual measurement of ~5 cells, or None for auto
labels, flows, styles, diams = model.eval(
    image, diameter=None, channels=[0, 0],
    flow_threshold=0.4, cellprob_threshold=0.0,
)
print(f"Segmented: {labels.max()} cells (est. diameter: {diams:.0f} px)")

# ──────────────────────────────────────────────
# 3. POST-PROCESS
# ──────────────────────────────────────────────
labels = clear_border(labels)
labels = relabel(labels > 0, connectivity=1)

areas = [p.area for p in regionprops(labels)]
if areas:
    min_area = int(np.median(areas) * 0.2)
    for region in regionprops(labels):
        if region.area < min_area:
            labels[labels == region.label] = 0
    labels = relabel(labels > 0, connectivity=1)
print(f"After cleanup: {labels.max()} cells")

# ──────────────────────────────────────────────
# 4. QC — visual
# ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} cells")
plt.tight_layout()
plt.savefig("analysis/qc_overlay.png", dpi=150, bbox_inches="tight")
plt.show()

# ──────────────────────────────────────────────
# 5. MEASURE & EXPORT
# ──────────────────────────────────────────────
import os
os.makedirs("analysis", exist_ok=True)

props = pd.DataFrame(regionprops_table(
    labels, intensity_image=image,
    properties=("label", "area", "eccentricity", "solidity",
                "mean_intensity", "max_intensity"),
))
props["area_um2"] = props["area"] * (pixel_size_um ** 2)
props = props.rename(columns={
    "mean_intensity": "mean_intensity_au",
    "max_intensity": "max_intensity_au",
})

tifffile.imwrite("analysis/labels.tif", labels.astype(np.int32), compression="zlib")
props.to_csv("analysis/measurements.csv", index=False)

print(f"\nResults: {len(props)} cells")
print(f"  Median area: {props['area_um2'].median():.1f} µm²")
```

---

## Pipeline 3: Batch Processing (multiple images)

Process a directory of images with the same pipeline. Collect all measurements
into one CSV with a filename column.

```python
import numpy as np
import pandas as pd
import tifffile
import os
from pathlib import Path
from skimage.measure import regionprops_table, regionprops, label as relabel
from skimage.segmentation import clear_border
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
input_dir = Path("images/")
output_dir = Path("analysis/")
output_dir.mkdir(exist_ok=True)

pixel_size_um = 0.325
image_files = sorted(input_dir.glob("*.tif"))
print(f"Found {len(image_files)} images")

# Load model once (not per-image)
model = StarDist2D.from_pretrained("2D_versatile_fluo")

# ──────────────────────────────────────────────
# PROCESS
# ──────────────────────────────────────────────
all_measurements = []

for img_path in image_files:
    print(f"Processing {img_path.name}...")

    # Read
    image = tifffile.imread(str(img_path))

    # Segment
    image_norm = normalize(image, pmin=1, pmax=99.8)
    labels, _ = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)

    # Post-process
    labels = clear_border(labels)
    labels = relabel(labels > 0, connectivity=1)
    areas = [p.area for p in regionprops(labels)]
    if areas:
        min_area = int(np.median(areas) * 0.3)
        for region in regionprops(labels):
            if region.area < min_area:
                labels[labels == region.label] = 0
        labels = relabel(labels > 0, connectivity=1)

    # Save labels
    tifffile.imwrite(
        str(output_dir / f"{img_path.stem}_labels.tif"),
        labels.astype(np.int32), compression="zlib",
    )

    # Measure
    props = pd.DataFrame(regionprops_table(
        labels, intensity_image=image,
        properties=("label", "area", "eccentricity", "solidity",
                    "mean_intensity", "max_intensity"),
    ))
    props["area_um2"] = props["area"] * (pixel_size_um ** 2)
    props["filename"] = img_path.name
    all_measurements.append(props)

    print(f"  → {labels.max()} objects")

# ──────────────────────────────────────────────
# EXPORT
# ──────────────────────────────────────────────
combined = pd.concat(all_measurements, ignore_index=True)
combined.to_csv(output_dir / "all_measurements.csv", index=False)

print(f"\nDone: {len(combined)} total objects from {len(image_files)} images")
print(f"Saved to {output_dir / 'all_measurements.csv'}")
```
