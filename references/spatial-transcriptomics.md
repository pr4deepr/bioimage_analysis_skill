# Spatial transcriptomics: Points2Regions int64-sparse clustering

## Symptom

Transcript-based region clustering (Points2Regions) crashes once the gene panel
or transcript count grows:

```
ValueError: Only sparse matrices with 32-bit integer indices are accepted.
            Got int64 indices.
```

## Cause

Points2Regions builds a scipy sparse feature matrix (rows = grid pixels,
cols = genes) and passes it to scikit-learn's `MiniBatchKMeans`. When `nnz`
exceeds `2**31`, scipy must keep **int64** index arrays (`.indices` / `.indptr`).
scikit-learn's KMeans validates with `accept_large_sparse=False` and rejects any
int64-indexed sparse — regardless of whether the values would fit.

Two sub-cases:

- **Incidental int64** (`nnz < 2**31`): indices could be int32 but aren't.
  Downcasting is safe — but scipy usually does this automatically on `.tocsr()`,
  so you rarely land here.
- **Genuinely large** (`nnz > 2**31`): downcasting would corrupt the matrix.
  This is what large panels hit, and it needs the chunked approach below.

Check which case you are in:

```python
print(X.shape, X.nnz, X.indices.dtype, "limit:", 2**31 - 1)
```

## Not a cuDF problem

cuDF's "int64 index support" refers to a **DataFrame row index**, a different
object from a scipy CSR's `.indices`/`.indptr`. Points2Regions never builds a
DataFrame in this path, so swapping pandas → cuDF changes nothing here. The GPU
equivalent of KMeans is cuML (`cuml.cluster.KMeans`), but it needs **dense**
input — infeasible for a genuinely large sparse matrix — and helps with speed,
not this validation error.

## Fix: cluster in row chunks

A row-slice of a CSR matrix re-derives its index dtype; any reasonable chunk's
`nnz` and column count fit in int32, so scikit-learn only ever sees int32 sparse
— losslessly. `MiniBatchKMeans` is a streaming estimator (`partial_fit`), so
chunked training is exactly its design; prediction is chunked too.

Implementation: `references/spatial_clustering.py`.

### Option A — patch Points2Regions (least code)

```python
from spatial_clustering import patch_points2regions, restore_points2regions

original = patch_points2regions(chunk_size=200_000, epochs=5,
                                init_subsample="auto")
# ... run your normal Points2Regions clustering call ...
restore_points2regions(original)   # optional
```

`patch_points2regions` swaps the `MiniBatchKMeans` symbol that Points2Regions
imports with a chunked drop-in, so existing calls just work.

### Option B — cluster a sparse matrix directly

```python
from spatial_clustering import chunked_fit_predict

labels = chunked_fit_predict(X, n_clusters=20, chunk_size=200_000, epochs=5)
```

### Tuning

- `chunk_size`: rows per chunk. Lower it if a chunk is memory-heavy; keep it
  well under `2**31 / (avg non-zeros per row)`.
- `epochs`: shuffled passes for `partial_fit`. 5 is usually plenty; raise it for
  tighter convergence.
- `init_subsample`: k-means++ warm start. Streaming `partial_fit` otherwise
  seeds centroids from the first chunk only, which can leave a cluster empty.
  Set `"auto"` (or an int row count) to run k-means++ on a random row-subsample
  first — a global-quality init that avoids degenerate clusters, still without
  materialising the int64 matrix for sklearn. Recommended for production runs.

All three (training, prediction, and this init) share **one** global centroid
set, so cluster identity is consistent across every chunk — labels mean the same
region everywhere, which is what Points2Regions needs before connected
components.

## Alternative knobs (no code change)

- **Coarsen the grid** (`pixel_width` ↑): fewer pixels → lower `nnz`, often back
  under `2**31`, at the cost of resolution.
- **Lower `pixel_smoothing`**: high values (e.g. 50) smear each transcript over
  many pixels and inflate `nnz`.

These trade resolution for fit; the chunked approach keeps full panel and
resolution and is the recommended fix.
