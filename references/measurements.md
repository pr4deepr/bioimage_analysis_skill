# Measurement Guide

Reference for selecting and interpreting measurements after segmentation.

## Common Measurements and Biological Meaning

### Morphology

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Area | Object size in µm² (or pixels) | Cell size, growth state, cell cycle phase |
| Eccentricity / aspect ratio | Elongation (0 = circle, 1 = line) | Migration phenotype, cytoskeletal changes |
| Solidity | Area / convex hull area | Boundary irregularity — blebbing, apoptosis |
| Form factor (4π × area / perimeter²) | Circularity (1 = perfect circle) | Low values suggest protrusions, filopodia |
| Perimeter | Boundary length | Ruffling, membrane dynamics |
| Compactness | Perimeter² / (4π × area) | Inverse of form factor; high = irregular |

### Intensity

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Mean intensity | Average signal per pixel | Expression level of marker |
| Integrated intensity | Sum of all pixel values | Total signal (accounts for cell size) |
| Intensity SD | Variation within object | Signal heterogeneity — punctate vs diffuse |
| Max intensity | Brightest pixel | Focal accumulation, aggregates |
| Intensity ratio (ch1/ch2) | Relative expression | Co-localization proxy, ratiometric reporters |

**Critical**: always clarify whether intensity is raw or background-subtracted. Raw intensity
comparisons across experiments are unreliable without normalization.

### Texture (Haralick / GLCM)

Texture features quantify spatial patterns of pixel intensity within objects.

- Useful for phenotypic profiling and morphological classification
- Difficult to interpret biologically in isolation
- Best used as input to classifiers (e.g., random forest on texture features to distinguish
  cell states) rather than reported as standalone metrics
- Common features: contrast, correlation, entropy, homogeneity

### Spatial / Neighborhood

| Measurement | What it captures | Biological interpretation |
|---|---|---|
| Nearest-neighbor distance | Spacing between objects | Confluency, clustering behavior |
| Neighbor count within radius | Local density | Microenvironment, paracrine signaling range |
| XY centroid coordinates | Object position | Required for spatial statistics (Ripley's K, etc.) |

---

## Measurement Pitfalls

These are the most common errors. Flag them proactively — users rarely catch these on their own.

**Segmentation errors propagate into measurements.**
A merged pair of cells will have ~2× area, distorted eccentricity, and averaged intensity.
Always visually inspect a random sample of segmented images before trusting bulk measurements.
Rule of thumb: overlay masks on 5-10 representative images per condition.

**Background subtraction matters more than you think.**
Compare mean intensity of your objects to the local background. If background is spatially
heterogeneous (common in tissue sections, uneven illumination), use local background
subtraction — in Python, measure intensity in a dilated annular region around each object
using scikit-image regionprops, or use rolling-ball subtraction in FIJI as a preprocessing step.

**Edge objects have truncated measurements.**
Cells touching the image border are partially cropped — their area, perimeter, and shape
measurements are wrong. Filter them out. In Python, check if any mask pixel touches
row 0, col 0, row max, or col max. In FIJI, use Analyze Particles with "Exclude on edges".

**Photobleaching in timelapse.**
Fluorescence intensity drops over time due to photobleaching. If comparing intensity across
timepoints, normalize per-frame (e.g., divide by median background intensity per frame).
Without this, you'll see a false downward trend in any intensity measurement.

**Pixel size calibration.**
Always confirm µm/pixel from image metadata before reporting measurements. Area in pixels
is meaningless for cross-experiment comparison. If metadata is missing, measure a known
structure (scale bar, hemocytometer grid) to calibrate.

**Saturation / clipping.**
If your brightest signal hits the detector ceiling (e.g., 255 in 8-bit, 4095 in 12-bit),
integrated and mean intensity are underestimates. Check your intensity histograms — if
there's a spike at the maximum value, you have saturation. Re-acquire if possible, or
note the limitation.

---

## Choosing What to Measure

Use the biology-to-measurement mapping from the analysis plan. Resist the temptation to
"measure everything" — scikit-image regionprops can extract dozens of features per object,
but reporting all of them is not analysis. Focus on features that directly address the
biological question.

If doing exploratory profiling (no specific hypothesis): extract a broad feature set, then
use dimensionality reduction (PCA, UMAP) or classification to find which features
discriminate your conditions. Report the discriminating features, not all features.
