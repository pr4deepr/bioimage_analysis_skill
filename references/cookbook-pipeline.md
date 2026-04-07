# End-to-End Pipeline Cookbook

Complete, runnable pipelines. Each creates an organized `analysis/` folder with
step subfolders. Uses functions from `bioimage_utils.py` for post-processing,
measurements, and results management.

---

## Pipeline 1: Fluorescence Nuclei (single image)

The most common case: segment nuclei in a DAPI/Hoechst image, measure, export.

```python
import numpy as np
import matplotlib.pyplot as plt
import tifffile
from skimage.measure import regionprops
from stardist.models import StarDist2D
from csbdeep.utils import normalize

from bioimage_utils import clean_labels, extract_measurements, ResultsManager

# ── Initialize ──
results = ResultsManager("analysis", "stardist_nuclei")

# ── 1. READ ──
image = tifffile.imread("nuclei.tif")
pixel_size_um = 0.325  # um/pixel — get from metadata or microscope settings
results.set_params(image="nuclei.tif", pixel_size_um=pixel_size_um,
                   dtype=str(image.dtype), shape=str(image.shape))

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
ax.set_title(f"Raw image ({image.shape[0]}x{image.shape[1]}, {image.dtype})")
results.save_figure(fig, "raw_preview.png", step="01_raw")

# ── 2. SEGMENT (StarDist) ──
# StarDist REQUIRES explicit normalization — without it, predictions may be empty
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
ax.imshow(labels_masked, cmap="nipy_spectral", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} nuclei")
results.save_figure(fig, "overlay.png", step="02_segmentation",
                    description="Segmentation overlay on raw image")

# ── 3. QC ──
fig, ax = plt.subplots(figsize=(8, 5))
cal_areas = [p.area * pixel_size_um**2 for p in regionprops(labels)]
ax.hist(cal_areas, bins=30, edgecolor="black", linewidth=0.5, color="#4C72B0")
ax.axvline(np.median(cal_areas), color="red", linestyle="--",
           label=f"Median: {np.median(cal_areas):.1f} um2")
ax.set_xlabel("Area (um2)")
ax.set_ylabel("Count")
ax.set_title(f"Size distribution (n={len(cal_areas)})")
ax.legend()
results.save_figure(fig, "histogram_areas.png", step="03_qc",
                    description="Object size distribution")

# ── 4. MEASURE & EXPORT ──
props = extract_measurements(labels, image, pixel_size_um=pixel_size_um)
results.save_csv(props, "measurements.csv", step="04_measurements",
                 description=f"{len(props)} nuclei measured")

results.write_manifest()
print(f"\nDone: {len(props)} nuclei -> {results.run_dir}")
```

---

## Pipeline 2: Cellpose for Irregular Cells (single image)

For cells with irregular shapes, cytoplasm stains, or touching objects.

**Note**: This uses the Cellpose 3.x API (`models.Cellpose`). For Cellpose 4.x,
use `models.CellposeModel` instead — `diameter` and `channels` are not needed.
See `segmentation.md` for version-specific code.

```python
import numpy as np
import matplotlib.pyplot as plt
import tifffile
from cellpose import models

from bioimage_utils import clean_labels, extract_measurements, ResultsManager

results = ResultsManager("analysis", "cellpose_cells")

# ── 1. READ ──
image = tifffile.imread("cells.tif")
pixel_size_um = 0.65  # um/pixel
results.set_params(image="cells.tif", pixel_size_um=pixel_size_um)

# ── 2. SEGMENT (Cellpose 3.x) ──
# For Cellpose 4.x: use models.CellposeModel(model_type="cyto3", gpu=True)
# and model.eval(image) — no diameter or channels needed.
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
ax.imshow(labels_masked, cmap="nipy_spectral", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} cells")
results.save_figure(fig, "overlay.png", step="02_segmentation")

# ── 4. MEASURE & EXPORT ──
props = extract_measurements(labels, image, pixel_size_um=pixel_size_um)
results.save_csv(props, "measurements.csv", step="04_measurements",
                 description=f"{len(props)} cells measured")

results.write_manifest()
print(f"\nDone: {len(props)} cells -> {results.run_dir}")
```

---

## Pipeline 3: Batch Processing (multiple images)

