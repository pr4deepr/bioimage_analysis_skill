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

## Pitfalls

- **Cellpose channel ordering**: channel 1 = segmentation target, channel 2 = nuclear auxiliary. Mis-ordering produces bad results silently.
- **DL models normalize internally**: feeding pre-normalized 8-bit data to Cellpose/StarDist can hurt performance. Check the tool's documentation.
- **Segmenting the wrong channel**: surprisingly common — always verify which channel you're passing to segmentation.

## Recommended Order

When multiple steps are needed:

1. Illumination correction (flat-field)
2. Background subtraction
3. Noise reduction
4. Intensity normalization
5. Channel extraction

Illumination correction before background subtraction because uneven illumination biases the background estimate. Noise reduction before normalization because extreme noise values distort the normalization range.
