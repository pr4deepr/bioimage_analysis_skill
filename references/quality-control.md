# Quality Control Checklist

Run through these checks after segmentation, before trusting any measurements.
Present them to the user in order — each check catches a different failure mode.

## 1. Visual Overlay

Overlay segmentation masks on the raw image. Do boundaries match the objects?

- Check at least 5-10 images per condition
- Look specifically for: over-segmentation (one cell split into many), under-segmentation
  (multiple cells merged), boundary misalignment (mask shifted from actual cell edge)
- In Python: use napari (add labels layer over image) or matplotlib contour overlay on
  the raw image. In FIJI: use Image > Overlay > Add Image or the ROI Manager.

## 2. Object Count Sanity Check

Does the automated count match manual count in a few representative fields?

- Pick 3-5 images with varying density
- Count manually (or use FIJI multi-point tool)
- Compare. If automated count is consistently >20% off, the segmentation needs tuning.
- Under-counting usually means objects are being merged or missed
- Over-counting usually means debris/noise is being detected or objects are being split

## 3. Size Distribution

Plot a histogram of object areas across all images.

What to look for:
- **Bimodal peak**: likely merged objects (large peak) alongside correctly segmented ones,
  or two genuine biological populations. Inspect the large objects to determine which.
- **Spike at very small values**: debris, noise, or fragmented segmentation artifacts.
  Set a minimum area filter (e.g., exclude objects < 50% of expected cell area).
- **Suspiciously uniform sizes**: possible over-segmentation artifact where a watershed
  or similar method is splitting objects into equal-sized pieces.
- **Long right tail**: a few very large objects are almost always merged clusters. Check them.

## 4. Edge Case Images

Check the images with the highest and lowest object counts in your dataset.

- Highest-count images: often high-density fields where segmentation struggles with
  touching objects. Verify objects are actually separated correctly.
- Lowest-count images: may be out-of-focus, have unusual staining, or contain mostly
  background. Verify the low count is real and not a segmentation failure.
- These extremes are where failures concentrate — fixing them often improves the whole dataset.

## 5. Measurement Distributions

Plot distributions of your key measurements across all objects.

- **Values at floor/ceiling**: if >5% of measurements are at the minimum or maximum
  possible value, something is wrong. Common causes: intensity saturation, zero-area
  objects from segmentation artifacts, or touching-border objects with truncated measurements.
- **Unexpected outliers**: extreme values may be real biology or segmentation errors.
  Inspect the source images for the top/bottom 1% of any measurement.
- **Condition-specific artifacts**: plot distributions separately per condition. If one
  condition has a wildly different distribution shape (not just shifted mean), check whether
  imaging conditions differed (focus, exposure, staining intensity).

## 6. Batch Effects (if applicable)

If data spans multiple plates, slides, or imaging sessions:

- Compare measurement distributions across batches for control conditions
- If controls differ across batches, you have a batch effect that will confound your analysis
- Common causes: different exposure times, lamp intensity drift, staining variability
- Mitigation: normalize measurements per-batch (z-score within batch), or include batch
  as a covariate in statistical models

---

## Quick Reference: Common Problems and Diagnosis

| Symptom | Likely cause | Fix |
|---|---|---|
| Too many small objects | Debris detection | Add minimum area filter |
| Too few objects | Threshold too stringent | Lower threshold or switch to adaptive |
| Objects merged together | Threshold too permissive, or no watershed | Add watershed, use instance segmentation (Cellpose/StarDist) |
| Jagged boundaries | Low resolution or aggressive thresholding | Smooth image first, or use model-based segmentation |
| Counts vary wildly between similar images | Inconsistent illumination | Flat-field correction, or use adaptive thresholding |
| Intensity measurements unreliable | No background subtraction | Subtract local background before measuring |
