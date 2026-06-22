"""Tests for the int64-sparse KMeans workaround used for Points2Regions
spatial-transcriptomics clustering.

Background
----------
Points2Regions builds a scipy sparse feature matrix internally and hands it to
scikit-learn's MiniBatchKMeans. When the gene panel / transcript count grows,
the matrix's ``nnz`` exceeds 2**31 and scipy keeps int64 index arrays. sklearn
then refuses it:

    ValueError: Only sparse matrices with 32-bit integer indices are accepted.
                Got int64 indices.

Downcasting the indices would corrupt the matrix (the values genuinely don't
fit in int32). The fix clusters in row chunks: each row-slice re-derives an
int32 index dtype, so sklearn only ever sees int32 sparse, with no data loss.

These tests pin down both halves of "accurate":
1. correctness of the chunked predict (must equal nearest-centre assignment),
2. recovery of real cluster structure (ARI ~ 1 on well-separated blobs),
while exercising the genuine int64 -> chunked path the bug requires.
"""
import numpy as np
import pytest
import scipy.sparse as sp
from sklearn.cluster import MiniBatchKMeans
from sklearn.datasets import make_blobs
from sklearn.metrics import adjusted_rand_score, pairwise_distances_argmin

import spatial_clustering as sc


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _force_int64(X):
    """Return a CSR copy whose index arrays are int64 (mimics a >2**31 nnz
    matrix that scipy could not downcast)."""
    X = sp.csr_matrix(X)
    X = X.copy()
    X.indices = X.indices.astype(np.int64)
    X.indptr = X.indptr.astype(np.int64)
    assert X.indices.dtype == np.int64 and X.indptr.dtype == np.int64
    return X


def _blobs(n=600, centers=4, n_features=8, std=0.6, seed=0):
    Xd, y = make_blobs(n_samples=n, centers=centers, n_features=n_features,
                       cluster_std=std, random_state=seed)
    # shift to non-negative so it resembles count-like data, then sparsify
    Xd = Xd - Xd.min()
    return sp.csr_matrix(Xd), y


# --------------------------------------------------------------------------- #
# the bug exists (guards against the workaround silently becoming unnecessary)
# --------------------------------------------------------------------------- #
def test_stock_minibatchkmeans_rejects_int64_indices():
    X, _ = _blobs()
    X64 = _force_int64(X)
    with pytest.raises(ValueError, match="int64"):
        MiniBatchKMeans(n_clusters=4, n_init=3, random_state=0).fit(X64)


def test_row_slice_of_int64_matrix_is_int32():
    """The mechanism the fix relies on: slicing rows downcasts the index dtype
    when the slice fits in int32."""
    X, _ = _blobs()
    X64 = _force_int64(X)
    chunk = X64[0:50]
    assert chunk.indices.dtype == np.int32
    assert chunk.indptr.dtype == np.int32


# --------------------------------------------------------------------------- #
# chunked_fit_predict
# --------------------------------------------------------------------------- #
def test_chunked_fit_predict_runs_on_int64_without_error():
    X, _ = _blobs()
    X64 = _force_int64(X)
    labels = sc.chunked_fit_predict(X64, n_clusters=4, chunk_size=50,
                                    epochs=5, random_state=0)
    assert labels.shape == (X64.shape[0],)
    assert set(np.unique(labels)).issubset(set(range(4)))


def test_chunked_fit_predict_recovers_cluster_structure():
    X, y = _blobs(std=0.5)
    X64 = _force_int64(X)
    labels = sc.chunked_fit_predict(X64, n_clusters=4, chunk_size=50,
                                    epochs=8, random_state=0)
    # well-separated blobs must be recovered almost perfectly
    assert adjusted_rand_score(y, labels) > 0.95


def test_chunked_fit_is_one_global_clustering_not_per_chunk():
    """The whole point of Points2Regions: a single clustering shared across the
    entire dataset. Chunked training must recover the *same* global partition as
    an ordinary single-shot fit — proving the centroids propagate across chunks
    rather than each chunk being clustered independently."""
    X, _ = _blobs(std=0.5)
    X64 = _force_int64(X)

    # reference: an ordinary global fit on the int32 matrix
    ref = MiniBatchKMeans(n_clusters=4, n_init=3, random_state=0).fit(X)
    chunked = sc.chunked_fit_predict(X64, n_clusters=4, chunk_size=50,
                                     epochs=8, random_state=0)

    # same partition as a single global fit (label ids may be permuted -> ARI)
    assert adjusted_rand_score(ref.labels_, chunked) > 0.9
    # one shared label set spanning all chunks, not 4-per-chunk fragmentation
    assert len(np.unique(chunked)) == 4


