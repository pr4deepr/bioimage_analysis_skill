# Measurements

## Common Measurements and Biological Meaning

### Morphology

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Area (µm²) | Object size | Cell size, growth state, cell cycle phase |
| Eccentricity (0-1) | Elongation | Migration phenotype, cytoskeletal changes |
| Solidity | Area / convex hull area | Boundary irregularity — blebbing, apoptosis |
| Form factor (4π×area/perimeter²) | Circularity | Low = protrusions, filopodia |
| Perimeter | Boundary length | Ruffling, membrane dynamics |

### Intensity

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Mean intensity | Average signal per pixel | Expression level of marker |
| Integrated intensity | Sum of all pixel values | Total signal (accounts for cell size) |
| Intensity SD | Variation within object | Punctate vs diffuse signal |
| Max intensity | Brightest pixel | Focal accumulation, aggregates |
| Intensity ratio (ch1/ch2) | Relative expression | Co-localization proxy, ratiometric reporters |

**Critical**: always clarify whether intensity is raw or background-subtracted. Raw comparisons across experiments are unreliable without normalization.

### Texture (GLCM / Haralick)
Useful for phenotypic profiling and classification. Difficult to interpret biologically in isolation — best as input to classifiers (random forest, etc.) rather than standalone metrics.

### Spatial

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Nearest-neighbor distance | Spacing between objects | Confluency, clustering behavior |
| Neighbor count within radius | Local density | Microenvironment, paracrine signaling range |
| XY centroid | Object position | Required for spatial statistics (Ripley's K, etc.) |

---

## Measurement Pitfalls

**Use `detect_measurement_pitfalls()` from `bioimage_utils.py`** before extracting
measurements. It programmatically checks for edge objects, saturation, missing
calibration, and merged objects:

```python
from bioimage_utils import detect_measurement_pitfalls
pitfalls = detect_measurement_pitfalls(labels, image, pixel_size_um=0.325)
for p in pitfalls:
    if p["detected"]:
        print(f"[{p['severity']}] {p['pitfall']}: {p['message']}")
        print(f"  Fix: {p['fix']}")
```

The function checks:
- **Edge objects** — objects touching the border have truncated area/shape
- **Saturation** — pixels at detector max underestimate intensity
- **Missing calibration** — area in pixels is meaningless for comparison
- **Background subtraction** — reminder to check for spatial heterogeneity
- **Photobleaching** (timelapse only) — intensity drops over time
- **Merged objects** — largest object >>10x median area suggests under-segmentation

Additional context for interpreting these pitfalls:

**Segmentation errors propagate into measurements.**
A merged pair has ~2x area, distorted eccentricity, averaged intensity. Always overlay masks on 5-10 representative images per condition before trusting bulk measurements.

**Background subtraction matters more than you think.**
If background is spatially heterogeneous (tissue sections, uneven illumination), use local background subtraction — measure intensity in a dilated annular region around each object with `skimage.segmentation.expand_labels`, then subtract.

---

## Choosing What to Measure

Use the biological question to drive measurement selection. Resist "measure everything" — focus on features that directly address the question.

For exploratory profiling (no specific hypothesis): extract a broad feature set, use PCA/UMAP or classification to find discriminating features, then report those.
