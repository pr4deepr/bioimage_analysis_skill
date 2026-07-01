"""
End-to-end cellular-neighborhood analysis on a QuPath / OPAL export.

Edit the CONFIG block, then run:  python run_neighborhoods.py
Outputs land in ./cn_output/ (labelled CSV, enrichment heatmap, Voronoi map).
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")            # save figures without a display; drop for interactive use
import matplotlib.pyplot as plt

from neighborhood_analysis import (
    load_qupath_export,
    compute_neighborhoods,
    neighborhood_composition,
    plot_neighborhood_heatmap,
    draw_voronoi_scatter,
)

# ------------------------------ CONFIG ------------------------------
EXPORT_PATH = "measurements.tsv"     # your QuPath "Export measurements" file
K = 10                               # window size (self + k-1 nearest); try 5 / 10 / 20
N_NEIGHBORHOODS = 10                 # number of neighborhoods (KMeans clusters)
UNCLASSIFIED = "keep"                # "keep" (label Other, preserves geometry) or "drop"
EXCLUDE_FROM_CLUSTERING = ()         # e.g. ("Other",) to keep it for geometry but not clustering
OUTDIR = Path("cn_output")
# Override auto-detection only if needed, e.g. celltype_col="Classification"
COLUMN_OVERRIDES = {}
# --------------------------------------------------------------------

OUTDIR.mkdir(exist_ok=True)

# 1. Load + standardise columns.
df, cols = load_qupath_export(EXPORT_PATH, unclassified=UNCLASSIFIED, **COLUMN_OVERRIDES)
print("Detected columns:", cols)
print(f"{len(df):,} cells across {df[cols['region']].nunique()} image(s).")
print("Phenotype counts:")
print(df[cols["celltype"]].value_counts())

# 2. Compute neighborhoods.
df, extras = compute_neighborhoods(
    df, x=cols["x"], y=cols["y"], region=cols["region"], celltype=cols["celltype"],
    k=K, n_neighborhoods=N_NEIGHBORHOODS,
    exclude_from_clustering=EXCLUDE_FROM_CLUSTERING,
)
nb = extras["neighborhood_col"]
df.to_csv(OUTDIR / "cells_with_neighborhoods.csv", index=False)
print(f"\nNeighborhood sizes ({nb}):")
print(df[nb].value_counts().sort_index())

# 3. Enrichment heatmap (which phenotypes define each neighborhood).
fc = neighborhood_composition(df, extras, as_enrichment=True)
fc.to_csv(OUTDIR / "neighborhood_enrichment_log2fc.csv")
g = plot_neighborhood_heatmap(fc, figsize=(max(6, 0.5 * fc.shape[1]), 6))
g.savefig(OUTDIR / "neighborhood_enrichment_heatmap.png", bbox_inches="tight", dpi=200)
plt.close("all")

# 4. Voronoi map of the largest image, coloured by neighborhood.
biggest = df[cols["region"]].value_counts().idxmax()
spot = df[df[cols["region"]] == biggest]
draw_voronoi_scatter(spot, x=cols["x"], y=cols["y"], neighborhood_col=nb,
                     savepath=OUTDIR / f"voronoi_{str(biggest)[:40]}.png")
plt.close("all")

print(f"\nDone. See {OUTDIR}/ for the labelled CSV, enrichment heatmap, and Voronoi map.")
