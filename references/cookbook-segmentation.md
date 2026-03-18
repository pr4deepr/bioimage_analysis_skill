# Segmentation Cookbook

Ready-to-use segmentation patterns for microscopy images. Each block includes complete imports, describes expected inputs/outputs, and annotates key parameters. Classical methods appear first (simplest), followed by deep-learning approaches.

---

## Classical Approaches

### Otsu thresholding + connected components

**When to use:** Single-channel images with clear intensity separation between foreground and background, and objects that do not touch.

```python
import numpy as np
from skimage.filters import threshold_otsu
from skimage.measure import label

# Input: 2D grayscale image as numpy array, dtype float or uint8/uint16
# image.shape == (H, W)

# threshold_otsu computes a global threshold that minimizes intra-class
# intensity variance. Works well when the histogram is bimodal (two peaks).
thresh = threshold_otsu(image)
binary = image > thresh  # True where foreground

# label assigns a unique integer to each connected component (object).
# connectivity=1 means 4-connected (only horizontal/vertical neighbors).
# Use connectivity=2 for 8-connected (includes diagonal neighbors).
labels = label(binary, connectivity=1)

# Output: labels — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
print(f"Found {labels.max()} objects")
```

### Adaptive thresholding (uneven illumination)

**When to use:** Images with uneven illumination or intensity gradients across the field of view, where a single global threshold fails.

```python
import numpy as np
from skimage.filters import threshold_local
from skimage.measure import label

# Input: 2D grayscale image as numpy array, dtype float or uint8/uint16
# image.shape == (H, W)

# block_size: size of the local neighborhood (in pixels) used to compute
# the threshold at each pixel. Must be odd. Larger values tolerate slower
# illumination gradients; smaller values capture finer local variation.
# A good starting point is ~10-15% of the image's shorter dimension.
block_size = 51

# offset: subtracted from the local mean. Positive values make the
# threshold stricter (fewer foreground pixels). Tune if you get too
# much or too little foreground.
offset = 0

local_thresh = threshold_local(image, block_size=block_size, offset=offset)
binary = image > local_thresh

labels = label(binary, connectivity=1)

# Output: labels — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
print(f"Found {labels.max()} objects")
```

### Threshold + distance transform + watershed (touching objects)

**When to use:** Objects that touch or partially overlap, such as confluent cells or clustered nuclei. Watershed splits merged blobs using intensity "valleys" between object centers.

```python
import numpy as np
from skimage.filters import threshold_otsu
from skimage.morphology import remove_small_objects
from skimage.segmentation import watershed
from skimage.feature import peak_local_max
from scipy import ndimage as ndi

# Input: 2D grayscale image as numpy array, dtype float or uint8/uint16
# image.shape == (H, W)

# Step 1 — create binary mask
thresh = threshold_otsu(image)
binary = image > thresh

# Step 2 — distance transform: each foreground pixel gets a value equal
# to its distance from the nearest background pixel. Object centers will
# have the highest values.
distance = ndi.distance_transform_edt(binary)

# Step 3 — find markers (seeds) for watershed.
# min_distance: minimum allowed distance (in pixels) between peaks.
# Set this to roughly half the smallest expected object diameter to
# prevent over-segmentation.
min_distance = 10
coords = peak_local_max(distance, min_distance=min_distance, labels=binary)

# Build a marker image: each seed gets a unique integer label
mask = np.zeros(distance.shape, dtype=bool)
mask[tuple(coords.T)] = True
markers = ndi.label(mask)[0]

# Step 4 — watershed. Negative distance is used so that "valleys"
# (object boundaries) become ridges that the watershed respects.
labels = watershed(-distance, markers, mask=binary)

# Output: labels — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
print(f"Found {labels.max()} objects")
```

---

## Deep Learning — Cellpose

### Cellpose >= 3.0 (cyto2, cyto3, nuclei)

**When to use:** General cell or nucleus segmentation when classical methods fail — Cellpose handles varied morphologies, touching objects, and inconsistent contrast. Version 3.0+ adds the `cyto3` model and a revised API.

