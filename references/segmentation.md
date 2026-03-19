# Segmentation

How to go from a preprocessed image to a labeled mask where each object has a unique ID.

## Decision Tree

Pick the simplest approach that could work. Move to DL only if classical methods fail.

| Image type | Objects | Recommended approach |
|---|---|---|
| Fluorescence, nuclei, not touching | Round, well-separated | StarDist `2D_versatile_fluo` |
| Fluorescence, nuclei, touching | Round, clustered | Cellpose `nuclei` or threshold + watershed |
| Fluorescence, whole cells | Irregular shapes | Cellpose `cyto3` (3.x) or `cyto2` (2.x) |
| Brightfield / phase contrast | Cells | Cellpose `livecell` |
| H&E histology | Nuclei | StarDist `2D_versatile_he` |
| High contrast, non-touching | Any | Otsu threshold + connected components |
| Touching objects, clean signal | Round-ish | Threshold + distance transform + watershed |
| Nothing works with pretrained | — | Custom training (20-50 annotations for Cellpose, 50+ for nnUNetv2) |

---

## Classical Approaches

**Otsu thresholding**: `skimage.filters.threshold_otsu` → binary → `skimage.measure.label`. Works when histogram is bimodal and objects don't touch.

**Adaptive thresholding**: `skimage.filters.threshold_local(image, block_size=51)`. Use when illumination is uneven.

**Watershed for touching objects**: threshold → `ndi.distance_transform_edt` → `peak_local_max(distance, min_distance=10)` → `watershed(-distance, markers, mask=binary)`. Set `min_distance` to ~half the smallest expected object diameter.

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

Combined pipeline — each step is optional:

```python
from scipy.ndimage import binary_fill_holes
from skimage.measure import regionprops, label as relabel
from skimage.morphology import binary_closing, disk
from skimage.segmentation import clear_border

def postprocess_labels(labels, min_area=0, remove_border=False,
                       fill_holes=False, smooth_radius=0):
    result = labels.copy()
    if remove_border:
        result = clear_border(result)
    if fill_holes:
        filled = np.zeros_like(result)
        for i in range(1, result.max() + 1):
            filled[binary_fill_holes(result == i)] = i
        result = filled
    if smooth_radius > 0:
        smoothed = np.zeros_like(result)
        selem = disk(smooth_radius)
        for i in range(1, result.max() + 1):
            smoothed[binary_closing(result == i, selem)] = i
        result = smoothed
    if min_area > 0:
        for p in regionprops(result):
            if p.area < min_area:
                result[result == p.label] = 0
    return relabel(result > 0, connectivity=1)
```

---

## When Automated Segmentation Fails

If 2-3 parameter combinations haven't worked, stop tuning and escalate:

1. **Interactive annotation + fine-tuning**: 20-50 manual annotations → fine-tune. Tools: Cellpose GUI, napari labels layer, QuPath
2. **Search for published workflows**: papers with similar modality often describe their pipeline in methods/supplementary
3. **Ask the community at forum.image.sc**: primary forum for bioimage analysis, monitored by tool developers

## Generalization Warning

Don't over-tune on sample data. Tune on a diverse sample (different conditions, batches, density ranges). Test on held-out images. If performance drops, simplify — the parameters are overfit.
