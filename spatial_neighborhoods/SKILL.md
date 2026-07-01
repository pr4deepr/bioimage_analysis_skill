---
name: cellular-neighborhoods
description: >
  Run cellular-neighborhood (CN) analysis on spatial proteomics single-cell data
  — the Nolan lab NeighborhoodCoordination method (Schürch et al., Cell 2020).
  Use this skill when the user wants spatial analysis of multiplexed tissue data:
  cellular neighborhoods, spatial niches, neighborhood analysis, cell neighborhood
  clustering, QuPath export, OPAL / multiplex IF / IHC, CODEX / mIF spatial
  clustering, "what cell types cluster together spatially", tissue microenvironment
  or niche identification. Consumes a per-cell table with X/Y coordinates, an
  image/region id, and a phenotype/classification per cell (e.g. a QuPath
  "Measure → Export measurements" file).
---

# Cellular Neighborhood (CN) analysis

Clusters cells by **what surrounds them**, not what they are. For each cell, take
its *k* nearest cells in the same image (a "window"), count the phenotypes in that
window, and cluster all those composition vectors with k-means. Each cluster is a
**cellular neighborhood** — a recurring local tissue motif (tumor–immune boundary,
immune aggregate, stroma, …).

Algorithm and code adapted from the Nolan lab
[NeighborhoodCoordination](https://github.com/nolanlab/NeighborhoodCoordination)
repo, packaged here for QuPath/OPAL exports. Full details and the "Other"-cell
trade-off are in `README.md` — read it before running.

## Files

- `neighborhood_analysis.py` — the importable algorithm (load, compute, interpret, plot)
- `run_neighborhoods.py` — end-to-end template (edit CONFIG, run)
- `README.md` — prerequisites, setup, interpretation, the "Other" decision
- `requirements.txt` — dependencies

## Prerequisite (do NOT skip)

The method **consumes** cell phenotypes; it does not discover them. Every cell must
already carry a discrete classification (in QuPath: threshold OPAL markers or train
an object classifier, then Measure → Export measurements). If cells are
unclassified, that is a decision to make, not an error — see the "Other" section
below.

## Setup

```bash
pip install -r requirements.txt
```

Required for computing: numpy, pandas, scikit-learn. Plotting adds matplotlib,
seaborn, scipy, shapely.

## Workflow (follow in order; checkpoint with the user)

1. **Load & inspect — then STOP.** Call `load_qupath_export(path, unclassified="keep")`.
   Columns (`Centroid X µm`/`Centroid Y µm`, `Image`, `Classification`) auto-detect;
   override only if needed. Print detected columns, cell count, number of images,
   and the full phenotype `value_counts()` including the **"Other" fraction**. Show
   the user and confirm the phenotypes look right before clustering.
2. **Compute.** `compute_neighborhoods(df, **cols, k=10, n_neighborhoods=10)`.
   `cols` is the dict returned by the loader. Try `k` in {5, 10, 20}. If "Other" is
   >~30% of cells, also run with `exclude_from_clustering=("Other",)` (keeps them
   for the neighbour geometry but not the clustering vector) and report how much the
   labels change.
3. **Interpret.** `neighborhood_composition(df, extras)` → `plot_neighborhood_heatmap`.
   Rows = neighborhoods, columns = phenotypes, red = enriched vs tissue average.
   Describe which phenotypes define each neighborhood and give each a biological name.
4. **Map.** `draw_voronoi_scatter(one_image_df, x, y, neighborhood_col)` to show the
   spatial layout of the neighborhoods for a representative image.
5. **Export.** Save the labelled cell table (adds a `neighborhood{k}` column) for
   downstream stats — e.g. comparing neighborhood frequencies between conditions.

## Key parameters

- **k** (window size): small = fine/local motifs, large = broad zones. Includes the
  cell itself (k=10 → cell + 9 nearest).
- **n_neighborhoods**: number of CNs (k-means clusters). Tune via the heatmap — merge
  if two look identical, raise if one is a muddle.
- **unclassified / "Other"**: kept by default (`"keep"`, relabelled "Other") to keep
  the k-NN geometry honest; dropping cells distorts the local scale unevenly. If
  "Other" dominates, use `exclude_from_clustering=("Other",)`. See README.

## Notes (already handled by the code)

- Neighbours are found **per image** — never across cores/slides.
- The dataframe index is reset internally, so **filtered exports are safe** (the
  original notebook silently mis-assigns neighbourhoods on a subset index).
- Blank classifications are normalised to "Other" (or dropped) on load.
