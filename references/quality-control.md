# Quality Control Checklist

Run through these checks after segmentation, before trusting any measurements. Present them to the user in order — each check catches a different failure mode.

## 1. Visual Overlay
Overlay masks on raw image. Check at least 5-10 images per condition. Look for: over-segmentation (one cell split into many), under-segmentation (cells merged), boundary misalignment.

## 2. Object Count Sanity Check
Compare automated count to manual count in 3-5 representative fields. If consistently >20% off, the segmentation needs tuning. Under-counting = merging. Over-counting = debris/splitting.

## 3. Size Distribution
Plot histogram of object areas. Look for:
- **Bimodal peak**: likely merged objects alongside correct ones
- **Spike at very small values**: debris or fragmentation artifacts → add minimum area filter
- **Suspiciously uniform sizes**: possible over-segmentation (watershed splitting equally)
- **Long right tail**: very large objects are almost always merged clusters

## 4. Edge Case Images
Check images with highest and lowest object counts. These extremes are where failures concentrate — fixing them often improves the whole dataset.

## 5. Measurement Distributions
Plot distributions of key measurements. Flag if:
- >5% of values at floor/ceiling → saturation or segmentation artifacts
- Unexpected outliers → inspect source images for top/bottom 1%
- One condition has wildly different distribution shape → check imaging conditions

## 6. Batch Effects
If data spans multiple plates/slides/sessions: compare control measurement distributions across batches. If controls differ, you have a batch effect. Mitigate: z-score within batch, or include batch as a covariate.

---

## Quick Reference: Common Problems

| Symptom | Likely cause | Fix |
|---|---|---|
| Too many small objects | Debris detection | Add minimum area filter |
| Too few objects | Threshold too stringent | Lower threshold or switch to adaptive |
| Objects merged together | No instance separation | Add watershed, or use Cellpose/StarDist |
| Jagged boundaries | Low resolution or aggressive thresholding | Smooth image first, or use model-based segmentation |
| Counts vary wildly between similar images | Inconsistent illumination | Flat-field correction, or adaptive thresholding |
| Intensity measurements unreliable | No background subtraction | Subtract local background before measuring |