Process a directory of images. Each image gets its own labels file;
all measurements go into one combined CSV. Wraps per-image processing
in try/except so one corrupt file doesn't kill the entire batch.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from pathlib import Path
from stardist.models import StarDist2D
from csbdeep.utils import normalize

from bioimage_utils import clean_labels, extract_measurements, ResultsManager

input_dir = Path("images/")
pixel_size_um = 0.325  # um/pixel
image_files = sorted(input_dir.glob("*.tif"))

results = ResultsManager("analysis", f"batch_stardist_{len(image_files)}imgs")
results.set_params(input_dir=str(input_dir), n_images=len(image_files),
                   pixel_size_um=pixel_size_um, model="StarDist 2D_versatile_fluo")

# Load model once
model = StarDist2D.from_pretrained("2D_versatile_fluo")

all_measurements = []
failed = []

for img_path in image_files:
    try:
        results.log(f"Processing {img_path.name}")
        image = tifffile.imread(str(img_path))

        # Segment
        image_norm = normalize(image, pmin=1, pmax=99.8)
        labels, _ = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)

        # Post-process
        labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.3)

        # Save labels
        results.save_image(labels, f"{img_path.stem}_labels.tif",
                           step="02_segmentation",
                           description=f"{stats['n_after']} objects")

        # Measure
        props = extract_measurements(labels, image, pixel_size_um=pixel_size_um)
        props["filename"] = img_path.name
        all_measurements.append(props)

        results.log(f"  {img_path.name}: {stats['n_after']} objects")
    except Exception as e:
        results.log(f"  FAILED {img_path.name}: {e}")
        failed.append(img_path.name)

# Export combined
if all_measurements:
    combined = pd.concat(all_measurements, ignore_index=True)
    results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                     description=f"{len(combined)} objects from {len(image_files) - len(failed)} images")

    # Summary plot
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(combined["area_um2"], bins=50, edgecolor="black", linewidth=0.5, color="#4C72B0")
    ax.set_xlabel("Area (um2)")
    ax.set_ylabel("Count")
    ax.set_title(f"All objects (n={len(combined)} from {len(image_files) - len(failed)} images)")
    results.save_figure(fig, "histogram_all_areas.png", step="03_qc",
                        description="Combined size distribution")

if failed:
    results.log(f"Failed images ({len(failed)}): {failed}")

