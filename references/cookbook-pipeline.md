# End-to-End Pipeline Cookbook

Complete, runnable pipelines. Each creates an organized `analysis/` folder with
step subfolders. Uses `clean_labels()` from `bioimage_utils.py` for post-processing.

---

## Pipeline 1: Fluorescence Nuclei (single image)

The most common case: segment nuclei in a DAPI/Hoechst image, measure, export.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from skimage.measure import regionprops_table, regionprops
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# (paste clean_labels from bioimage_utils.py, or import if saved as module)
# (paste ResultsManager from quality-control.md or saved module)

# ── Initialize ──
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
labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.3)
results.log(f"After cleanup: {stats['n_after']} objects "
            f"(removed {stats['n_border_removed']} border, "
            f"{stats['n_small_removed']} small)")

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
from skimage.measure import regionprops_table, regionprops
from cellpose import models

# (paste clean_labels from bioimage_utils.py)
# (paste ResultsManager)

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
labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.2)
results.log(f"After cleanup: {stats['n_after']} cells "
            f"(removed {stats['n_border_removed']} border, "
            f"{stats['n_small_removed']} small)")

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
all measurements go into one combined CSV.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from pathlib import Path
from skimage.measure import regionprops_table, regionprops
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# (paste clean_labels from bioimage_utils.py)
# (paste ResultsManager)

input_dir = Path("images/")
pixel_size_um = 0.325
image_files = sorted(input_dir.glob("*.tif"))

results = ResultsManager("analysis", f"batch_stardist_{len(image_files)}imgs")
results.set_params(input_dir=str(input_dir), n_images=len(image_files),
                   pixel_size_um=pixel_size_um, model="StarDist 2D_versatile_fluo")

# Load model once
model = StarDist2D.from_pretrained("2D_versatile_fluo")

all_measurements = []

for img_path in image_files:
    results.log(f"Processing {img_path.name}")
    image = tifffile.imread(str(img_path))

    # Segment
    image_norm = normalize(image, pmin=1, pmax=99.8)
    labels, _ = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)

    # Post-process
    labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.3)

    # Save labels (show=False during batch to avoid opening hundreds of viewers)
    results.save_image(labels, f"{img_path.stem}_labels.tif",
                       step="02_segmentation",
                       description=f"{stats['n_after']} objects")

    # Measure
    props = pd.DataFrame(regionprops_table(
        labels, intensity_image=image,
        properties=("label", "area", "eccentricity", "solidity",
                    "mean_intensity", "max_intensity"),
    ))
    props["area_um2"] = props["area"] * (pixel_size_um ** 2)
    props["filename"] = img_path.name
    all_measurements.append(props)

    results.log(f"  {img_path.name}: {stats['n_after']} objects")

# Export combined
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

