#!/usr/bin/env python3
"""Benchmark TabPFN (+ ManyClassClassifier) against standard baselines for
per-cell phenotyping on multiplexed spatial-proteomics data.

Implements the protocol in ``tabpfn-spatial-proteomics-evaluation.md`` (§6):
patient-grouped cross-validation, stratified context subsampling for TabPFN,
and imbalance-aware metrics with calibration and wall-clock timing.

Designed for the Schürch 2020 CRC CODEX table (``main_fcs_csv.csv``: columns
``ClusterName`` (label), ``X:X``/``Y:Y``, ``File Name`` (region), ``patients``,
``groups``, plus ~56 marker-intensity columns) but is schema-robust: metadata
columns are detected by name and everything else numeric is treated as a marker.

Models whose libraries are absent (tabpfn, tabpfn_extensions, xgboost) are
skipped with a note, so the baseline comparison still runs on a bare stack.

Usage
-----
    python tabpfn_phenotyping_benchmark.py --csv main_fcs_csv.csv --out results/
    python tabpfn_phenotyping_benchmark.py --smoke        # synthetic fixture, no data needed
    python tabpfn_phenotyping_benchmark.py --csv URL_OR_PATH --folds 5 --context 10000

If ``--csv`` is an ``http(s)://`` URL (e.g. a GitHub ``media.githubusercontent.com``
LFS link) it is downloaded first. ``.csv.gz`` is read transparently.
"""
from __future__ import annotations

import argparse
import io
import os
import time
import urllib.request
import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Columns that are metadata, never markers, regardless of dataset.
META_COLS_DEFAULT = {
    "X:X", "Y:Y", "X", "Y", "x", "y",
    "File Name", "filename", "reg", "region",
    "ClusterName", "ClusterID", "cluster",
    "patients", "patient", "groups", "group",
    "neighborhood10", "neighborhood", "TMA", "spot", "CellID", "cell_id",
}

# Best-effort coarse lineage map for the 28 Schürch CRC ClusterName types,
# used only by the optional `tabpfn_coarse` model (<=10 classes -> vanilla TabPFN).
LINEAGE_MAP = {
    "tumor cells": "epithelial/tumor",
    "tumor cells / immune cells": "epithelial/tumor",
    "CD11c+ DCs": "myeloid",
    "CD68+ macrophages": "myeloid",
    "CD68+CD163+ macrophages": "myeloid",
    "CD163+ macrophages": "myeloid",
    "CD68+ macrophages GzmB+": "myeloid",
    "CD11b+CD68+ macrophages": "myeloid",
    "CD11b+ monocytes": "myeloid",
    "granulocytes": "granulocyte",
    "CD4+ T cells": "T cell",
    "CD4+ T cells CD45RO+": "T cell",
    "CD4+ T cells GATA3+": "T cell",
    "CD8+ T cells": "T cell",
    "CD3+ T cells": "T cell",
    "Tregs": "T cell",
    "NK cells": "NK",
    "B cells": "B/plasma",
    "plasma cells": "B/plasma",
    "vasculature": "vascular/lymphatic",
    "lymphatics": "vascular/lymphatic",
    "immune cells / vasculature": "vascular/lymphatic",
    "stroma": "stroma/muscle",
    "smooth muscle": "stroma/muscle",
    "adipocytes": "stroma/muscle",
    "nerves": "nerve/other",
    "immune cells": "immune-other",
    "undefined": "nerve/other",
}


# --------------------------------------------------------------------------- #
# Data loading and schema detection
# --------------------------------------------------------------------------- #
def load_table(csv: str, nrows: int | None = None) -> pd.DataFrame:
    if csv.startswith(("http://", "https://")):
        print(f"[data] downloading {csv}")
        with urllib.request.urlopen(csv, timeout=300) as r:  # noqa: S310
            raw = r.read()
        buf = io.BytesIO(raw)
        comp = "gzip" if csv.endswith(".gz") else "infer"
        return pd.read_csv(buf, compression=comp, low_memory=False, nrows=nrows)
    print(f"[data] reading {csv}" + (f" (first {nrows} rows)" if nrows else ""))
    return pd.read_csv(csv, low_memory=False, nrows=nrows)


