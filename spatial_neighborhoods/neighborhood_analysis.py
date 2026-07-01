"""
Cellular neighborhood (CN) analysis for spatial proteomics (QuPath / OPAL).

A cleaned, importable adaptation of the Nolan lab NeighborhoodCoordination code
(Schurch et al., Cell 2020):
https://github.com/nolanlab/NeighborhoodCoordination

The original lives in Jupyter notebooks that rely on module-level globals and a
couple of now-deprecated / fragile pandas idioms. This module packages the same
algorithm as plain functions with explicit arguments and hardens the two spots
that bite people replicating it on QuPath data:

  * reset_index hazard - the notebook indexes a NumPy array with pandas index
    LABELS, so a filtered/subset dataframe silently produces WRONG neighborhoods.
    Here every function resets to a clean RangeIndex internally, so it is safe to
    pass a filtered export.
  * unclassified cells - kept by default and labelled "Other" so the k-nearest-
    neighbour geometry stays honest (dropping cells distorts the local scale,
    unevenly, across the tissue). You can optionally keep them for the neighbour
    search but exclude them from the clustering feature vector.

Algorithm (unchanged from the paper):
  for every cell -> take its k nearest cells WITHIN THE SAME IMAGE (the cell
  itself is included) -> count how many of each phenotype are in that window ->
  MiniBatchKMeans on those composition vectors. Each cluster is a cellular
  neighborhood.

Required: numpy, pandas, scikit-learn.
Plotting helpers also need: matplotlib, seaborn, scipy, shapely.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import MiniBatchKMeans


# ---------------------------------------------------------------------------
# QuPath loader
# ---------------------------------------------------------------------------

# QuPath column headers, verified against QuPath source, most-preferred first.
_QUPATH_X = ["Centroid X µm", "Centroid X um", "Centroid X px", "Centroid X"]
_QUPATH_Y = ["Centroid Y µm", "Centroid Y um", "Centroid Y px", "Centroid Y"]
_QUPATH_REGION = ["Image", "Image Name"]
_QUPATH_CLASS = ["Classification", "Class", "Name"]  # canonical header is "Classification"


def _first_present(candidates, columns):
    for c in candidates:
        if c in columns:
            return c
    return None


def load_qupath_export(
    path,
    x_col=None,
    y_col=None,
    region_col=None,
    celltype_col=None,
    unclassified="keep",   # "keep" -> label as "Other"; "drop" -> remove
    other_label="Other",
    sep=None,
):
    """
    Load a QuPath measurement export and standardise the columns CN analysis needs.

    QuPath (Measure -> Export measurements) writes one row per cell, TAB-separated
    by default. Coordinate headers are "Centroid X µm"/"Centroid Y µm" when the
    image is calibrated (else "... px"), the image id column is "Image", and the
    phenotype column is "Classification". All four are auto-detected but can be
    overridden.

    unclassified:
        "keep" (default) - blank/NaN classifications are RELABELLED `other_label`
            ("Other") and kept. This preserves the true local cell density, so the
            k-nearest-neighbour windows stay at a consistent physical scale. See
            the module docstring / README for the trade-off.
        "drop" - remove unclassified cells entirely (distorts neighbour geometry;
            only sensible when the unclassified fraction is very small).

    Returns
    -------
    (df, cols) : (DataFrame, dict)
        `cols` maps 'x','y','region','celltype' to resolved column names, ready to
        splat into compute_neighborhoods(df, **cols, ...).
    """
    if sep is None:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            header = fh.readline()
        sep = "\t" if header.count("\t") >= header.count(",") else ","

    df = pd.read_csv(path, sep=sep)

    x_col = x_col or _first_present(_QUPATH_X, df.columns)
    y_col = y_col or _first_present(_QUPATH_Y, df.columns)
    region_col = region_col or _first_present(_QUPATH_REGION, df.columns)
    celltype_col = celltype_col or _first_present(_QUPATH_CLASS, df.columns)

    missing = [n for n, c in [("x", x_col), ("y", y_col),
                              ("region", region_col), ("celltype", celltype_col)]
               if c is None]
    if missing:
        raise ValueError(
            f"Could not auto-detect column(s): {', '.join(missing)}. "
            f"Available columns: {list(df.columns)}. "
            "Pass them explicitly, e.g. celltype_col='Classification'."
        )

    # Normalise blank/NaN phenotypes to a single label.
    cls = df[celltype_col].astype("string")
    blank = cls.isna() | cls.str.strip().isin(["", "nan", "None"])
    n_blank = int(blank.sum())
    if unclassified == "drop":
        if n_blank:
            print(f"Dropping {n_blank} unclassified cells "
                  f"({100*n_blank/len(df):.1f}% of {len(df)}).")
        df = df.loc[~blank.values].copy()
    elif unclassified == "keep":
        cls = cls.where(~blank, other_label)
        df = df.copy()
        df[celltype_col] = cls.astype(str)
        if n_blank:
            print(f"Kept {n_blank} unclassified cells relabelled '{other_label}' "
                  f"({100*n_blank/len(df):.1f}% of {len(df)}).")
    else:
        raise ValueError("unclassified must be 'keep' or 'drop'")

    df = df.reset_index(drop=True)
    return df, {"x": x_col, "y": y_col, "region": region_col, "celltype": celltype_col}


# ---------------------------------------------------------------------------
# Neighborhood identification (core algorithm)
# ---------------------------------------------------------------------------

def _window_indices(coords, k):
    """Global-safe: indices of the k nearest cells (incl. self) for every cell."""
    k = min(k, len(coords))  # small regions may have fewer cells than k
    nn = NearestNeighbors(n_neighbors=k).fit(coords)
    _, idx = nn.kneighbors(coords)
    return idx


def compute_neighborhoods(
    df,
    x,
    y,
    region,
    celltype,
    k=10,
    n_neighborhoods=10,
    exclude_from_clustering=(),
    random_state=0,
    neighborhood_col=None,
    return_extras=True,
):
    """
    Assign every cell to a cellular neighborhood.

    Mirrors the NeighborhoodCoordination "Neighborhood Identification" notebook:
    per-image k-NN windows -> per-window phenotype counts -> MiniBatchKMeans.
    The dataframe index is reset internally, so filtered inputs are safe.

    Parameters
    ----------
    df : DataFrame                    one row per cell.
    x, y : str                        centroid columns (prefer calibrated µm).
    region : str                      image/core id; neighbours stay within it.
    celltype : str                    discrete phenotype per cell.
    k : int                           window size (self + k-1 nearest). Try 5/10/20.
    n_neighborhoods : int             number of neighborhoods (KMeans clusters).
    exclude_from_clustering : seq[str]
        Phenotypes to keep for the NEIGHBOUR SEARCH (geometry) but drop from the
        KMeans feature vector, e.g. ("Other",). Remaining counts are renormalised
        to fractions per window so sparse windows compare fairly. Empty (default)
        = classic behaviour, everything clusters on raw counts.
    random_state : int                KMeans seed.
    neighborhood_col : str            output column name (default f"neighborhood{k}").

    Returns
    -------
    df_out : DataFrame                copy of df + categorical neighborhood column.
    extras : dict (if return_extras)
        'windows'          (n_cells, n_types) raw per-window phenotype counts
        'cell_types'       column order for 'windows'
        'feature_types'    types actually used by KMeans
        'centroids'        KMeans centroids (feature space)
        'kmeans'           fitted MiniBatchKMeans
        'neighborhood_col' output column name
    """
    if neighborhood_col is None:
        neighborhood_col = f"neighborhood{k}"

    df = df.reset_index(drop=True).copy()          # neutralises the reset_index hazard
    cell_types = sorted(df[celltype].astype(str).unique())
    onehot = (pd.get_dummies(df[celltype].astype(str))
              .reindex(columns=cell_types, fill_value=0)
              .values.astype(np.float32))

    # Sum the phenotype composition of each cell's k-NN window, per image.
    windows = np.zeros((len(df), len(cell_types)), dtype=np.float32)
    for _, region_idx in df.groupby(region, sort=False).groups.items():
        region_idx = np.asarray(region_idx)
        coords = df.loc[region_idx, [x, y]].values.astype(np.float64)
        nbr_local = _window_indices(coords, k)          # local positions within region
        global_nbr = region_idx[nbr_local]              # -> global row indices
        windows[region_idx] = onehot[global_nbr].sum(axis=1)

    # Build the clustering feature matrix (optionally excluding some types).
    exclude = set(exclude_from_clustering)
    feature_types = [t for t in cell_types if t not in exclude]
    if not feature_types:
        raise ValueError("exclude_from_clustering removed every phenotype.")
    keep_idx = [cell_types.index(t) for t in feature_types]
    feats = windows[:, keep_idx].astype(np.float64)
    if exclude:
        # renormalise to fractions of the KEPT phenotypes (guard empty windows)
        totals = feats.sum(axis=1, keepdims=True)
        totals[totals == 0] = 1.0
        feats = feats / totals

    km = MiniBatchKMeans(n_clusters=n_neighborhoods, random_state=random_state)
    labels = km.fit_predict(feats)

    df[neighborhood_col] = pd.Categorical(labels)

    if not return_extras:
        return df
    return df, {
        "windows": windows,
        "cell_types": cell_types,
        "feature_types": feature_types,
        "centroids": km.cluster_centers_,
        "kmeans": km,
        "neighborhood_col": neighborhood_col,
    }


# ---------------------------------------------------------------------------
# Interpretation: which phenotypes define each neighborhood
# ---------------------------------------------------------------------------

def neighborhood_composition(df, extras, as_enrichment=True):
    """
    Per-neighborhood phenotype profile, as either raw mean fractions or log2
    fold-enrichment vs the tissue-wide average (the paper's heatmap). Computed
    from the true per-window composition over ALL phenotypes (incl. any excluded
    from clustering), so "Other" is still visible for interpretation.

    Returns a DataFrame (neighborhoods x phenotypes).
    """
    windows = extras["windows"]
    cell_types = extras["cell_types"]
    ncol = extras["neighborhood_col"]

    labels = df[ncol].astype(int).values
    comp = pd.DataFrame(windows, columns=cell_types)
    comp["__nb__"] = labels
    mean_counts = comp.groupby("__nb__").mean()
    frac = mean_counts.div(mean_counts.sum(axis=1), axis=0)      # fraction per neighborhood
    if not as_enrichment:
        return frac

    # log2 fold-change vs the tissue-wide average, with the paper's pseudocount
    # smoothing (offset each composition by the tissue average, then renormalise)
    # so a neighborhood lacking a phenotype gives a finite value, not -inf.
    tissue_avg = windows.sum(axis=0) / windows.sum()             # > 0 for every present type
    smoothed = frac.values + tissue_avg
    smoothed = smoothed / smoothed.sum(axis=1, keepdims=True)
    fc = np.log2(smoothed / tissue_avg)
    return pd.DataFrame(fc, index=frac.index, columns=cell_types)


def plot_neighborhood_heatmap(fc, vmin=-3, vmax=3, savepath=None, **kwargs):
    """Clustered heatmap of the enrichment table. Requires seaborn."""
    import seaborn as sns
    g = sns.clustermap(fc, vmin=vmin, vmax=vmax, cmap="bwr",
                       row_cluster=False, **kwargs)
    if savepath:
        g.savefig(savepath, bbox_inches="tight")
    return g


# ---------------------------------------------------------------------------
# Voronoi visualisation (from the repo's voronoi.py; logic unchanged)
# ---------------------------------------------------------------------------

def voronoi_finite_polygons_2d(vor, radius=None):
    """Reconstruct infinite 2D Voronoi regions to finite ones.
    Adapted from https://stackoverflow.com/questions/20515554 via the Nolan lab repo."""
    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")
    new_regions = []
    new_vertices = vor.vertices.tolist()
    center = vor.points.mean(axis=0)
    if radius is None:
        radius = np.ptp(vor.points, axis=0).max()

    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region in enumerate(vor.point_region):
        vertices = vor.regions[region]
        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue
        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]
        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue
            t = vor.points[p2] - vor.points[p1]
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])
            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius
            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
        new_region = np.array(new_region)[np.argsort(angles)]
        new_regions.append(new_region.tolist())
    return new_regions, np.asarray(new_vertices)


