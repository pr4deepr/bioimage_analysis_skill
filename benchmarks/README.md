# TabPFN spatial-proteomics benchmark

Companion to [`tabpfn-spatial-proteomics-evaluation.md`](./tabpfn-spatial-proteomics-evaluation.md).
The report is the analysis; this is the runnable protocol (§6 of the report):
patient-grouped cross-validation of TabPFN (+ `ManyClassClassifier`) against
standard baselines for per-cell phenotyping, with imbalance-aware metrics,
calibration (ECE), and wall-clock timing.

## Files

- `tabpfn_phenotyping_benchmark.py` — the harness (data loading, schema
  detection, grouped CV, models, metrics, reporting; includes a synthetic
  `--smoke` fixture).
- `requirements.txt` — dependencies.
- `tabpfn-spatial-proteomics-evaluation.md` — the written evaluation / verdict.

## Install

```bash
pip install -r requirements.txt
```

Baselines (logistic regression, kNN, random forest, XGBoost) run with the core
stack alone. TabPFN additionally needs `torch` and **gated model weights** — see
the note below.

## Quick check (no data needed)

```bash
python tabpfn_phenotyping_benchmark.py --smoke --folds 3
```

Runs the whole pipeline on a synthetic fixture that mirrors the CRC CODEX schema
(56 markers, 28 imbalanced classes, patient groups). Scores are near-perfect
because the fixture is trivially separable — it validates the plumbing, not model
quality.

## Run on the real data

The dataset is `main_fcs_csv.csv` (Schürch 2020 CRC CODEX; Mendeley
`mpjzbtfgfr`). Point `--csv` at a local path or an `http(s)` URL (`.csv` or
`.csv.gz`):

```bash
# local file
python tabpfn_phenotyping_benchmark.py --csv main_fcs_csv.csv --out results --leakage-check

# straight from a GitHub LFS mirror (public repo), no git-lfs client needed:
python tabpfn_phenotyping_benchmark.py \
  --csv https://media.githubusercontent.com/media/<owner>/<repo>/<branch>/main_fcs_csv.csv \
  --out results --leakage-check
```

Key flags: `--folds` (grouped CV folds), `--context` (TabPFN in-context training
budget; stratified subsample, default 10000), `--label-col`/`--group-col`
(defaults `ClusterName`/`patients`), `--leakage-check` (also runs a random
cell-level split to quantify the leakage gap — expect it to look better and be
misleading, which is the point).

Outputs (in `--out`): `leaderboard.csv`, `per_class_f1.csv` (sorted by support,
rare classes first), `results.md`.

## Important: TabPFN weights are gated

TabPFN downloads its checkpoint from HuggingFace (`Prior-Labs/tabpfn_*`), which is
**gated** (accept terms + authenticate) and is **blocked in restricted network
environments** (e.g. Claude Code on the web, where only package registries and
GitHub are reachable). Consequences:

- **Baselines run anywhere.** The harness catches the TabPFN weight-load failure
  per-fold and still produces the baseline leaderboard; TabPFN then appears under
  *"Models available but with 0 successful folds"* in `results.md`.
- **To actually benchmark TabPFN**, run where HuggingFace is reachable: visit
  `https://huggingface.co/Prior-Labs/tabpfn_3`, accept the terms, then
  `hf auth login` or `export HF_TOKEN=...` before running. A GPU is strongly
  recommended — `ManyClassClassifier` runs many TabPFN inferences per prediction
  (ECOC codebook), so CPU on ~10⁵ cells is slow.

## What the harness implements (and why)

- **Patient-grouped splits** (`GroupKFold` on `patients`) — cells within a
  patient/region are correlated; random splits leak and inflate every model.
- **Stratified context subsampling** — TabPFN's context is capped (~10k rows);
  the subsample preserves rare classes as far as possible.
- **`ManyClassClassifier`** — output-coding wrapper that lets TabPFN exceed its
  10-class head (the CRC data has 28 `ClusterName` types). Also a `tabpfn_coarse`
  model that collapses to ≤10 lineages for vanilla TabPFN.
- **Metrics** — balanced accuracy and macro-F1 (imbalance-robust headline),
  per-class F1 by support, ROC-AUC (OvR), ECE (calibration), and fit+predict
  wall-clock.
- **Preprocessing** — per-marker `arcsinh` + z-score, fit inside each fold.

See the evaluation report for the full rationale and the go/no-go recommendation.
