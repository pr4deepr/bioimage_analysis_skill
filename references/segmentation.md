# Segmentation

How to go from a preprocessed image to a labeled mask where each object has a unique ID.

## Segmentation Approaches

### Thresholding (Classical)

Convert a grayscale image to binary (object vs background) based on intensity.

**How it works**: pick an intensity cutoff — pixels above it are "object", below are
"background". Automated methods (Otsu, Li, Triangle, etc.) compute the cutoff from
the image histogram.

**When it works well**:
- High contrast between objects and background
- Objects don't touch each other
- Relatively uniform background intensity (or after illumination correction)

**When it fails**:
- Touching/overlapping objects get merged into one blob
- Low contrast or noisy images produce fragmented masks
- Brightfield / phase contrast images (halo artifacts confuse thresholding)

**Key parameters**:
- Threshold method: Otsu (good default for bimodal histograms), Li (minimizes cross-entropy,
  good for dim objects), Triangle (good for skewed histograms with few bright objects),
  Adaptive/local (handles uneven illumination by computing threshold per-region)
- Minimum object size: filter out small noise detections after thresholding

**Recommended tools**: scikit-image filters.threshold_otsu / threshold_li / threshold_local,
FIJI Image > Adjust > Threshold (interactive), scipy.ndimage.label for connected components.

> See: cookbook-segmentation.md § Otsu thresholding + connected components
> See: cookbook-segmentation.md § Adaptive thresholding

### Watershed

Separates touching objects by treating the intensity image like a topographic surface and
finding the "watershed lines" between intensity basins.

**How it works**: find seeds (local intensity minima or maxima, depending on convention),
then grow regions from seeds until they meet at boundaries.

**When it works well**:
- Touching round objects (nuclei) where thresholding alone merges them
- Combined with a distance transform on a binary mask: threshold first, compute distance
  from background, then watershed on the distance map

**When it fails**:
- Irregularly shaped objects (over-segments into fragments)
- Very dense clusters where seeds can't be reliably identified
- Objects with concavities (watershed splits at every concavity)

**Key parameters**:
- Seed detection: minimum distance between seeds controls over/under-segmentation
- Smoothing of the distance map before finding seeds (reduces over-segmentation)

**Recommended tools**: scikit-image segmentation.watershed, scipy.ndimage.distance_transform_edt,
FIJI Process > Binary > Watershed, MorphoLibJ (FIJI plugin for advanced morphological watershed).

> See: cookbook-segmentation.md § Threshold + distance transform + watershed

### Deep Learning Instance Segmentation

Neural networks trained to detect and separate individual objects, even when touching.

**How it works**: models learn object boundaries and shapes from training data. Inference
produces per-pixel predictions that are decoded into individual object masks.

**When it works well**:
- Touching, overlapping, or irregularly shaped objects
- Challenging modalities (brightfield, phase contrast)
- Large datasets where manual thresholding would need constant tuning
- When pretrained models exist for your object type

**When it fails**:
- Object type is very different from training data and no pretrained model fits
- Very few objects in the dataset (hard to train custom models)
- Extreme image artifacts that weren't in training data

**Available pretrained models and what they're good for**:

| Model | Best for | Notes |
|---|---|---|
| Cellpose `cyto2` / `cyto3` | Whole cells (fluorescence + brightfield) | Needs cytoplasm channel ± nuclear channel |
| Cellpose `nuclei` | Nuclei in fluorescence | Fast, works well on DAPI/Hoechst |
| Cellpose `livecell` | Cells in brightfield/phase contrast | Trained on diverse cell lines |
| StarDist `2D_versatile_fluo` | Nuclei in fluorescence | Very fast, assumes star-convex shapes |
| StarDist `2D_versatile_he` | Nuclei in H&E histology | |
| Mesmer / DeepCell | Nuclear + whole-cell in multiplexed imaging | Purpose-built for spatial proteomics |
| nnUNetv2 | Anything, with custom training data | No pretrained models — you train on your data |

**Key parameters** (vary by tool):
- Cellpose: `diameter` (expected object size in pixels — critical to set correctly),
  `flow_threshold` (confidence cutoff), `cellprob_threshold` (how aggressive to detect)
