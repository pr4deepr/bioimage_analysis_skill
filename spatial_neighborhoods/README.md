# Cellular Neighborhood (CN) analysis for QuPath / OPAL data

A self-contained resource for running **cellular-neighborhood analysis** (Schürch
et al., *Cell* 2020 — the [Nolan lab NeighborhoodCoordination](https://github.com/nolanlab/NeighborhoodCoordination)
method) on **OPAL multiplex-IF single-cell tables exported from QuPath**.

> **What CN analysis does:** it clusters cells by *what surrounds them*, not by what
> they are. For every cell it takes the *k* nearest cells in the same image (a
> "window"), counts how many of each phenotype are in that window, and clusters
> all those composition vectors with k-means. Each cluster is a **cellular
> neighborhood** — a recurring local tissue motif (e.g. "tumor–immune boundary",
> "immune aggregate", "stroma"). Two cells with the same phenotype land in
> different neighborhoods if their surroundings differ.

This bundle is three files:

| File | Purpose |
|---|---|
| `neighborhood_analysis.py` | The validated, importable algorithm (load, compute, interpret, plot). |
| `run_neighborhoods.py` | End-to-end script — edit the CONFIG block and run. |
| `README.md` | This guide + a paste-ready Claude Code prompt. |

---

## Prerequisite (the real work is upstream, in QuPath)

The algorithm **consumes** cell phenotypes; it does **not** discover them. Before
you run anything, every cell must carry a classification in QuPath:

1. Detect cells (e.g. **Cell detection** / StarDist on the DAPI/nuclear channel).
2. **Phenotype every cell** — threshold your OPAL markers (single-measurement
   classifiers / "Create thresholder", combined into composite classes) or train
   an **object classifier**. Multi-marker cells export as colon-joined strings
   like `Tumor: CD8` — that's fine, each unique string is treated as one phenotype.
3. **Measure → Export measurements** (detections). QuPath writes one row per cell,
   **tab-separated** by default.

The export will contain (exact headers, verified against QuPath source):

| Role | QuPath column |
|---|---|
| X coordinate | `Centroid X µm` (calibrated) or `Centroid X px` |
| Y coordinate | `Centroid Y µm` / `Centroid Y px` |
| Image / core id | `Image` |
| Phenotype | `Classification` |

`load_qupath_export()` auto-detects all four; override only if your headers differ.

**Calibrate your pixel size in QuPath** so coordinates come out in µm — then a
window of *k* cells means a consistent physical scale across images. Don't mix
calibrated and uncalibrated images in one run.

---

## Setup (local machine)

```bash
python -m venv .venv && source .venv/bin/activate      # or use conda/mamba
pip install numpy pandas scikit-learn matplotlib seaborn scipy shapely
```

(Only the first three are needed to compute neighborhoods; the rest are for the
heatmap and Voronoi plots.)

---

## Two ways to run it

### A. Just run the script

Edit the `CONFIG` block at the top of `run_neighborhoods.py` (`EXPORT_PATH`, `K`,
`N_NEIGHBORHOODS`, …), then:

```bash
python run_neighborhoods.py
```

Outputs land in `cn_output/`: the labelled cell table, the enrichment heatmap,
and a Voronoi map of the largest image.

### B. Drive it with Claude Code (recommended for the first pass)

Drop this folder into your project, open Claude Code in that directory, and paste
the prompt below. It makes Claude look at your data and confirm the phenotype
breakdown **before** clustering, which is where the important judgement calls are.

```text
I have a QuPath measurement export of OPAL multiplex-IF data at:
    <PATH-TO-YOUR-EXPORT.tsv>
Each row is a cell with a `Classification` phenotype, `Centroid X µm` /
`Centroid Y µm` coordinates, and an `Image` column (one image per tissue core).

Use the scripts in ./spatial_neighborhoods/ to run cellular-neighborhood (CN)
analysis (Nolan lab NeighborhoodCoordination method). Do it in this order:

1. Load the export with load_qupath_export(..., unclassified="keep") so
   unclassified cells are kept and labelled "Other" (this preserves the
   k-nearest-neighbour geometry). Print the detected columns, the total cell
   count, the number of images, and the full phenotype value_counts — including
   what fraction is "Other". STOP and show me this, and ask me to confirm the
   phenotypes look right before clustering.

2. After I confirm, run compute_neighborhoods at k=10 with 10 neighborhoods.
   If "Other" is more than ~30% of cells, ALSO run a second version with
   exclude_from_clustering=("Other",) and tell me how much the neighborhood
   assignments change between the two.

3. Show me the log2 enrichment heatmap (neighborhood_composition +
   plot_neighborhood_heatmap) and describe, in words, which phenotypes define
   each neighborhood and a plausible biological name for each.

4. Draw a Voronoi map (draw_voronoi_scatter) of one representative image
   coloured by neighborhood so I can see the spatial structure.

Save all outputs to ./cn_output/. Don't wire anything into a skill — just run
the analysis and report back at each checkpoint.
```

Replace `<PATH-TO-YOUR-EXPORT.tsv>`. If your project layout differs, adjust the
`./spatial_neighborhoods/` path.

---

## The two knobs

- **`k`** (window size): small *k* → fine, local motifs; large *k* → broad tissue
  zones. Try 5 / 10 / 20 and pick what gives interpretable, non-redundant
  neighborhoods. (`k` counts the cell itself + its *k*-1 nearest.)
- **`n_neighborhoods`** (clusters): how many CNs to carve out. Read the enrichment
  heatmap — if two neighborhoods look identical, lower it; if one is a muddle of
  everything, raise it.

---

## The "Other" / unclassified decision

In OPAL data, 30–60% of detections often get no positive phenotype. What you do
with them **changes the result**, because the *k* nearest cells are drawn from
whatever cells are in the table:

- **Keep them (default, `unclassified="keep"`).** Preserves true local cell
  density, so windows stay at a consistent physical scale across the tissue.
  Dropping cells stretches windows unevenly — more in unclassified-rich regions —
  and silently distorts every neighborhood. This is why keep is the default.
- **Downside of keeping:** "Other" is a grab-bag (junk + real cells outside your
  panel). If it's a large fraction it can *dominate* the clustering, so
  neighborhoods sort by "how much Other is here" rather than by your biology.
- **Best of both:** keep them for the neighbour search but drop the "Other" column
  from the clustering vector — `exclude_from_clustering=("Other",)`. Correct
  geometry, biology-driven clusters. The kept counts are renormalised to fractions
  so sparse windows still compare fairly.
- **Better still, upstream:** give marker-negative cells an honest coarse label in
  QuPath (`stroma`, `epithelial-marker-negative`) instead of leaving them "Other".
- **Sensitivity check:** run keep vs. exclude-from-clustering and compare labels.
  If they agree, the choice is moot; if they diverge, "Other" is driving your
  structure and you should decide deliberately.

---

## Reading the outputs

- **`neighborhood_enrichment_heatmap.png`** — rows = neighborhoods, columns =
  phenotypes, colour = log2 fold-enrichment vs the tissue average. Red = that
  phenotype is over-represented in that neighborhood. This is how you *name* each
  CN.
- **`cells_with_neighborhoods.csv`** — your original table plus a
  `neighborhood10` column, ready for downstream stats (e.g. compare neighborhood
  frequencies between conditions/patients).
- **`voronoi_<image>.png`** — the tissue coloured by neighborhood; shows the
  spatial layout of the motifs.

---

## Notes / gotchas (already handled, but good to know)

- **`reset_index` safety.** The original notebook indexes a NumPy array with
  pandas *labels*, so a filtered/subset dataframe silently yields **wrong**
  neighborhoods. Every function here resets to a clean `RangeIndex` internally, so
  it's safe to pass a filtered export.
- **Self-inclusion.** Each window includes the cell itself (the paper's behaviour),
  so `k=10` = the cell + its 9 nearest neighbours.
- **Per-image neighbours.** Neighbours are found only *within* the same `Image` —
  cells never borrow neighbours across cores/slides.
- **Blank classifications** are normalised to `"Other"` (or dropped) on load, so
  they can't crash the one-hot step.

## Attribution

Algorithm from the Nolan lab
[NeighborhoodCoordination](https://github.com/nolanlab/NeighborhoodCoordination)
repository (Schürch et al., *Cell* 2020). This is a repackaging for QuPath/OPAL
inputs; the neighborhood-identification logic and Voronoi reconstruction are
adapted from that repo.
