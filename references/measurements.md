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

Flag these proactively — users rarely catch them on their own.

**Segmentation errors propagate into measurements.**
A merged pair has ~2× area, distorted eccentricity, averaged intensity. Always overlay masks on 5-10 representative images per condition before trusting bulk measurements.

**Background subtraction matters more than you think.**
If background is spatially heterogeneous (tissue sections, uneven illumination), use local background subtraction — measure intensity in a dilated annular region around each object with `skimage.segmentation.expand_labels`, then subtract.

**Edge objects have truncated measurements.**
Cells touching the image border are partially cropped — area, perimeter, and shape are wrong. Filter with `skimage.segmentation.clear_border` or check if mask pixels touch row 0/col 0/max.

**Photobleaching in timelapse.**
Intensity drops over time. Normalize per-frame (divide by median background intensity) or you'll see a false downward trend.

**Pixel size calibration.**
Always confirm µm/pixel from metadata before reporting. Area in pixels is meaningless for cross-experiment comparison. If metadata missing, measure a known structure.

**Saturation / clipping.**
If brightest signal hits detector ceiling (255 in 8-bit, 4095 in 12-bit), intensity is underestimated. Check histograms — spike at max value = saturation.

---

## Choosing What to Measure

Use the biological question to drive measurement selection. Resist "measure everything" — focus on features that directly address the question.

For exploratory profiling (no specific hypothesis): extract a broad feature set, use PCA/UMAP or classification to find discriminating features, then report those.