results.write_manifest()
print(f"\nDone: {len(combined)} objects from {len(image_files)} images → {results.run_dir}")
```

---

## Pipeline 4: Large 2D Image — Tiled Processing

For whole-slide histology, OPAL multiplex, CometAssay mosaics, or any image too
large to load into RAM at once. Uses tifffile to read tiles without loading the
full image.

**Workflow: crop → tune → full run.**

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from pathlib import Path
from skimage.measure import regionprops_table, regionprops

# (paste clean_labels from bioimage_utils.py)
# (paste estimate_memory from bioimage_utils.py)
# (paste ResultsManager)

image_path = "slide.tif"

# ── 1. CHECK SIZE (read metadata only, no pixel loading) ──
with tifffile.TiffFile(image_path) as tif:
    page = tif.pages[0]
    full_shape = (page.imagelength, page.imagewidth)
    dtype = page.dtype
    n_channels = page.samplesperpixel
    print(f"Image: {full_shape[1]}×{full_shape[0]}, {dtype}, {n_channels}ch")

mem = estimate_memory(full_shape + (n_channels,) if n_channels > 1 else full_shape,
                      dtype=str(dtype))
print(f"Single array: {mem['size_gb']:.2f} GB, peak: {mem['peak_gb']:.2f} GB")
print(f"Fits in RAM: {mem['fits_in_ram']}")
if mem['warning']:
    print(f"⚠ {mem['warning']}")

# ── 2. EXTRACT CROP FOR PARAMETER TUNING ──
# Read a small region without loading the full image
crop_size = 1024
cy, cx = full_shape[0] // 2, full_shape[1] // 2
crop = tifffile.imread(image_path,
                       key=0,  # first page/plane
                       )[cy:cy+crop_size, cx:cx+crop_size]

# Tune segmentation parameters on the crop
from cellpose import models
model = models.Cellpose(model_type="cyto3", gpu=True)

# Try different diameters on the crop
for diameter in [30, 50, 80]:
    test_labels, _, _, _ = model.eval(crop, diameter=diameter, channels=[0, 0])
    print(f"  diameter={diameter}: {test_labels.max()} objects")

# Pick the best diameter based on results
best_diameter = 50  # ← set after reviewing crop results

# ── 3. TILED PROCESSING ──
tile_size = 2048
overlap = 256  # overlap should be > largest expected object diameter
results = ResultsManager("analysis", "tiled_large_image")
results.set_params(image=image_path, tile_size=tile_size, overlap=overlap,
                   diameter=best_diameter, full_shape=str(full_shape))

all_measurements = []
full_labels = np.zeros(full_shape, dtype=np.int32)
label_offset = 0

for y in range(0, full_shape[0], tile_size - overlap):
    for x in range(0, full_shape[1], tile_size - overlap):
        # Read one tile (tifffile reads from disk, not RAM)
        y_end = min(y + tile_size, full_shape[0])
        x_end = min(x + tile_size, full_shape[1])
        tile = tifffile.imread(image_path, key=0)[y:y_end, x:x_end]

        # Segment the tile
        tile_labels, _, _, _ = model.eval(
            tile, diameter=best_diameter, channels=[0, 0])

        # Post-process
        tile_labels, stats = clean_labels(
            tile_labels, remove_border=False, min_area_fraction=0.2)

        # Remove objects in the overlap zone (they'll be in the next tile too)
        # Keep only objects whose centroid is in the non-overlap region
        inner_y = overlap // 2 if y > 0 else 0
        inner_x = overlap // 2 if x > 0 else 0
        for region in regionprops(tile_labels):
            cy_r, cx_r = region.centroid
            if cy_r < inner_y or cx_r < inner_x:
                tile_labels[tile_labels == region.label] = 0

        # Place in full label image with offset
        mask = tile_labels > 0
        tile_labels[mask] += label_offset
        full_labels[y:y_end, x:x_end][mask] = tile_labels[mask]
        label_offset = full_labels.max()

        # Measure this tile
        if tile_labels.max() > 0:
            props = pd.DataFrame(regionprops_table(
                tile_labels, intensity_image=tile,
                properties=("label", "area", "centroid",
                            "mean_intensity"),
            ))
            # Adjust centroid to full-image coordinates
            props["centroid-0"] += y
            props["centroid-1"] += x
            all_measurements.append(props)

        results.log(f"Tile ({y},{x}): {stats['n_after']} objects")

# ── 4. EXPORT ──
combined = pd.concat(all_measurements, ignore_index=True)
results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                 description=f"{len(combined)} objects from tiled processing")

results.write_manifest()
print(f"\nDone: {len(combined)} objects → {results.run_dir}")
```

**Notes:**
- For pyramidal TIFFs (e.g., from slide scanners), use `openslide` for efficient
  tile reading: `slide.read_region((x, y), level=0, (tile_size, tile_size))`
- For OME-ZARR, use `zarr.open(path)[y:y_end, x:x_end]` for lazy chunk access
- Tile overlap should be larger than the biggest expected object diameter
- The centroid-in-inner-region strategy handles stitching without duplicate objects
- For dask-based lazy loading: `dask_image.imread(path)` gives a dask array that
  reads tiles on demand — useful when combined with `dask.delayed` for parallel tile processing

---

## Pipeline 5: 3D Volume / Timelapse — Chunked Processing

For z-stacks, light-sheet volumes, or timelapses too large to load at once.
Processes one plane or timepoint at a time.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from pathlib import Path
from skimage.measure import regionprops_table, regionprops

# (paste clean_labels from bioimage_utils.py)
# (paste estimate_memory from bioimage_utils.py)
# (paste ResultsManager)

image_path = "stack.tif"

