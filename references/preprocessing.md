# Preprocessing

Not all steps are needed — pick what applies based on data and modality.

## When to Apply What

| Problem | Solution | Tool |
|---|---|---|
| Uneven illumination across field | Flat-field correction | BaSiC algorithm, or divide by illumination reference |
| Non-zero background, need intensity measurements | Background subtraction | Rolling-ball (FIJI/skimage), top-hat, or per-object annular subtraction |
| Noisy image, segmentation failing on spurious maxima | Noise reduction | Gaussian (sigma 1-2), median (kernel 3-5), or non-local means for low-SNR |
| Brightness varies across dataset | Intensity normalization | Percentile clip to 1st-99th, rescale to 0-1 |
| Multi-channel data | Channel extraction | Segment from channel that best defines boundaries (e.g., DAPI for nuclei) |
| Tool expects different bit depth | Bit depth conversion | Rescale first, then convert (never truncate 16→8 without rescaling) |
| Intensity decay over time in timelapse | Photobleaching correction | Exponential fit to pre-stimulus baseline, or frame-wise normalization by background region. See `timeseries-functional.md` |
| Frame-to-frame motion in timelapse | Image registration | `skimage.registration.phase_cross_correlation` for rigid translation; suite2p or CaImAn for non-rigid. Register before segmentation or trace extraction |

## Pitfalls

- **Cellpose channel ordering**: channel 1 = segmentation target, channel 2 = nuclear auxiliary. Mis-ordering produces bad results silently.
- **Cellpose normalizes internally** and is robust to raw uint16 — do not pre-normalize to 8-bit. **StarDist requires explicit normalization** via `csbdeep.utils.normalize(image, pmin=1, pmax=99.8)` before prediction — without it, StarDist may return empty results.
- **Segmenting the wrong channel**: surprisingly common — always verify which channel you're passing to segmentation.

## Recommended Order

When multiple steps are needed:

1. Channel extraction (select the channel to segment — DAPI for nuclei, membrane marker for cells, etc.)
2. Illumination correction (flat-field)
3. Background subtraction
4. Noise reduction
5. Intensity normalization

Channel extraction first because all subsequent steps should operate on the channel you're actually segmenting. Illumination correction before background subtraction because uneven illumination biases the background estimate. Noise reduction before normalization because extreme noise values distort the normalization range.