```python
# Cellpose >= 3.0
import numpy as np
from cellpose import models

# Input: 2D grayscale or multichannel image as numpy array
# image.shape == (H, W) for grayscale or (H, W, C) for multichannel

# model_type choices:
#   "cyto3"  — newest general cell model (Cellpose 3.0+), best default choice
#   "cyto2"  — previous-generation cell model, still good
#   "nuclei" — optimized for round, compact nuclei
model = models.Cellpose(model_type="cyto3", gpu=True)

# channels: [cytoplasm_channel, nucleus_channel]
#   [0, 0] — grayscale (single-channel), auto-detect
#   [1, 2] — channel 1 is cytoplasm (green), channel 2 is nucleus (blue)
#   [2, 3] — channel 2 is cytoplasm, channel 3 is nucleus (red)
#   [0, 2] — no cytoplasm channel, nucleus is channel 2
channels = [0, 0]

# diameter: expected object diameter in pixels.
#   None — let Cellpose auto-estimate (recommended first pass)
#   30   — override with a known value; speeds up and can improve accuracy
# flow_threshold: maximum allowed error of the flow field (default 0.4).
#   Lower values reject more borderline objects, giving cleaner but fewer masks.
#   Range: 0.1 (strict) to 1.0 (permissive)
# cellprob_threshold: pixel probability threshold for foreground (default 0.0).
#   Higher values shrink masks (only high-confidence pixels kept).
#   Range: -6.0 (include dim pixels) to 6.0 (only bright/confident pixels)
masks, flows, styles, diams = model.eval(
    image,
    diameter=None,             # auto-estimate on first run
    channels=channels,
    flow_threshold=0.4,        # default; increase if masks look fragmented
    cellprob_threshold=0.0,    # default; increase to shrink masks
)

# Output: masks — int32 array, shape (H, W)
#   0 = background, 1..N = individual cells
print(f"Found {masks.max()} objects, estimated diameter: {diams:.1f} px")
```

### Cellpose 2.x (cyto, cyto2, nuclei)

**When to use:** When you are on Cellpose 2.x (pip install cellpose < 3). The API is nearly identical but `cyto3` is not available and channel handling differs slightly.

```python
# Cellpose 2.x
import numpy as np
from cellpose import models

# Input: 2D grayscale or multichannel image as numpy array
# image.shape == (H, W) for grayscale or (H, W, C) for multichannel

# model_type choices for Cellpose 2.x:
#   "cyto"   — original cytoplasm model
#   "cyto2"  — improved cytoplasm model (recommended)
#   "nuclei" — nuclear segmentation
model = models.Cellpose(model_type="cyto2", gpu=True)

# channels: same convention as 3.0 — [cytoplasm_channel, nucleus_channel]
#   [0, 0] for grayscale
channels = [0, 0]

# diameter: expected object diameter in pixels.
#   None — auto-estimate (uses built-in size model)
# flow_threshold: max flow error (default 0.4).
#   Lower = stricter, fewer masks. Higher = more permissive.
# cellprob_threshold: foreground probability cutoff (default 0.0).
#   Increase to shrink masks; decrease to grow them.
masks, flows, styles, diams = model.eval(
    image,
    diameter=None,
    channels=channels,
    flow_threshold=0.4,
    cellprob_threshold=0.0,
)

# Output: masks — int32 array, shape (H, W)
#   0 = background, 1..N = individual cells
print(f"Found {masks.max()} objects, estimated diameter: {diams:.1f} px")
```

### Cellpose with custom model

**When to use:** When you have trained a Cellpose model on your own data (e.g., a specific cell type or staining protocol) and want to apply it.

```python
# Cellpose >= 3.0 (custom model loading also works in 2.x with same API)
import numpy as np
from cellpose import models

# Input: 2D image as numpy array, shape (H, W) or (H, W, C)

# Provide the path to your custom-trained Cellpose model file.
# This was produced by cellpose training (CLI or GUI).
custom_model_path = "path/to/your_custom_model"

model = models.CellposeModel(pretrained_model=custom_model_path, gpu=True)

channels = [0, 0]  # adjust to match your training data channel layout

# diameter: use the diameter your model was trained at, or None to auto-detect.
# flow_threshold / cellprob_threshold: same meaning as built-in models.
#   Start with defaults, then tune if masks are over- or under-segmented.
masks, flows, styles = model.eval(
    image,
    diameter=None,
    channels=channels,
    flow_threshold=0.4,
    cellprob_threshold=0.0,
)

# Output: masks — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
print(f"Found {masks.max()} objects")
```

---

## Deep Learning — StarDist

### StarDist (2D_versatile_fluo)

**When to use:** Fluorescence images of round or star-convex objects (nuclei, spheroids). StarDist is fast and works well when object shapes are roughly convex.