# ── 1. CHECK SIZE ──
with tifffile.TiffFile(image_path) as tif:
    # For multi-page TIFFs, each page is one plane/timepoint
    n_pages = len(tif.pages)
    page = tif.pages[0]
    plane_shape = (page.imagelength, page.imagewidth)
    dtype = page.dtype
    print(f"Stack: {n_pages} planes, each {plane_shape[1]}×{plane_shape[0]}, {dtype}")

full_shape = (n_pages,) + plane_shape
mem = estimate_memory(full_shape, dtype=str(dtype))
print(f"Full volume: {mem['size_gb']:.2f} GB | Fits in RAM: {mem['fits_in_ram']}")

# ── 2. CROP-FIRST: tune on one representative plane ──
# Pick middle plane for tuning (or use max-intensity projection of a few planes)
mid_idx = n_pages // 2
test_plane = tifffile.imread(image_path, key=mid_idx)

# Optional: if single plane is also large, crop it
# test_crop = test_plane[500:1500, 500:1500]

from cellpose import models
model = models.Cellpose(model_type="cyto3", gpu=True)

# Tune on test plane
for diameter in [20, 40, 60]:
    test_labels, _, _, _ = model.eval(test_plane, diameter=diameter, channels=[0, 0])
    print(f"  diameter={diameter}: {test_labels.max()} objects")

best_diameter = 40  # ← set after reviewing

# ── 3. PROCESS PLANE-BY-PLANE ──
results = ResultsManager("analysis", "3d_planewise")
results.set_params(image=image_path, n_planes=n_pages, plane_shape=str(plane_shape),
                   diameter=best_diameter)

all_measurements = []

for z in range(n_pages):
    # Read one plane at a time — never holds full volume in RAM
    plane = tifffile.imread(image_path, key=z)

    # Segment
    labels, _, _, _ = model.eval(plane, diameter=best_diameter, channels=[0, 0])

    # Post-process
    labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.3)

    # Measure
    if labels.max() > 0:
        props = pd.DataFrame(regionprops_table(
            labels, intensity_image=plane,
            properties=("label", "area", "eccentricity",
                        "mean_intensity"),
        ))
        props["z_plane"] = z
        all_measurements.append(props)

    if z % 10 == 0:
        results.log(f"Plane {z}/{n_pages}: {stats['n_after']} objects")

# ── 4. EXPORT ──
combined = pd.concat(all_measurements, ignore_index=True)
results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                 description=f"{len(combined)} objects across {n_pages} planes")

# Summary: objects per plane
fig, ax = plt.subplots(figsize=(8, 4))
per_plane = combined.groupby("z_plane").size()
ax.plot(per_plane.index, per_plane.values)
ax.set_xlabel("Z plane")
ax.set_ylabel("Object count")
ax.set_title("Objects per plane")
results.save_figure(fig, "objects_per_plane.png", step="03_qc", show=False)

results.write_manifest()
print(f"\nDone: {len(combined)} objects across {n_pages} planes → {results.run_dir}")
```

**3D segmentation alternatives (when 3D context matters):**
- **Cellpose 3D**: `model.eval(volume, do_3D=True, diameter=40)` — segments the
  full volume using 3D flow fields. Requires loading the full volume into RAM.
  For large volumes, use dask: `volume = dask.array.from_zarr("stack.zarr")`
  and process in overlapping sub-volumes.
- **PlantSeg**: purpose-built for 3D cell segmentation in plant tissue and
  cleared samples. Uses 3D U-Net + graph partitioning.
- **2D-per-slice vs true 3D**: 2D-per-slice (this pipeline) is faster and uses
  less RAM, but loses z-continuity — objects aren't tracked across planes.
  True 3D gives connected objects but needs the full volume (or large chunks) in memory.

**Timelapse variant:** Replace `z_plane` with `timepoint`. For tracking objects
across timepoints, use `btrack` or `trackpy` after per-frame segmentation.

**Dask for lazy loading:** For zarr-backed data, use dask arrays to avoid loading
the full volume. Each slice access reads only that chunk from disk:
```python
import dask.array as da
import zarr

z = zarr.open("stack.zarr", mode="r")
volume = da.from_zarr(z)  # lazy — nothing loaded yet
plane = volume[z_idx].compute()  # loads one plane
```
