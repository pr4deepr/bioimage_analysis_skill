# End-to-End Pipeline Cookbook

Complete, runnable pipelines using `ResultsManager` from `cookbook-results.md`.
Every run creates an organized folder with step subfolders and an HTML manifest.

---

## Pipeline 1: Fluorescence Nuclei (single image)

The most common case: segment nuclei in a DAPI/Hoechst image, measure, export.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from skimage.measure import regionprops_table, regionprops, label as relabel
from skimage.segmentation import clear_border
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# (paste ResultsManager from cookbook-results.md, or import if saved as module)

# ── Initialize results ──
results = ResultsManager("analysis", "stardist_nuclei")

# ── 1. READ ──
image = tifffile.imread("nuclei.tif")
pixel_size_um = 0.325
results.set_params(image="nuclei.tif", pixel_size_um=pixel_size_um,
                   dtype=str(image.dtype), shape=str(image.shape))

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
ax.set_title(f"Raw image ({image.shape[0]}×{image.shape[1]}, {image.dtype})")
results.save_figure(fig, "raw_preview.png", step="01_raw")

# ── 2. SEGMENT (StarDist) ──
image_norm = normalize(image, pmin=1, pmax=99.8)
model = StarDist2D.from_pretrained("2D_versatile_fluo")
labels, details = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)
results.set_params(model="StarDist 2D_versatile_fluo", prob_thresh=0.5, nms_thresh=0.3)
results.log(f"Segmented: {labels.max()} objects")

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
results.log(f"After cleanup: {labels.max()} objects")

# Save labels + overlay
results.save_image(labels, "labels.tif", step="02_segmentation",
                   description=f"{labels.max()} objects")

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} nuclei")
results.save_figure(fig, "overlay.png", step="02_segmentation",
                    description="Segmentation overlay on raw image")

# ── 3. QC ──
# qc = run_qc_checks(labels, image)  # from quality-control.md
# results.set_qc(qc)
# results.save_text(print_qc_report(qc), "qc_report.txt", step="03_qc")

fig, ax = plt.subplots(figsize=(8, 5))
cal_areas = [p.area * pixel_size_um**2 for p in regionprops(labels)]
ax.hist(cal_areas, bins=30, edgecolor="black", linewidth=0.5, color="#4C72B0")
ax.axvline(np.median(cal_areas), color="red", linestyle="--",
           label=f"Median: {np.median(cal_areas):.1f} µm²")
ax.set_xlabel("Area (µm²)")
ax.set_ylabel("Count")
ax.set_title(f"Size distribution (n={len(cal_areas)})")
ax.legend()
results.save_figure(fig, "histogram_areas.png", step="03_qc",
                    description="Object size distribution")

# ── 4. MEASURE & EXPORT ──
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
results.save_csv(props, "measurements.csv", step="04_measurements",
                 description=f"{len(props)} nuclei measured")

# ── MANIFEST — opens in browser ──
results.write_manifest()
print(f"\nDone: {len(props)} nuclei → {results.run_dir}")
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
from cellpose import models

# (paste ResultsManager from cookbook-results.md)

# ── Initialize results ──
results = ResultsManager("analysis", "cellpose_cells")

# ── 1. READ ──
image = tifffile.imread("cells.tif")
pixel_size_um = 0.65
results.set_params(image="cells.tif", pixel_size_um=pixel_size_um)

# ── 2. SEGMENT (Cellpose) ──
model = models.Cellpose(model_type="cyto3", gpu=True)
labels, flows, styles, diams = model.eval(
    image, diameter=None, channels=[0, 0],
    flow_threshold=0.4, cellprob_threshold=0.0,
)
results.set_params(model="Cellpose cyto3", diameter=f"{diams:.0f} (auto)",
                   flow_threshold=0.4, cellprob_threshold=0.0)
results.log(f"Segmented: {labels.max()} cells")

# ── 3. POST-PROCESS ──
labels = clear_border(labels)
labels = relabel(labels > 0, connectivity=1)
areas = [p.area for p in regionprops(labels)]
if areas:
    min_area = int(np.median(areas) * 0.2)
    for region in regionprops(labels):
        if region.area < min_area:
            labels[labels == region.label] = 0
    labels = relabel(labels > 0, connectivity=1)
results.log(f"After cleanup: {labels.max()} cells")

# Save labels + overlay
results.save_image(labels, "labels.tif", step="02_segmentation",
                   description=f"{labels.max()} cells")

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} cells")
results.save_figure(fig, "overlay.png", step="02_segmentation")

# ── 4. MEASURE & EXPORT ──
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
results.save_csv(props, "measurements.csv", step="04_measurements",
                 description=f"{len(props)} cells measured")

results.write_manifest()
print(f"\nDone: {len(props)} cells → {results.run_dir}")
```

---

## Pipeline 3: Batch Processing (multiple images)

Process a directory of images. Each image gets its own labels file;
all measurements go into one combined CSV. Uses a single run folder.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from pathlib import Path
from skimage.measure import regionprops_table, regionprops, label as relabel
from skimage.segmentation import clear_border
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# (paste ResultsManager from cookbook-results.md)

# ── Config ──
input_dir = Path("images/")
pixel_size_um = 0.325
image_files = sorted(input_dir.glob("*.tif"))

results = ResultsManager("analysis", f"batch_stardist_{len(image_files)}imgs")
results.set_params(input_dir=str(input_dir), n_images=len(image_files),
                   pixel_size_um=pixel_size_um, model="StarDist 2D_versatile_fluo")

# Load model once
model = StarDist2D.from_pretrained("2D_versatile_fluo")

# ── Process ──
all_measurements = []

for img_path in image_files:
    results.log(f"Processing {img_path.name}")
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

    # Save labels (suppress auto-open during batch)
    results.save_image(labels, f"{img_path.stem}_labels.tif",
                       step="02_segmentation",
                       description=f"{labels.max()} objects")

    # Measure
    props = pd.DataFrame(regionprops_table(
        labels, intensity_image=image,
        properties=("label", "area", "eccentricity", "solidity",
                    "mean_intensity", "max_intensity"),
    ))
    props["area_um2"] = props["area"] * (pixel_size_um ** 2)
    props["filename"] = img_path.name
    all_measurements.append(props)

    results.log(f"  {img_path.name}: {labels.max()} objects")

# ── Export combined ──
combined = pd.concat(all_measurements, ignore_index=True)
results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                 description=f"{len(combined)} objects from {len(image_files)} images")

# Summary plot
fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(combined["area_um2"], bins=50, edgecolor="black", linewidth=0.5, color="#4C72B0")
ax.set_xlabel("Area (µm²)")
ax.set_ylabel("Count")
ax.set_title(f"All objects (n={len(combined)} from {len(image_files)} images)")
results.save_figure(fig, "histogram_all_areas.png", step="03_qc",
                    description="Combined size distribution", show=False)

# ── Manifest ──
results.write_manifest()
print(f"\nDone: {len(combined)} objects from {len(image_files)} images → {results.run_dir}")
```