```python
# StarDist 0.8+
import numpy as np
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# Input: 2D grayscale image as numpy array, dtype float or uint8/uint16
# image.shape == (H, W)

# normalize: rescale intensities to [0, 1] using percentile clipping.
# pmin/pmax: lower/upper percentile for clipping.
#   (1, 99.8) is a good default; increase pmin or decrease pmax if
#   there are bright outliers or dim background noise.
image_norm = normalize(image, pmin=1, pmax=99.8)

# 2D_versatile_fluo: pretrained on a broad mix of fluorescence images.
# Other built-in options: "2D_versatile_he" for H&E histology.
model = StarDist2D.from_pretrained("2D_versatile_fluo")

# prob_thresh: minimum object probability to accept a detection (default ~0.5).
#   Lower = more detections (may include false positives).
#   Higher = fewer detections (only high-confidence objects).
# nms_thresh: non-maximum suppression IoU threshold (default ~0.3).
#   Controls how much overlap is tolerated before merging.
#   Lower = merge more aggressively (fewer overlapping objects).
#   Higher = allow more overlap (keep closely packed objects separate).
labels, details = model.predict_instances(
    image_norm,
    prob_thresh=0.5,   # increase to reject faint/uncertain detections
    nms_thresh=0.3,    # decrease to merge highly overlapping detections
)

# Output: labels — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
# details — dict with 'coord', 'points', 'prob' for each detected object
print(f"Found {labels.max()} objects")
```

### StarDist with custom model

**When to use:** When you have trained a StarDist model on your own data for improved accuracy on a specific tissue or cell type.

```python
# StarDist 0.8+ (custom model)
import numpy as np
from stardist.models import StarDist2D
from csbdeep.utils import normalize

# Input: 2D grayscale image as numpy array
# image.shape == (H, W)

image_norm = normalize(image, pmin=1, pmax=99.8)

# Load a custom model from a local directory.
# The directory must contain the model files produced by StarDist training
# (weights, config, thresholds).
model = StarDist2D(None, name="my_stardist_model", basedir="path/to/models")

# prob_thresh / nms_thresh: start with the optimized thresholds stored
# in the model directory (model.thresholds). Override here only if you
# need to tune detection sensitivity after training.
labels, details = model.predict_instances(
    image_norm,
    prob_thresh=None,  # None = use model's optimized threshold
    nms_thresh=None,   # None = use model's optimized threshold
)

# Output: labels — int32 array, shape (H, W)
#   0 = background, 1..N = individual objects
print(f"Found {labels.max()} objects")
```

---

## Post-Processing

Each step below works independently on a label image. They can be combined in any order using the pipeline function at the end.

### Filter small objects by area

**When to use:** Remove noise, debris, or partial cells that are too small to be real objects.

```python
import numpy as np
from skimage.measure import regionprops

# Input: labels — int32 array, shape (H, W), 0 = background, 1..N = objects
# Output: filtered — same format with small objects set to 0, then relabeled

def filter_small_objects(labels, min_area=100):
    """Remove objects with fewer than min_area pixels.

    Parameters
    ----------
    labels : np.ndarray
        Label image (0 = background).
    min_area : int
        Minimum object area in pixels. Objects smaller than this are removed.
        Set based on expected minimum real object size in your images.
    """
    filtered = labels.copy()
    for region in regionprops(labels):
        if region.area < min_area:
            filtered[filtered == region.label] = 0
    # Relabel so IDs are consecutive 1..N
    from skimage.measure import label as relabel
    filtered = relabel(filtered > 0, connectivity=1)
    return filtered
```

### Remove edge-touching objects

**When to use:** Exclude incomplete objects at image borders that would bias measurements (area, shape, intensity).

```python
import numpy as np
from skimage.segmentation import clear_border
from skimage.measure import label as relabel

# Input: labels — int32 array, shape (H, W), 0 = background, 1..N = objects
# Output: cleaned — same format with border-touching objects removed

def remove_edge_objects(labels):
    """Remove objects that touch any edge of the image.

    Uses skimage.segmentation.clear_border which sets any labeled
    object touching row 0, row -1, col 0, or col -1 to 0.
    """
    cleaned = clear_border(labels)
    # Relabel so IDs are consecutive
    cleaned = relabel(cleaned > 0, connectivity=1)
    return cleaned
```

### Fill holes