def test_chunked_fit_predict_does_not_mutate_input_dtype():
    X, _ = _blobs()
    X64 = _force_int64(X)
    sc.chunked_fit_predict(X64, n_clusters=4, chunk_size=50, random_state=0)
    assert X64.indices.dtype == np.int64  # original untouched -> no corruption


# --------------------------------------------------------------------------- #
# the drop-in estimator
# --------------------------------------------------------------------------- #
def test_streaming_estimator_fits_int64_and_exposes_sklearn_attrs():
    Cls = sc.make_streaming_minibatch_kmeans(chunk_size=50, epochs=6)
    X, _ = _blobs()
    X64 = _force_int64(X)
    model = Cls(n_clusters=4, random_state=0).fit(X64)
    assert model.cluster_centers_.shape == (4, X64.shape[1])
    assert model.labels_.shape == (X64.shape[0],)


def test_streaming_predict_equals_nearest_centre_assignment():
    """Chunked predict must be *exactly* nearest-centre assignment — this is the
    correctness check independent of any implementation detail."""
    Cls = sc.make_streaming_minibatch_kmeans(chunk_size=50, epochs=6)
    X, _ = _blobs()
    X64 = _force_int64(X)
    model = Cls(n_clusters=4, random_state=0).fit(X64)

    got = model.predict(X64)
    expected = pairwise_distances_argmin(X64, model.cluster_centers_)
    np.testing.assert_array_equal(got, expected)
    # labels_ recorded during fit must match a fresh predict
    np.testing.assert_array_equal(model.labels_, got)


def test_streaming_predict_chunking_is_invariant_to_chunk_size():
    """Predicting in chunks of different sizes yields identical labels (the
    split must not change results)."""
    X, _ = _blobs()
    X64 = _force_int64(X)
    big = sc.make_streaming_minibatch_kmeans(chunk_size=10_000, epochs=6)(
        n_clusters=4, random_state=0).fit(X64)
    # reuse the SAME centres so only the predict-chunking differs
    small = sc.make_streaming_minibatch_kmeans(chunk_size=7, epochs=6)(
        n_clusters=4, random_state=0)
    small.cluster_centers_ = big.cluster_centers_.copy()
    small.n_features_in_ = big.n_features_in_
    small._n_threads = getattr(big, "_n_threads", 1)
    np.testing.assert_array_equal(big.predict(X64), small.predict(X64))


def test_streaming_estimator_passthrough_on_int32():
    """When given an int32 matrix it must behave like stock MiniBatchKMeans
    (no chunked path), so existing small-data workflows are unaffected."""
    Cls = sc.make_streaming_minibatch_kmeans(chunk_size=50, epochs=6)
    X, _ = _blobs()
    assert X.indices.dtype == np.int32
    model = Cls(n_clusters=4, random_state=0).fit(X)
    assert model.cluster_centers_.shape == (4, X.shape[1])
    # nearest-centre invariant still holds on the int32 path
    expected = pairwise_distances_argmin(X, model.cluster_centers_)
    np.testing.assert_array_equal(model.predict(X), expected)


# --------------------------------------------------------------------------- #
# patch_points2regions
# --------------------------------------------------------------------------- #
def test_patch_points2regions_swaps_and_restores(monkeypatch):
    """Patch the symbol Points2Regions imports, without the real package
    installed, using a stand-in module."""
    import sys
    import types

    fake_mod = types.ModuleType("points2regions._points2regions")
    fake_mod.MiniBatchKMeans = MiniBatchKMeans
    pkg = types.ModuleType("points2regions")
    monkeypatch.setitem(sys.modules, "points2regions", pkg)
    monkeypatch.setitem(sys.modules, "points2regions._points2regions", fake_mod)

    original = sc.patch_points2regions(chunk_size=50, epochs=4)
    assert original is MiniBatchKMeans
    assert fake_mod.MiniBatchKMeans is not MiniBatchKMeans
    assert issubclass(fake_mod.MiniBatchKMeans, MiniBatchKMeans)

    # the swapped-in class actually handles int64 where the original would fail
    X, _ = _blobs()
    X64 = _force_int64(X)
    model = fake_mod.MiniBatchKMeans(n_clusters=4, random_state=0).fit(X64)
    assert model.labels_.shape == (X64.shape[0],)

    # restoration puts the original back
    sc.restore_points2regions(original)
    assert fake_mod.MiniBatchKMeans is MiniBatchKMeans