results.write_manifest()
print(f"\nDone: {len(all_measurements)} images processed, {len(failed)} failed -> {results.run_dir}")
```

---

## Pipeline 4: Large 2D Image — Tiled Processing

For whole-slide histology, OPAL multiplex, CometAssay mosaics, or any image too
large to load into RAM at once. Uses BioIO's dask backend for lazy loading —
only the requested tile is read from disk.

**Workflow: crop -> tune -> full run.**

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skimage.measure import regionprops_table, regionprops
from bioio import BioImage

from bioimage_utils import clean_labels, estimate_memory, ResultsManager

image_path = "slide.czi"  # works with CZI, LIF, ND2, OME-TIFF, TIFF, etc.

# ── 1. CHECK SIZE (lazy — no pixels loaded) ──
img = BioImage(image_path)
print(f"Dims: {img.dims}")             # e.g. Dimensions [T: 1, C: 3, Z: 1, Y: 40000, X: 50000]
print(f"Shape: {img.shape}")           # (1, 3, 1, 40000, 50000)
print(f"Dtype: {img.dtype}")
print(f"Pixel size: {img.physical_pixel_sizes}")  # PhysicalPixelSizes(Z=None, Y=0.325, X=0.325)

# Dask array — lazy, nothing loaded yet
lazy_data = img.dask_data  # shape: (T, C, Z, Y, X)
full_shape = (img.dims.Y, img.dims.X)

mem = estimate_memory(full_shape, dtype=str(img.dtype))
print(f"Single plane: {mem['size_gb']:.2f} GB, peak: {mem['peak_gb']:.2f} GB")
print(f"Fits in RAM: {mem['fits_in_ram']}")

# ── 2. EXTRACT CROP FOR PARAMETER TUNING ──
# Slice the dask array — only the crop is loaded into RAM
crop_size = 1024
cy, cx = full_shape[0] // 2, full_shape[1] // 2
# C=0 selects channel 0 — adjust to match your segmentation target
# (e.g., C=0 for DAPI/nuclei, C=1 for membrane, etc.)
crop = img.get_image_dask_data("YX", T=0, C=0, Z=0)
crop = crop[cy:cy+crop_size, cx:cx+crop_size].compute()  # only 1024x1024 loaded

# Tune segmentation parameters on the crop
# Note: this uses Cellpose 3.x API. For 4.x, see segmentation.md.
from cellpose import models
model = models.Cellpose(model_type="cyto3", gpu=True)

for diameter in [30, 50, 80]:
    test_labels, _, _, _ = model.eval(crop, diameter=diameter, channels=[0, 0])
    print(f"  diameter={diameter}: {test_labels.max()} objects")

best_diameter = 50  # <- set after reviewing crop results

# ── 3. TILED PROCESSING ──
tile_size = 2048
overlap = 256  # overlap must be > largest expected object diameter
results = ResultsManager("analysis", "tiled_large_image")

# Pixel size from metadata — None means uncalibrated (measurements in pixels)
pixel_size_um = img.physical_pixel_sizes.Y
if pixel_size_um is None:
    print("WARNING: No pixel size in metadata. Measurements will be in pixels.")
results.set_params(image=image_path, tile_size=tile_size, overlap=overlap,
                   diameter=best_diameter, full_shape=str(full_shape),
                   pixel_size_um=pixel_size_um or "uncalibrated")

# Get the 2D dask array for the channel we want
lazy_plane = img.get_image_dask_data("YX", T=0, C=0, Z=0)

all_measurements = []
label_offset = 0

for y in range(0, full_shape[0], tile_size - overlap):
    for x in range(0, full_shape[1], tile_size - overlap):
        y_end = min(y + tile_size, full_shape[0])
        x_end = min(x + tile_size, full_shape[1])

        # Only this tile is loaded from disk
        tile = lazy_plane[y:y_end, x:x_end].compute()

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

        # Measure this tile (no need to hold full label image in RAM)
        if tile_labels.max() > 0:
            tile_labels_offset = tile_labels.copy()
            mask = tile_labels_offset > 0
            tile_labels_offset[mask] += label_offset
            label_offset = tile_labels_offset.max()

            props = pd.DataFrame(regionprops_table(
                tile_labels, intensity_image=tile,
                properties=("label", "area", "centroid",
                            "mean_intensity"),
            ))
            # Adjust centroid to full-image coordinates
            props["centroid-0"] += y
            props["centroid-1"] += x
            if pixel_size_um is not None:
                props["area_um2"] = props["area"] * (pixel_size_um ** 2)
            all_measurements.append(props)

        results.log(f"Tile ({y},{x}): {stats['n_after']} objects")

# ── 4. EXPORT ──
combined = pd.concat(all_measurements, ignore_index=True)
results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                 description=f"{len(combined)} objects from tiled processing")

results.write_manifest()
print(f"\nDone: {len(combined)} objects -> {results.run_dir}")
```

**Notes:**
- **BioIO reads CZI, LIF, ND2, OME-TIFF, TIFF** — no need to handle each format
  differently. Install the right plugin: `pip install bioio-czi`, `bioio-lif`, etc.
- **Pixel size comes from metadata** — `img.physical_pixel_sizes` reads it
  automatically, no manual calibration needed for supported formats
- For pyramidal TIFFs (slide scanners), `openslide` may be faster for tile access
- Tile overlap should be larger than the biggest expected object diameter
- The centroid-in-inner-region strategy handles stitching without duplicate objects
- **Fallback** if BioIO is not installed: use `tifffile.imread(path, key=0)[y:y_end, x:x_end]`

---

## Pipeline 5: 3D Volume / Timelapse — Chunked Processing

For z-stacks, light-sheet volumes, or timelapses too large to load at once.
Uses BioIO's dask backend to load one plane/timepoint at a time without
holding the full volume in RAM.

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skimage.measure import regionprops_table, regionprops
from bioio import BioImage

from bioimage_utils import clean_labels, estimate_memory, ResultsManager

image_path = "stack.czi"  # or .nd2, .lif, .ome.tif, .tif, etc.

# ── 1. CHECK SIZE (lazy — no pixels loaded) ──
img = BioImage(image_path)
print(f"Dims: {img.dims}")             # e.g. Dimensions [T: 1, C: 2, Z: 50, Y: 2048, X: 2048]
print(f"Shape: {img.shape}")
print(f"Pixel size: {img.physical_pixel_sizes}")