**When to use:** Objects with internal holes (e.g., ring-shaped fluorescence in cytoplasm stains) that should be solid for accurate area measurement.

```python
import numpy as np
from scipy.ndimage import binary_fill_holes
from skimage.measure import label as relabel

# Input: labels — int32 array, shape (H, W), 0 = background, 1..N = objects
# Output: filled — same format with holes inside each object filled

def fill_label_holes(labels):
    """Fill holes inside each labeled object.

    Processes each object independently so that gaps between
    objects are preserved (only internal holes are filled).
    """
    filled = np.zeros_like(labels)
    for obj_id in range(1, labels.max() + 1):
        obj_mask = labels == obj_id
        obj_filled = binary_fill_holes(obj_mask)
        filled[obj_filled] = obj_id
    return filled
```

### Smooth boundaries (morphological closing)

**When to use:** Rough or jagged object boundaries that you want to smooth, e.g., after thresholding noisy images.

```python
import numpy as np
from skimage.morphology import binary_closing, disk
from skimage.measure import label as relabel

# Input: labels — int32 array, shape (H, W), 0 = background, 1..N = objects
# Output: smoothed — same format with smoothed boundaries

def smooth_boundaries(labels, radius=2):
    """Smooth object boundaries using morphological closing.

    Parameters
    ----------
    labels : np.ndarray
        Label image (0 = background).
    radius : int
        Radius of the disk structuring element in pixels.
        Larger radius = more smoothing but may merge nearby objects.
        Start with 1-2 for subtle smoothing.
    """
    smoothed = np.zeros_like(labels)
    selem = disk(radius)
    for obj_id in range(1, labels.max() + 1):
        obj_mask = labels == obj_id
        obj_closed = binary_closing(obj_mask, selem)
        smoothed[obj_closed] = obj_id
    # Relabel in case closing merged objects or created artifacts
    smoothed = relabel(smoothed > 0, connectivity=1)
    return smoothed
```

### Combined post-processing pipeline

**When to use:** Apply multiple post-processing steps in a single call. Each step is optional and controlled by its parameter.

```python
import numpy as np
from scipy.ndimage import binary_fill_holes
from skimage.measure import regionprops, label as relabel
from skimage.morphology import binary_closing, disk
from skimage.segmentation import clear_border

# Input: labels — int32 array, shape (H, W), 0 = background, 1..N = objects
# Output: processed — same format, cleaned up

def postprocess_labels(
    labels,
    min_area=0,
    remove_border=False,
    fill_holes=False,
    smooth_radius=0,
):
    """Combined post-processing pipeline for label images.

    Parameters
    ----------
    labels : np.ndarray
        Label image (0 = background).
    min_area : int
        Remove objects with fewer than this many pixels. 0 = skip.
    remove_border : bool
        If True, remove objects touching the image border.
    fill_holes : bool
        If True, fill holes inside each object.
    smooth_radius : int
        Radius for morphological closing to smooth boundaries. 0 = skip.

    Returns
    -------
    np.ndarray
        Cleaned label image with consecutive integer labels.
    """
    result = labels.copy()

    # Step 1 — Remove border-touching objects
    if remove_border:
        result = clear_border(result)

    # Step 2 — Fill holes inside objects
    if fill_holes:
        filled = np.zeros_like(result)
        for obj_id in range(1, result.max() + 1):
            obj_mask = result == obj_id
            obj_filled = binary_fill_holes(obj_mask)
            filled[obj_filled] = obj_id
        result = filled

    # Step 3 — Smooth boundaries
    if smooth_radius > 0:
        smoothed = np.zeros_like(result)
        selem = disk(smooth_radius)
        for obj_id in range(1, result.max() + 1):
            obj_mask = result == obj_id
            obj_closed = binary_closing(obj_mask, selem)
            smoothed[obj_closed] = obj_id
        result = smoothed

    # Step 4 — Filter small objects (last, so smoothing/filling are counted)
    if min_area > 0:
        for region in regionprops(result):
            if region.area < min_area:
                result[result == region.label] = 0

    # Final relabel so IDs are consecutive 1..N
    result = relabel(result > 0, connectivity=1)
    return result


# Example usage:
# labels = postprocess_labels(
#     raw_labels,
#     min_area=200,          # remove objects < 200 px
#     remove_border=True,    # drop edge-touching objects
#     fill_holes=True,       # fill internal holes
#     smooth_radius=2,       # gentle boundary smoothing
# )
```
