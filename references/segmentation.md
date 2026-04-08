# Segmentation

How to go from a preprocessed image to a labeled mask where each object has a unique ID.

## Decision Tree

Pick the simplest approach that could work. Move to DL only if classical methods fail.

**Use `pick_segmentation_tool()` from `bioimage_utils.py`** to get a concrete recommendation:

```python
from bioimage_utils import pick_segmentation_tool
result = pick_segmentation_tool("nuclei", modality="fluorescence", objects_touching=True)
# Returns: {"tool": "stardist", "model": "2D_versatile_fluo", "fallback_tool": "cellpose", ...}
```

Then **validate the model** for the installed version:

```python
from bioimage_utils import validate_model_for_version
check = validate_model_for_version("cellpose", "cyto3")
# Returns: {"valid": True/False, "message": "...", "suggestion": "cyto2"}
```

Reference table (the function encodes this logic):

| Image type | Objects | Recommended approach |
|---|---|---|
| Fluorescence, nuclei, not touching | Round, well-separated | StarDist `2D_versatile_fluo` |
| Fluorescence, nuclei, touching | Round, clustered | StarDist `2D_versatile_fluo`, fallback Cellpose `nuclei` |
| Fluorescence, whole cells | Irregular shapes | Cellpose `cyto3` (3.x) or `cyto2` (2.x) |
| Brightfield / phase contrast | Cells | Cellpose `livecell` |
| H&E histology | Nuclei | StarDist `2D_versatile_he` |
| High contrast, non-touching | Any | Otsu threshold + connected components |
| Touching objects, clean signal | Round-ish | Threshold + distance transform + watershed |
| Nothing works with pretrained | — | Custom training (20-50 annotations for Cellpose, 50+ for nnUNetv2) |
| Functional timelapse (calcium, voltage, pH) | Cells visible in frames | Cellpose/StarDist on max/mean time projection |
| Functional timelapse, dim cells | Only visible through activity | Activity map + percentile threshold + watershed |

**Functional timelapse data** (calcium imaging, voltage imaging, pH reporters, etc.): segmentation approach depends on cell visibility. If cells are visible in individual frames, use Cellpose/StarDist on a max or mean time projection — standard segmentation works. If cells are dim and only visible through their temporal activity, standard approaches fail — use `compute_activity_map()` from `bioimage_utils.py` to create a brightness-independent activity image, then segment that with percentile thresholding + watershed. If there is frame-to-frame motion, register the stack first. See `timeseries-functional.md` for the full workflow.

---

## Classical Approaches

**Otsu thresholding**: `skimage.filters.threshold_otsu` → binary → `skimage.measure.label`. Works when histogram is bimodal and objects don't touch.

**Otsu limitation**: Otsu assumes a bimodal intensity distribution (foreground vs background). It fails when foreground is a small fraction of the image — sparse colonies, rare cell types, functional imaging data where only a few cells are active. In these cases, Otsu sets the threshold too high (foreground peak is swamped by background). Use percentile-based thresholds (`np.percentile(image[image > 0], 65)`) or adaptive methods instead.

**Adaptive thresholding**: `skimage.filters.threshold_local(image, block_size=51)`. Use when illumination is uneven.

**Watershed for touching objects**:

```python
from skimage.filters import threshold_otsu
from skimage.measure import label
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from scipy import ndimage as ndi
import numpy as np

# 1. Threshold
thresh = threshold_otsu(image)
binary = image > thresh

# 2. Distance transform — each pixel = distance to nearest background
distance = ndi.distance_transform_edt(binary)

# 3. Find seeds (local maxima = cell centers in distance map)
# min_distance: ~half the smallest expected object diameter
coords = peak_local_max(distance, min_distance=10, labels=binary)
seed_mask = np.zeros(distance.shape, dtype=bool)
seed_mask[tuple(coords.T)] = True
markers = label(seed_mask)

# 4. Watershed — floods from seeds, -distance so it floods valleys first
labels = watershed(-distance, markers, mask=binary)
```

