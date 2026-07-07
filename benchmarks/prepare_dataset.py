#!/usr/bin/env python3
"""Convert an AnnData (.h5ad) spatial-proteomics object into a flat CSV that
`tabpfn_phenotyping_benchmark.py` can read.

Writes: marker columns (from adata.X / a chosen layer) + a `cell_label` column
(from an obs key) + a `group` column (from an obs key) + `X:X`/`Y:Y` if spatial
coordinates are present in obsm. See datasets.md for sources (squidpy, spatialdata).

Usage
-----
    python prepare_dataset.py --h5ad mibitof.h5ad --label-obs Cluster \
        --group-obs library_id --out mibitof_cells.csv

    # then
    python tabpfn_phenotyping_benchmark.py --csv mibitof_cells.csv \
        --label-col cell_label --group-col group --dry-run
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd


def to_dense(X):
    return X.toarray() if hasattr(X, "toarray") else np.asarray(X)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--h5ad", required=True, help="input AnnData .h5ad")
    ap.add_argument("--label-obs", required=True,
                    help="obs column holding the cell-type label")
    ap.add_argument("--group-obs", required=True,
                    help="obs column holding the sample/patient id (for grouped CV)")
    ap.add_argument("--layer", default=None,
                    help="use adata.layers[LAYER] instead of adata.X (e.g. an "
                         "arcsinh/normalized layer)")
    ap.add_argument("--spatial-key", default="spatial",
                    help="obsm key with X/Y coordinates (default: spatial)")
    ap.add_argument("--out", required=True, help="output CSV path")
    args = ap.parse_args()

    try:
        import anndata as ad
    except Exception:
        print("ERROR: needs `anndata` (pip install anndata)", file=sys.stderr)
        return 1

    adata = ad.read_h5ad(args.h5ad)
    print(f"[in] {args.h5ad}: {adata.n_obs} cells x {adata.n_vars} vars")

    for key in (args.label_obs, args.group_obs):
        if key not in adata.obs:
            print(f"ERROR: obs column {key!r} not found. Available: "
                  f"{list(adata.obs.columns)}", file=sys.stderr)
            return 1

    X = to_dense(adata.layers[args.layer] if args.layer else adata.X)
    df = pd.DataFrame(X, columns=[str(v) for v in adata.var_names])
    df["cell_label"] = adata.obs[args.label_obs].to_numpy()
    df["group"] = adata.obs[args.group_obs].to_numpy()
    if args.spatial_key in adata.obsm:
        xy = np.asarray(adata.obsm[args.spatial_key])
        df["X:X"], df["Y:Y"] = xy[:, 0], xy[:, 1]

    df.to_csv(args.out, index=False)
    n_lab = df["cell_label"].nunique()
    n_grp = df["group"].nunique()
    print(f"[out] {args.out}: {len(df)} cells, {adata.n_vars} markers, "
          f"{n_lab} labels, {n_grp} groups")
    print("      run: python tabpfn_phenotyping_benchmark.py --csv "
          f"{args.out} --label-col cell_label --group-col group --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