- StarDist: `prob_thresh` (detection confidence), `nms_thresh` (overlap handling)

**When to train a custom model**:
- Pretrained models produce clearly wrong results after parameter tuning
- Your objects have unusual morphology not represented in training data
- You need very high accuracy for publication
- Budget: ~20-50 annotated images for Cellpose fine-tuning, 50+ for nnUNetv2

> See: cookbook-segmentation.md § Deep Learning — Cellpose
> See: cookbook-segmentation.md § Deep Learning — StarDist

---

## Post-Processing

After initial segmentation, clean up the mask before measurement.

### Filtering Small Objects
Remove objects below a minimum area threshold. These are usually debris, noise, or
segmentation fragments. Set the threshold based on the expected minimum cell size for
your cell type.

### Filtering by Shape
Remove objects with extreme shape metrics (very high eccentricity, very low solidity).
These are typically segmentation artifacts, not real cells.

### Removing Edge Objects
Objects touching the image border have incomplete measurements. Remove them unless you
only need counts (in which case, keep them for counting but exclude from shape/intensity
measurements).

### Filling Holes
Binary masks sometimes have holes inside objects (from uneven staining or thresholding
artifacts). Fill them unless the holes are biologically meaningful (e.g., donut-shaped
cells, nuclear rings).

### Smoothing Boundaries
Jagged mask boundaries produce noisy perimeter and shape measurements. A light
morphological closing (dilate then erode, kernel size 1-3) smooths boundaries without
significantly changing area.

> See: cookbook-segmentation.md § Post-Processing

---

## Choosing Between Approaches

Use this decision flow (same as in SKILL.md, expanded here with more detail):

**Start with the simplest approach that could work.** Try classical thresholding first
if the images look clean. Move to DL only if thresholding fails. This saves time and
keeps the pipeline simpler and more interpretable.

**Evaluate on a representative sample, not one image.** A threshold that works on one
image may fail on others with different staining intensity or density. Test on 10-20
images spanning the range of conditions in your dataset.

**Pretrained DL models are not magic.** They can fail on data that differs significantly
from their training distribution. Always visually verify results rather than assuming
a DL model is correct.

**Hybrid approaches are fine.** For example: use StarDist for nuclear segmentation, then
expand to whole-cell using classical watershed on a membrane channel. Mix methods based
on what works for each step.

---

## Generalization: Don't Over-Tune on Sample Data

A pipeline that's been tweaked to perfection on 3 sample images may fail on the rest of
the dataset. This is especially common when:
- Sample images are from one condition but the dataset spans multiple conditions
- The "best" images were chosen for tuning (clean, high-contrast) but the dataset includes
  harder cases (out-of-focus, low-density, unusual morphology)
- Parameters were adjusted iteratively until the sample looked perfect, overfitting to
  those specific images

**Best practice**: tune on a small diverse sample (images from different conditions,
batches, density ranges). After tuning, test on a held-out set the pipeline hasn't seen.
If performance drops, the parameters are overfit — simplify.

---

## When Automated Segmentation Isn't Working

If 2-3 parameter combinations haven't produced acceptable results, stop tuning and escalate:

**Interactive annotation + fine-tuning**: have the user manually annotate 20-50 objects,
then fine-tune the model on their data. This is almost always more productive than
continued parameter tweaking. Tools for annotation:
- Cellpose GUI (built-in annotation and retraining workflow)
- napari with labels layer (freehand drawing, good for irregular shapes)
- QuPath (tissue-level annotation, good for histology)

**Search for published workflows**: many papers describe their segmentation pipeline in
the methods or supplementary material. Search for papers with similar modality and
biological question. Ask the user if they have reference publications.

**Ask the community at forum.image.sc**: this is the primary forum for bioimage analysis,
actively monitored by developers of CellProfiler, Cellpose, StarDist, napari, QuPath, and
other tools. Users can post example images and get expert advice on approach selection and
parameter tuning. Suggest this when the problem is genuinely difficult or unusual.