Set `min_distance` to ~half the smallest expected object diameter. If over-segmenting, increase it.

---

## Deep Learning — Cellpose

### Cellpose >= 3.0

```python
from cellpose import models

model = models.Cellpose(model_type="cyto3", gpu=True)
# channels: [cytoplasm, nucleus]. [0,0] for grayscale
# diameter: None = auto-estimate (recommended first pass)
# flow_threshold: 0.1 (strict) to 1.0 (permissive), default 0.4
# cellprob_threshold: -6.0 (include dim) to 6.0 (only bright), default 0.0
masks, flows, styles, diams = model.eval(
    image, diameter=None, channels=[0, 0],
    flow_threshold=0.4, cellprob_threshold=0.0,
)
```

### Cellpose 2.x

Same API but **no `cyto3`**. Use `cyto2` (recommended) or `cyto` or `nuclei`.

```python
from cellpose import models
model = models.Cellpose(model_type="cyto2", gpu=True)
masks, flows, styles, diams = model.eval(
    image, diameter=None, channels=[0, 0],
    flow_threshold=0.4, cellprob_threshold=0.0,
)
```

### Cellpose >= 4.0

**Breaking changes from 3.x**: `models.Cellpose` is removed. `diameter` and
`channels` are ignored (Cellpose-SAM is size- and channel-order invariant).
Weights are bfloat16 by default (~50% smaller, ~40% faster).

```python
from cellpose import models

model = models.CellposeModel(model_type="cyto3", gpu=True)
# No diameter or channels needed — Cellpose 4 handles this automatically
# flow_threshold and cellprob_threshold still work
masks, flows, styles = model.eval(
    image,
    flow_threshold=0.4, cellprob_threshold=0.0,
)
# Note: styles is a zero vector in 4.x (kept for API compat)
```

### Custom Cellpose model

```python
from cellpose import models
model = models.CellposeModel(pretrained_model="path/to/model", gpu=True)
masks, flows, styles = model.eval(
    image, diameter=None, channels=[0, 0],
)
```

---

## Deep Learning — StarDist

```python
from stardist.models import StarDist2D
from csbdeep.utils import normalize

image_norm = normalize(image, pmin=1, pmax=99.8)
model = StarDist2D.from_pretrained("2D_versatile_fluo")
# prob_thresh: higher = fewer detections (default ~0.5)
# nms_thresh: lower = merge more overlapping detections (default ~0.3)
labels, details = model.predict_instances(
    image_norm, prob_thresh=0.5, nms_thresh=0.3,
)
```

Custom model: `StarDist2D(None, name="my_model", basedir="path/to/models")`.

---

## Post-Processing

**Use `clean_labels()` from `bioimage_utils.py`** for standard post-processing
(border removal + small object filtering):

```python
from bioimage_utils import clean_labels
labels, stats = clean_labels(labels, remove_border=True, min_area_fraction=0.3)
# stats: {"n_before": 150, "n_after": 120, "n_border_removed": 15, "n_small_removed": 15}
```

For additional post-processing (hole filling, boundary smoothing), add these
steps after `clean_labels()`:

```python
from scipy.ndimage import binary_fill_holes
from skimage.morphology import binary_closing, disk
from skimage.measure import label as relabel
import numpy as np

# Fill holes inside objects (skip if holes are biologically meaningful)
filled = np.zeros_like(labels)
for i in range(1, labels.max() + 1):
    filled[binary_fill_holes(labels == i)] = i
labels = filled

# Smooth jagged boundaries (kernel 1-3)
smoothed = np.zeros_like(labels)
selem = disk(1)
for i in range(1, labels.max() + 1):
    smoothed[binary_closing(labels == i, selem)] = i
labels = relabel(smoothed > 0, connectivity=1)
```

---

## When Automated Segmentation Fails

If 2-3 parameter combinations haven't worked, stop tuning and escalate:

1. **Interactive annotation + fine-tuning**: 20-50 manual annotations → fine-tune. Tools: Cellpose GUI, napari labels layer, QuPath
2. **Search for published workflows**: papers with similar modality often describe their pipeline in methods/supplementary
3. **Ask the community at forum.image.sc**: primary forum for bioimage analysis, monitored by tool developers

## Generalization Warning

Don't over-tune on sample data. Tune on a diverse sample (different conditions, batches, density ranges). Test on held-out images. If performance drops, simplify — the parameters are overfit.

---

## Large Data

When images are too large to load into RAM — whole-slide histology, OPAL multiplex,
CometAssay mosaics, large 3D volumes, long timelapses.

**First: check if it fits.** Use `estimate_memory()` from `bioimage_utils.py`:

```python
from bioimage_utils import estimate_memory
mem = estimate_memory((50000, 50000), dtype="uint16")
# {"size_gb": 4.66, "peak_gb": 13.97, "fits_in_ram": False, "warning": "..."}
```

**Always: tune on a crop first.** Never run full-dataset segmentation without
testing parameters on a small region. Use BioIO's dask backend to read a crop
without loading the full image:

```python
from bioio import BioImage

img = BioImage("slide.czi")  # works with CZI, LIF, ND2, OME-TIFF, TIFF
print(f"Shape: {img.dims}")  # Dimensions [T: 1, C: 3, Z: 1, Y: 40000, X: 50000]
print(f"Pixel size: {img.physical_pixel_sizes}")  # auto from metadata

# Lazy dask array — nothing loaded yet
lazy = img.get_image_dask_data("YX", T=0, C=0, Z=0)
# Only the crop is loaded into RAM
crop = lazy[1000:1512, 1000:1512].compute()
# Tune parameters on crop, then proceed to full processing
```

If BioIO is not installed, fall back to tifffile:
```python
import tifffile
with tifffile.TiffFile("slide.tif") as tif:
    shape = (tif.pages[0].imagelength, tif.pages[0].imagewidth)
crop = tifffile.imread("slide.tif", key=0)[1000:1512, 1000:1512]
```

### When to use each strategy

| Scenario | Strategy | Pipeline |
|---|---|---|
| Single large 2D (histology, OPAL, mosaic) | Tiled processing with overlap | Pipeline 4 in cookbook-pipeline.md |
| 3D volume (z-stack, light-sheet) | Plane-by-plane 2D segmentation | Pipeline 5 in cookbook-pipeline.md |
| 3D where z-context matters | Cellpose 3D or PlantSeg on sub-volumes | See Pipeline 5 notes |
| Timelapse (100s of timepoints) | Per-timepoint processing | Pipeline 5 variant |
| Hundreds of standard-size images | Batch processing | Pipeline 3 in cookbook-pipeline.md |

### BioIO + dask for lazy loading

BioIO returns dask arrays natively — the best approach for most microscopy formats:

```python
from bioio import BioImage

img = BioImage("data.czi")          # CZI, LIF, ND2, OME-TIFF, TIFF
lazy = img.dask_data                 # lazy 5D (TCZYX) dask array
plane = img.get_image_dask_data("YX", T=0, C=0, Z=5).compute()  # one plane → numpy
```

BioIO handles format-specific details (chunking, metadata, dimension ordering)
and provides pixel sizes from metadata via `img.physical_pixel_sizes`.

For raw zarr without BioIO:
```python
import dask.array as da, zarr
volume = da.from_zarr(zarr.open("data.zarr", "r"))  # lazy
plane = volume[42].compute()
```

### Key considerations

- **Tile overlap** must be larger than the biggest expected object diameter,
  otherwise objects at tile edges get split
- **Stitching**: use centroid-in-inner-region to avoid duplicate objects at
  tile boundaries (see Pipeline 4)
- **3D segmentation**: 2D-per-slice is faster and uses less RAM but loses
  z-continuity. True 3D (Cellpose `do_3D=True`, PlantSeg) gives connected
  objects but needs the full volume or large overlapping sub-volumes in memory
- **Timelapse tracking**: after per-frame segmentation, use `btrack` or
  `trackpy` to link objects across timepoints