def detect_schema(df: pd.DataFrame, label_col: str, group_col: str,
                  meta_cols: set[str]) -> list[str]:
    """Return the marker columns: numeric columns that are not metadata."""
    non_marker = set(meta_cols) | {label_col, group_col}
    markers = []
    for c in df.columns:
        if c in non_marker or str(c).startswith("Unnamed"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            markers.append(c)
    return markers


# --------------------------------------------------------------------------- #
# Preprocessing (fit on train, apply to test — no leakage)
# --------------------------------------------------------------------------- #
def fit_preprocess(X_train: np.ndarray, cofactor: float = 5.0):
    Xt = np.arcsinh(X_train / cofactor)
    mu = Xt.mean(axis=0)
    sd = Xt.std(axis=0) + 1e-8
    return (cofactor, mu, sd)


def apply_preprocess(X: np.ndarray, params) -> np.ndarray:
    cofactor, mu, sd = params
    return (np.arcsinh(X / cofactor) - mu) / sd


def stratified_subsample(y: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Indices of a class-stratified subsample of size ~n (keeps >=1 per class)."""
    if n >= len(y):
        return np.arange(len(y))
    idx_by_c = {c: np.where(y == c)[0] for c in np.unique(y)}
    frac = n / len(y)
    picked = []
    for c, idx in idx_by_c.items():
        k = max(1, int(round(len(idx) * frac)))
        picked.append(rng.choice(idx, size=min(k, len(idx)), replace=False))
    out = np.concatenate(picked)
    if len(out) > n:
        out = rng.choice(out, size=n, replace=False)
    return out


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def expected_calibration_error(y_true, proba, classes, n_bins: int = 15) -> float:
    conf = proba.max(axis=1)
    pred = classes[proba.argmax(axis=1)]
    correct = (pred == y_true).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.sum():
            ece += (m.sum() / len(conf)) * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def score(y_true, y_pred, proba, classes) -> dict:
    from sklearn.metrics import (balanced_accuracy_score, f1_score,
                                  accuracy_score, roc_auc_score)
    out = {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }
    if proba is not None:
        try:
            yb = pd.get_dummies(pd.Categorical(y_true, categories=classes)).values
            out["roc_auc_ovr_macro"] = roc_auc_score(yb, proba, average="macro",
                                                      multi_class="ovr")
        except Exception:
            out["roc_auc_ovr_macro"] = np.nan
        out["ece"] = expected_calibration_error(np.asarray(y_true), proba, classes)
    return out


# --------------------------------------------------------------------------- #
# Model registry
# --------------------------------------------------------------------------- #
@dataclass
class ModelSpec:
    name: str
    make: object                       # () -> fresh estimator
    context_subsample: bool = False    # fit only on the stratified context subsample
    coarse: bool = False               # predict coarse lineage labels
    available: bool = True
    note: str = ""


def build_registry(context: int) -> list[ModelSpec]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.ensemble import RandomForestClassifier

    specs = [
        ModelSpec("logreg", lambda: LogisticRegression(max_iter=2000, n_jobs=-1)),
        ModelSpec("knn", lambda: KNeighborsClassifier(n_neighbors=15, n_jobs=-1)),
        ModelSpec("random_forest",
                  lambda: RandomForestClassifier(n_estimators=300, n_jobs=-1,
                                                 class_weight="balanced_subsample",
                                                 random_state=0)),
    ]
    # XGBoost (optional). Wrapped so folds missing a class (common with rare
    # cell types under grouped splits) still get contiguous 0..K-1 labels.
    try:
        from xgboost import XGBClassifier
        from sklearn.preprocessing import LabelEncoder

        class XGBWrapper:
            def __init__(self):
                self._x = XGBClassifier(
                    n_estimators=400, max_depth=6, learning_rate=0.1,
                    subsample=0.8, colsample_bytree=0.8, n_jobs=-1,
                    tree_method="hist", eval_metric="mlogloss")
                self._le = LabelEncoder()

            def fit(self, X, y):
                self._x.fit(X, self._le.fit_transform(y))
                self.classes_ = self._le.classes_
                return self

            def predict(self, X):
                return self._le.inverse_transform(self._x.predict(X))

            def predict_proba(self, X):
                return self._x.predict_proba(X)

        specs.append(ModelSpec("xgboost", XGBWrapper))
    except Exception as e:
        specs.append(ModelSpec("xgboost", None, available=False, note=str(e)))

    # TabPFN + ManyClassClassifier (optional) — the model under evaluation
    try:
        from tabpfn import TabPFNClassifier
        from tabpfn_extensions.many_class import ManyClassClassifier

        def make_many():
            base = TabPFNClassifier(ignore_pretraining_limits=True)
            return ManyClassClassifier(estimator=base, random_state=0)

        specs.append(ModelSpec("tabpfn_manyclass", make_many, context_subsample=True,
                               note="TabPFN via ECOC codebook (all classes)"))
        specs.append(ModelSpec(
            "tabpfn_coarse",
            lambda: TabPFNClassifier(ignore_pretraining_limits=True),
            context_subsample=True, coarse=True,
            note="vanilla TabPFN on <=10 coarse lineages"))
    except Exception as e:
        specs.append(ModelSpec("tabpfn_manyclass", None, available=False, note=str(e)))
    return specs


# --------------------------------------------------------------------------- #
# Cross-validation driver
# --------------------------------------------------------------------------- #
def run(df: pd.DataFrame, markers: list[str], label_col: str, group_col: str,
        folds: int, context: int, seed: int, random_split: bool):
    from sklearn.model_selection import GroupKFold, StratifiedKFold
    from sklearn.preprocessing import LabelEncoder

    rng = np.random.default_rng(seed)
    X = df[markers].to_numpy(dtype=float)
    y_names = df[label_col].astype(str).to_numpy()
    groups = df[group_col].astype(str).to_numpy()
    # Integer-encode labels once (XGBoost requires 0..K-1; sklearn/TabPFN accept it too).
    le = LabelEncoder().fit(y_names)
    y = le.transform(y_names)
    class_names = le.classes_
    coarse_names = np.array([LINEAGE_MAP.get(v, "other") for v in y_names])
    y_coarse = LabelEncoder().fit_transform(coarse_names)

    n_groups = len(np.unique(groups))
    folds = min(folds, n_groups) if not random_split else folds
    if random_split:
        splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
        split_iter = list(splitter.split(X, y))
        split_kind = "random (leakage check)"
    else:
        splitter = GroupKFold(n_splits=folds)
        split_iter = list(splitter.split(X, y, groups))
        split_kind = f"patient-grouped ({group_col})"

    print(f"[cv] {split_kind}: {folds} folds | {len(y)} cells | "
          f"{len(np.unique(y))} classes | {n_groups} groups | {len(markers)} markers")

    specs = build_registry(context)
    results: dict[str, list[dict]] = {s.name: [] for s in specs}
    per_class_f1: dict[str, list[np.ndarray]] = {}
    class_order = np.unique(y)

    for fi, (tr, te) in enumerate(split_iter):
        pp = fit_preprocess(X[tr])
        Xtr_all, Xte = apply_preprocess(X[tr], pp), apply_preprocess(X[te], pp)
        sub = stratified_subsample(y[tr], context, rng)
        for s in specs:
            if not s.available or s.make is None:
                continue
            ytr_src = y_coarse if s.coarse else y
            yte_src = y_coarse if s.coarse else y
            rows = sub if s.context_subsample else np.arange(len(tr))
            Xtr, ytr = Xtr_all[rows], ytr_src[tr][rows]
            yte = yte_src[te]
            try:
                t0 = time.time()
                est = s.make()
                est.fit(Xtr, ytr)
                try:
                    proba = est.predict_proba(Xte)
                    classes = est.classes_
                    pred = classes[proba.argmax(axis=1)]
                except Exception:
                    proba, classes, pred = None, None, est.predict(Xte)
                dt = time.time() - t0
                m = score(yte, pred, proba, classes if proba is not None else np.unique(yte))
                m["seconds"] = dt
                m["n_train"] = len(ytr)
                results[s.name].append(m)
                if not s.coarse:
                    from sklearn.metrics import f1_score
                    f1c = f1_score(yte, pred, labels=class_order, average=None,
                                   zero_division=0)
                    per_class_f1.setdefault(s.name, []).append(f1c)
                print(f"  fold {fi} {s.name:18} balAcc={m['balanced_accuracy']:.3f} "
                      f"macroF1={m['macro_f1']:.3f} {dt:.1f}s")
            except Exception as e:
                print(f"  fold {fi} {s.name:18} ERROR: {type(e).__name__}: {e}")

    return results, per_class_f1, class_order, y, specs, split_kind, class_names


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def _to_md(df, index=False):
    try:
        return df.to_markdown(index=index, floatfmt=".3f")
    except Exception:
        return df.round(3).to_string(index=index)


def summarize(results, per_class_f1, class_order, y, specs, split_kind, out_dir,
              class_names):
    import os
    os.makedirs(out_dir, exist_ok=True)
    names = np.asarray(class_names)[class_order]
    rows = []
    for name, folds in results.items():
        if not folds:
            continue
        df = pd.DataFrame(folds)
        agg = {"model": name, "n_folds": len(df)}
        for col in ["balanced_accuracy", "macro_f1", "weighted_f1", "accuracy",
                    "roc_auc_ovr_macro", "ece", "seconds"]:
            if col in df:
                agg[f"{col}_mean"] = df[col].mean()
                agg[f"{col}_std"] = df[col].std()
        rows.append(agg)
    lead = pd.DataFrame(rows).sort_values("balanced_accuracy_mean", ascending=False)
    lead.to_csv(os.path.join(out_dir, "leaderboard.csv"), index=False)

    # rare-class table (support + per-class F1 per model)
    supp = pd.Series(y).value_counts().reindex(class_order).fillna(0).astype(int)
    pc = {name: np.mean(v, axis=0) for name, v in per_class_f1.items() if v}
    pcdf = pd.DataFrame(pc, index=names)
    pcdf.insert(0, "support", supp.values)
    pcdf = pcdf.sort_values("support")
    pcdf.to_csv(os.path.join(out_dir, "per_class_f1.csv"))

    lines = [f"# Benchmark results ({split_kind})\n",
             "## Leaderboard (mean over folds)\n",
             _to_md(lead, index=False),
             "\n\n## Per-class F1 by support (rare classes first)\n",
             _to_md(pcdf, index=True),
             "\n\n## Models skipped (library missing)\n"]
    for s in specs:
        if not s.available:
            lines.append(f"- `{s.name}`: {s.note}")
    ran = {name for name, f in results.items() if f}
    stalled = [s for s in specs if s.available and s.name not in ran]
    if stalled:
        lines.append("\n## Models available but with 0 successful folds\n")
        for s in stalled:
            lines.append(f"- `{s.name}`: no folds completed — check the run log "
                         f"(TabPFN needs HuggingFace-gated weights + network access).")
    md = "\n".join(lines)
    with open(os.path.join(out_dir, "results.md"), "w") as f:
        f.write(md)
    print("\n" + md)
    print(f"\n[out] wrote leaderboard.csv, per_class_f1.csv, results.md to {out_dir}/")
    return lead


# --------------------------------------------------------------------------- #
# Synthetic fixture (for --smoke, mirrors the CRC CODEX schema)
# --------------------------------------------------------------------------- #
def synthetic(n_cells=6000, n_patients=12, n_markers=56, n_classes=28, seed=0):
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 3, size=(n_classes, n_markers))
    types = list(LINEAGE_MAP.keys())[:n_classes]
    # imbalanced class priors (a few dominant, a long tail — like real phenotyping)
    prior = rng.dirichlet(np.linspace(0.2, 3.0, n_classes))
    yi = rng.choice(n_classes, size=n_cells, p=prior)
    X = centers[yi] + rng.normal(0, 1.5, size=(n_cells, n_markers))
    X = np.sinh(X) * 5.0  # de-normalize so arcsinh preprocessing is exercised
    patients = rng.integers(0, n_patients, size=n_cells)
    df = pd.DataFrame(X, columns=[f"marker_{i:02d}" for i in range(n_markers)])
    df["ClusterName"] = [types[i] for i in yi]
    df["patients"] = [f"p{p:02d}" for p in patients]
    df["groups"] = (patients % 2 + 1)
    df["X:X"] = rng.uniform(0, 1000, n_cells)
    df["Y:Y"] = rng.uniform(0, 1000, n_cells)
    df["File Name"] = [f"reg{p:02d}_A" for p in patients]
    return df


# --------------------------------------------------------------------------- #
# Dry run — pre-flight checks, no cross-validation (don't burn GPU hours)
# --------------------------------------------------------------------------- #
def dry_run(df, args) -> int:
    import platform
    ok = True
    tabpfn_ready = False

    def check(label, passed, detail=""):
        nonlocal ok
        mark = "PASS" if passed else "FAIL"
        if passed is None:
            mark = "WARN"
        elif not passed:
            ok = False
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))

    print("=" * 70)
    print("DRY RUN — pre-flight checks (no cross-validation is run)")
    print("=" * 70)
    print(f"\npython {platform.python_version()} on {platform.system()} "
          f"{platform.machine()}")

    # --- libraries / models ------------------------------------------------ #
    print("\n[1] libraries & models")
    specs = build_registry(args.context)
    for s in specs:
        check(f"model `{s.name}`", True if s.available else None,
              s.note if not s.available else s.note or "available")

    # --- compute ----------------------------------------------------------- #
    print("\n[2] compute")
    try:
        import torch
        cuda = torch.cuda.is_available()
        check("torch import", True, f"{torch.__version__}")
        check("CUDA GPU", None if not cuda else True,
              "available" if cuda else "no GPU — TabPFN will be slow on CPU")
        if cuda:
            print(f"        device: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        check("torch import", None, f"{type(e).__name__}: {e} (baselines still run)")

    # --- TabPFN weight cache ---------------------------------------------- #
    print("\n[3] TabPFN weights (gated HuggingFace checkpoint)")
    print(f"        HF_HOME={os.environ.get('HF_HOME', '(default ~/.cache/huggingface)')}"
          f"  HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE', '0')}")
    try:
        from tabpfn import TabPFNClassifier
        Xt = np.random.RandomState(0).randn(32, 4)
        yt = (Xt[:, 0] > 0).astype(int)
        TabPFNClassifier(device="cpu").fit(Xt, yt).predict(Xt[:2])
        check("TabPFN checkpoint loads", True, "cached/reachable")
        tabpfn_ready = True
    except Exception as e:
        check("TabPFN checkpoint loads", None,
              f"{type(e).__name__}: {str(e).splitlines()[0][:120]} "
              "(run prefetch_tabpfn.py on a login node)")

    # --- data -------------------------------------------------------------- #
    print("\n[4] data & schema" + (f" (sampled {args.sample_rows} rows)"
                                    if args.sample_rows else ""))
    have_label = args.label_col in df.columns
    have_group = args.group_col in df.columns
    check(f"label column `{args.label_col}`", have_label,
          "" if have_label else f"not found in {list(df.columns)[:20]}")
    check(f"group column `{args.group_col}`", have_group,
          "" if have_group else "(needed for patient-grouped splits)")
    if not have_label:
        print("\nRESULT: NOT READY — fix the label column.")
        return 1

    markers = detect_schema(df, args.label_col, args.group_col, META_COLS_DEFAULT)
    check("marker columns detected", len(markers) > 0, f"{len(markers)} markers")
    check("markers within TabPFN 500-feature limit", len(markers) <= 500,
          f"{len(markers)}")
    nan_m = int(df[markers].isna().sum().sum()) if markers else 0
    check("no NaNs in markers", nan_m == 0, f"{nan_m} NaN cells" if nan_m else "clean")

    n_cells = len(df)
    n_classes = df[args.label_col].nunique()
    supp = df[args.label_col].value_counts()
    print(f"        cells={n_cells}  classes={n_classes}  "
          f"rarest='{supp.index[-1]}' (n={int(supp.iloc[-1])})  "
          f"most common='{supp.index[0]}' (n={int(supp.iloc[0])})")
    check("class count vs TabPFN 10-class head", None if n_classes > 10 else True,
          f"{n_classes} classes → ManyClassClassifier required (tabpfn_manyclass)"
          if n_classes > 10 else f"{n_classes} ≤ 10")
    if have_group:
        n_groups = df[args.group_col].nunique()
        check(f"folds ({args.folds}) ≤ groups ({n_groups})", args.folds <= n_groups,
              "" if args.folds <= n_groups else "reduce --folds")
        ctx = min(args.context, int(n_cells * (n_groups - 1) / n_groups))
        print(f"        groups={n_groups}  ~context/fold={ctx} "
              f"(cap --context={args.context})  cells>context={n_cells > args.context}")

    tp = "TabPFN ready" if tabpfn_ready else "TabPFN needs weights cached (see [3])"
    print("\n" + "=" * 70)
    print(f"RESULT: {'READY' if ok else 'ISSUES ABOVE'} — baselines can run; {tp}. "
          "No CV was executed.")
    print("=" * 70)
    return 0 if ok else 2


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="path or http(s) URL to the single-cell CSV (.csv/.csv.gz)")
    ap.add_argument("--smoke", action="store_true", help="run on a synthetic fixture")
    ap.add_argument("--label-col", default="ClusterName")
    ap.add_argument("--group-col", default="patients")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--context", type=int, default=10000,
                    help="TabPFN in-context training budget (stratified subsample)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="results")
    ap.add_argument("--leakage-check", action="store_true",
                    help="also run a random (cell-level) split to quantify leakage")
    ap.add_argument("--dry-run", action="store_true",
                    help="pre-flight checks only (env, data, weights) — no CV")
    ap.add_argument("--sample-rows", type=int, default=0,
                    help="read only the first N rows (fast --dry-run on huge files)")
    args = ap.parse_args()

    if args.smoke:
        print("[mode] SMOKE — synthetic fixture (no external data)")
        df = synthetic()
    elif args.csv:
        df = load_table(args.csv, nrows=args.sample_rows or None)
    else:
        ap.error("provide --csv PATH/URL or --smoke")

    if args.dry_run:
        raise SystemExit(dry_run(df, args))

    if args.label_col not in df.columns:
        raise SystemExit(f"label column {args.label_col!r} not found; "
                         f"columns are: {list(df.columns)[:40]}")
    markers = detect_schema(df, args.label_col, args.group_col, META_COLS_DEFAULT)
    if not markers:
        raise SystemExit("no marker columns detected — check --label-col/--group-col")
    df = df.dropna(subset=[args.label_col, args.group_col]).reset_index(drop=True)

    res, pcf1, classes, y, specs, kind, names = run(
        df, markers, args.label_col, args.group_col,
        args.folds, args.context, args.seed, random_split=False)
    summarize(res, pcf1, classes, y, specs, kind, args.out, names)

    if args.leakage_check:
        print("\n[leakage-check] running random cell-level split for comparison...")
        r2, p2, c2, y2, s2, k2, n2 = run(
            df, markers, args.label_col, args.group_col,
            args.folds, args.context, args.seed, random_split=True)
        summarize(r2, p2, c2, y2, s2, k2, args.out + "_randomsplit", n2)


if __name__ == "__main__":
    main()
