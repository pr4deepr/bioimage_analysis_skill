"""Spatial-transcriptomics clustering helpers.

Workaround for the Points2Regions int64-sparse bottleneck
---------------------------------------------------------
Points2Regions (wahlby-lab/Points2Regions, issue #3) builds a scipy sparse
feature matrix and passes it to scikit-learn's ``MiniBatchKMeans``. As the gene
panel / number of detected transcripts grows, the matrix's ``nnz`` exceeds
2**31, so scipy must keep **int64** index arrays. scikit-learn then refuses it::

    ValueError: Only sparse matrices with 32-bit integer indices are accepted.
                Got int64 indices.

Downcasting the indices to int32 would corrupt the matrix (the values genuinely
overflow int32), so that is not an option. Note this is unrelated to cuDF/cupy:
a cuDF *DataFrame* row index is a different object from a scipy CSR's
``.indices``/``.indptr`` arrays, and cuDF never enters this code path.

The fix clusters in **row chunks**. A row-slice of a CSR matrix re-derives its
index dtype, and any reasonable chunk's ``nnz`` and column count fit in int32 —
so scikit-learn only ever sees int32 sparse, losslessly. ``MiniBatchKMeans`` is
a streaming estimator (``partial_fit``), so chunked training is exactly what it
is designed for; prediction is likewise done chunk-by-chunk.

Public API
----------
- ``make_streaming_minibatch_kmeans(chunk_size, epochs)`` -> drop-in estimator
  class (subclass of ``MiniBatchKMeans``) that transparently handles int64
  sparse input.
- ``chunked_fit_predict(X, n_clusters, ...)`` -> cluster-label array for a
  sparse matrix, regardless of index dtype.
- ``patch_points2regions(...)`` / ``restore_points2regions(original)`` -> swap
  the symbol Points2Regions imports so existing P2R calls just work.

Design: dependencies are imported inside functions so importing this module
never fails when numpy/scipy/sklearn are absent.
"""

_P2R_MODULE = "points2regions._points2regions"


def make_streaming_minibatch_kmeans(chunk_size=200_000, epochs=5):
    """Build a ``MiniBatchKMeans`` subclass that trains and predicts in row
    chunks when handed an int64-indexed sparse matrix.

    Parameters
    ----------
    chunk_size : int
        Number of rows per chunk. Each chunk is downcast to int32 automatically
        by scipy's row slicing, so keep it well under ~2**31 / (avg non-zeros
        per row). 200k rows is comfortable for typical panels.
    epochs : int
        Number of shuffled passes over the data for ``partial_fit``. More
        epochs -> tighter convergence; 5 is usually plenty for region
        clustering.

    Returns
    -------
    type
        A class usable exactly like ``sklearn.cluster.MiniBatchKMeans``. On
        int32 input it falls back to the stock implementation unchanged.
    """
    import numpy as np
    import scipy.sparse as sp
    from sklearn.cluster import MiniBatchKMeans

    def _needs_chunking(X):
        return sp.issparse(X) and X.indices.dtype != np.int32

    # NOTE: no custom __init__ — sklearn forbids *args/**kwargs in an
    # estimator constructor (it introspects the signature for get_params).
    # chunk_size / epochs are captured from this factory's closure instead.
    class StreamingMiniBatchKMeans(MiniBatchKMeans):

        def fit(self, X, y=None, sample_weight=None):
            if not _needs_chunking(X):
                return super().fit(X, y=y, sample_weight=sample_weight)

            X = X.tocsr()
            n = X.shape[0]
            rng = np.random.default_rng(self.random_state)
            for _ in range(epochs):
                order = rng.permutation(n)
                for s in range(0, n, chunk_size):
                    batch = X[order[s:s + chunk_size]]
                    self.partial_fit(batch)
            # full label assignment, also chunked so predict never sees int64
            self.labels_ = self.predict(X)
            return self

        def predict(self, X):
            if not _needs_chunking(X):
                return super().predict(X)
            X = X.tocsr()
            parts = []
            for s in range(0, X.shape[0], chunk_size):
                parts.append(super().predict(X[s:s + chunk_size]))
            return np.concatenate(parts)

    StreamingMiniBatchKMeans.__name__ = "StreamingMiniBatchKMeans"
    StreamingMiniBatchKMeans.__qualname__ = "StreamingMiniBatchKMeans"
    return StreamingMiniBatchKMeans


def chunked_fit_predict(X, n_clusters, *, chunk_size=200_000, epochs=5,
                        random_state=0, **kmeans_kwargs):
    """Cluster a sparse feature matrix that may have int64 indices.

    Parameters
    ----------
    X : scipy.sparse matrix
        Feature matrix (rows = pixels/observations, cols = genes/features).
    n_clusters : int
        Number of clusters.
    chunk_size, epochs : int
        See :func:`make_streaming_minibatch_kmeans`.
    random_state : int or None
        Seed for reproducibility.
    **kmeans_kwargs
        Forwarded to ``MiniBatchKMeans`` (e.g. ``batch_size``, ``max_iter``).

    Returns
    -------
    numpy.ndarray
        Integer cluster label per row. The input matrix is not modified.
    """
    cls = make_streaming_minibatch_kmeans(chunk_size=chunk_size, epochs=epochs)
    model = cls(n_clusters=n_clusters, random_state=random_state,
                **kmeans_kwargs).fit(X)
    return model.labels_


def patch_points2regions(chunk_size=200_000, epochs=5):
    """Replace ``MiniBatchKMeans`` inside the Points2Regions module with the
    chunked drop-in, so existing P2R clustering calls handle int64 sparse.

    Call this *before* running the clustering step::

        from spatial_clustering import patch_points2regions
        original = patch_points2regions(chunk_size=200_000, epochs=5)
        # ... run Points2Regions clustering ...
        # optionally: restore_points2regions(original)

    Returns
    -------
    type
        The original ``MiniBatchKMeans`` class, for later restoration.
    """
    import importlib

    mod = importlib.import_module(_P2R_MODULE)
    original = mod.MiniBatchKMeans
    mod.MiniBatchKMeans = make_streaming_minibatch_kmeans(
        chunk_size=chunk_size, epochs=epochs)
    return original


def restore_points2regions(original):
    """Undo :func:`patch_points2regions`, restoring the original class."""
    import importlib

    mod = importlib.import_module(_P2R_MODULE)
    mod.MiniBatchKMeans = original