n_z = img.dims.Z
n_t = img.dims.T
plane_shape = (img.dims.Y, img.dims.X)
full_shape = (n_z,) + plane_shape

mem = estimate_memory(full_shape, dtype=str(img.dtype))
print(f"Full volume: {mem['size_gb']:.2f} GB | Fits in RAM: {mem['fits_in_ram']}")

# ── 2. CROP-FIRST: tune on one representative plane ──
mid_z = n_z // 2
# C=0 selects channel 0 — change to the channel you want to segment
test_plane = img.get_image_dask_data("YX", T=0, C=0, Z=mid_z).compute()

# Note: this uses Cellpose 3.x API. For 4.x, see segmentation.md.
from cellpose import models
model = models.Cellpose(model_type="cyto3", gpu=True)

for diameter in [20, 40, 60]:
    test_labels, _, _, _ = model.eval(test_plane, diameter=diameter, channels=[0, 0])
    print(f"  diameter={diameter}: {test_labels.max()} objects")

best_diameter = 40  # <- set after reviewing

# ── 3. PROCESS PLANE-BY-PLANE ──
# Pixel size from metadata — None means uncalibrated
pixel_size_um = img.physical_pixel_sizes.Y
if pixel_size_um is None:
    print("WARNING: No pixel size in metadata. Measurements will be in pixels.")
results = ResultsManager("analysis", "3d_planewise")
results.set_params(image=image_path, n_z=n_z, n_t=n_t,
                   plane_shape=str(plane_shape), diameter=best_diameter,
                   pixel_size_um=pixel_size_um or "uncalibrated")

all_measurements = []

for t in range(n_t):
    for z in range(n_z):
        # Load one plane at a time — only this plane is in RAM
        plane = img.get_image_dask_data("YX", T=t, C=0, Z=z).compute()

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
            props["timepoint"] = t
            if pixel_size_um is not None:
                props["area_um2"] = props["area"] * (pixel_size_um ** 2)
            all_measurements.append(props)

        if z % 10 == 0:
            results.log(f"T={t}, Z={z}/{n_z}: {stats['n_after']} objects")

# ── 4. EXPORT ──
combined = pd.concat(all_measurements, ignore_index=True)
results.save_csv(combined, "all_measurements.csv", step="04_measurements",
                 description=f"{len(combined)} objects across {n_z} planes, {n_t} timepoints")

# Summary: objects per plane
fig, ax = plt.subplots(figsize=(8, 4))
per_plane = combined.groupby("z_plane").size()
ax.plot(per_plane.index, per_plane.values)
ax.set_xlabel("Z plane")
ax.set_ylabel("Object count")
ax.set_title("Objects per plane")
results.save_figure(fig, "objects_per_plane.png", step="03_qc")

results.write_manifest()
print(f"\nDone: {len(combined)} objects across {n_z}Z x {n_t}T -> {results.run_dir}")
```

**Why BioIO + dask for large data:**
- `img.dask_data` returns a lazy 5D (TCZYX) dask array — nothing is loaded until
  `.compute()` is called. Only the requested slice hits RAM.
- `img.get_image_dask_data("YX", T=0, C=0, Z=5)` extracts exactly one plane as
  a 2D dask array. Call `.compute()` to materialize it as numpy.
- Works with CZI, LIF, ND2, OME-TIFF — BioIO handles the format details.
- Pixel sizes come from metadata: `img.physical_pixel_sizes.Y` — no manual calibration.
- **Fallback** if BioIO is not installed: use `tifffile.imread(path, key=z)` for
  multi-page TIFFs, or `zarr.open(path)[z]` for zarr-backed data.

**3D segmentation (when z-context matters):**
- **Cellpose 3D**: `model.eval(volume, do_3D=True, diameter=40)` — segments the
  full volume using 3D flow fields. Requires the volume to fit in RAM.
  For large volumes, process overlapping sub-volumes and stitch.
- **PlantSeg**: purpose-built for 3D cell segmentation in plant tissue and
  cleared samples. Uses 3D U-Net + graph partitioning.
- **2D-per-slice vs true 3D**: 2D-per-slice (this pipeline) is faster and uses
  less RAM, but loses z-continuity. True 3D gives connected objects but needs
  the full volume (or large overlapping chunks) in memory.

**Timelapse tracking:** After per-frame segmentation, use `btrack` or `trackpy`
to link objects across timepoints.