def draw_voronoi_scatter(spot, x, y, neighborhood_col, palette=None,
                         figsize=(6, 6), line_width=0.1, invert_y=True,
                         savepath=None):
    """
    Voronoi map of ONE image coloured by cellular neighborhood - the paper's
    signature tissue view. `spot` = the cells of a single image/region.
    Requires matplotlib, seaborn, scipy, shapely.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    from shapely.geometry import MultiPoint, Point, Polygon
    from scipy.spatial import Voronoi

    if palette is None:
        palette = sns.color_palette("bright", 20)
    codes = pd.Categorical(spot[neighborhood_col]).codes
    colors = [palette[c % len(palette)] for c in codes]

    points = spot[[x, y]].values.astype(float)
    if invert_y:
        points[:, 1] = points[:, 1].max() - points[:, 1]

    vor = Voronoi(points)
    regions, vertices = voronoi_finite_polygons_2d(vor)
    mask = MultiPoint([Point(p) for p in points]).convex_hull

    plt.figure(figsize=figsize)
    for i, region in enumerate(regions):
        poly = vertices[region]
        poly = np.append(poly, poly[:1], axis=0)
        clipped = Polygon(poly).intersection(mask)
        if clipped.is_empty or clipped.geom_type != "Polygon":
            continue
        xs, ys = clipped.exterior.coords.xy
        plt.fill(xs, ys, facecolor=colors[i], edgecolor=colors[i],
                 linewidth=line_width)
    plt.axis("off")
    if savepath:
        plt.savefig(savepath, bbox_inches="tight", dpi=200)
    return plt.gca()
