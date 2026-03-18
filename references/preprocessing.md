# Preprocessing

Steps to prepare raw microscopy images before segmentation. Not all steps are needed for
every dataset — pick what applies based on the data and modality.

## Illumination Correction / Flat-Field

Uneven illumination across the field of view causes intensity gradients that confuse
both thresholding and DL models. More problematic in widefield than confocal.

**When to apply**: if background intensity varies visibly across the image, or if you're
comparing intensity measurements across the field.

**Approaches**:
- Retrospective: estimate illumination function from the image stack (median of all images,
  or polynomial fit). Divide each image by the illumination function.
- Prospective: acquire a flat-field reference image (uniform fluorescent slide) and divide.
- BaSiC algorithm handles both illumination and dark-field correction from the image stack
  itself — good default for plate-based experiments.

**Recommended tools**: BaSiC (ImageJ plugin or Python), scikit-image polynomial fitting,
FIJI (Process > Calculator for flat-field division).

```python
# Flat-field correction: divide image by illumination estimate
corrected = image / illumination_image * illumination_image.mean()
```

## Background Subtraction

Removes autofluorescence or non-specific staining so intensity measurements reflect
true signal.

**When to apply**: if background is non-zero and you need accurate intensity measurements.
Less critical if you only need object shapes/counts.

**Approaches**:
- Rolling-ball subtraction: fits a "ball" under the intensity surface. Good for slowly
  varying background. Set radius larger than your largest object.
- Top-hat filtering: morphological operation that removes large-scale background while
  preserving small bright objects. Good for punctate stains.
- Local background measurement: measure intensity in an annular region around each object
  and subtract per-object. Most accurate for heterogeneous background.

**Recommended tools**: FIJI (Process > Subtract Background), scikit-image
morphology.white_tophat, scipy.ndimage for local background estimation.

```python
from skimage.restoration import rolling_ball
background = rolling_ball(image, radius=50)
background_removed = image - background
```

```python
from skimage.morphology import disk, white_tophat
background_removed = white_tophat(image, footprint=disk(radius))
```

## Noise Reduction

Smoothing reduces noise but also blurs boundaries. Use the minimum amount needed.

**When to apply**: noisy images where segmentation is failing on spurious local maxima
or fragmented thresholds. Skip if images are clean — unnecessary smoothing hurts
segmentation accuracy.

**Approaches**:
- Gaussian blur: simple, fast. Sigma 1-2 pixels is usually enough. Larger sigma =
  more blurring.
- Median filter: preserves edges better than Gaussian. Good for salt-and-pepper noise.
  Use kernel size 3-5.
- Non-local means denoising: slower but preserves fine structure. Good for low-SNR data
  where you need sharp boundaries.

**Recommended tools**: scikit-image filters (gaussian, median, denoise_nl_means),
FIJI Process > Filters.

```python
from skimage.filters import gaussian
smoothed = gaussian(image, sigma=1.0)
```

```python
from skimage.filters import median
from skimage.morphology import disk
denoised = median(image, footprint=disk(3))
```

## Channel Separation and Selection

For multi-channel images, extract the relevant channel(s) before segmentation.

**When to apply**: always, for multi-channel data. Segmentation should run on the channel
that best defines the object boundary (e.g., DAPI for nuclei, membrane marker for cells).

**Pitfalls**:
- Make sure you're segmenting from the right channel. A surprisingly common error is
  running nuclear segmentation on the wrong fluorescence channel.
- For Cellpose: the tool expects specific channel ordering (channel 1 = segmentation
  target, channel 2 = nuclear auxiliary). Mis-ordering produces bad results silently.

**Recommended tools**: BioIO (Python — reads multi-channel microscopy formats natively),
numpy indexing, FIJI Image > Color > Split Channels.

```python
# For multi-channel array with shape (C, Y, X)
dapi_channel = image[0]  # first channel
marker_channel = image[1]  # second channel
```

## Intensity Normalization

Rescale intensity values to a standard range so segmentation parameters transfer across
images and experiments.

**When to apply**: if images vary significantly in brightness across the dataset (different
exposure times, staining variability, different imaging sessions).

**Approaches**:
- Percentile normalization: clip to 1st-99th percentile, then rescale to 0-1. Robust to
  outlier bright pixels (debris, dead cells).
- Per-image normalization: normalize each image independently. Use when absolute intensity
  doesn't matter (shape-only segmentation).
- Per-batch normalization: normalize to batch statistics. Use when comparing intensity
  across images within a batch.

**Recommended tools**: scikit-image exposure.rescale_intensity, numpy percentile + clip,
FIJI Image > Adjust > Brightness/Contrast (for interactive exploration).

```python
import numpy as np
p1, p99 = np.percentile(image, (1, 99))
normalized = np.clip((image - p1) / (p99 - p1), 0, 1).astype(np.float32)
```

## Bit Depth Conversion

Some tools expect specific bit depths (8-bit, 16-bit, 32-bit float).

**When to apply**: when a tool fails or produces unexpected results. Check if it expects
a different bit depth than your data.

**Pitfalls**:
- Converting 16-bit to 8-bit without rescaling truncates or clips values. Always rescale
  first (e.g., map the data range to 0-255).
- Some DL models (Cellpose, StarDist) handle normalization internally — feeding
  pre-normalized 8-bit data can actually hurt performance. Check the tool's documentation.

---

## Preprocessing Order

When multiple steps are needed, this order generally works best:

1. Illumination correction (flat-field)
2. Background subtraction
3. Noise reduction
4. Intensity normalization
5. Channel extraction

Illumination correction before background subtraction because uneven illumination biases
the background estimate. Noise reduction before normalization because extreme noise values
can distort the normalization range.
