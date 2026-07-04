# Evaluating TabPFN for spatial-proteomics cell phenotyping

*An evidence-grounded feasibility review. Case study: the Schürch et al. 2020 colorectal-cancer
CODEX dataset. Scope: per-cell phenotyping (assigning each cell a type from its multiplexed
marker intensities). This is a written evaluation, not a benchmark harness.*

---

## 1. Verdict (TL;DR)

**Conditional GO — TabPFN is a credible, fast, tuning-free baseline for CODEX/IMC cell phenotyping,
but *only* when paired with `ManyClassClassifier` from `tabpfn-extensions`.**

- The single hard blocker for this task is TabPFN v2's **10-class architectural cap**. Real
  phenotyping panels have far more types — the case-study dataset has **28** cell types in its
  `ClusterName` column. Vanilla TabPFN cannot fit this at all.
- `tabpfn-extensions`' **`ManyClassClassifier`** (an output-coding / ECOC wrapper) lifts that cap by
  decomposing the 28-class problem into a codebook of ≤10-class TabPFN sub-problems. This turns
  "impossible" into "viable" — at the cost of running many TabPFN inferences per prediction.
- The two remaining frictions are *manageable, not blocking*: the ~10⁵ cells vastly exceed TabPFN's
  ~10k context limit (solve by **stratified context subsampling** — fit on a few thousand cells,
  predict the rest), and 56 markers sit comfortably under the 500-feature limit.
- **The biggest risk is not TabPFN, it's the evaluation protocol.** Cells are strongly correlated
  within a patient/tissue region; a naïve random train/test split leaks and inflates accuracy for
  *every* method. Any honest benchmark must use **patient-level grouped splits**.

**Where TabPFN is most compelling here:** rapid, no-hyperparameter baselining; small-cohort or
few-marker settings; and as a probabilistic, well-calibrated second opinion on an existing gating /
clustering pipeline. **Where it is weakest:** raw throughput on millions of cells, and any claim that
it "beats" tuned gradient-boosted trees on large tabular data — the literature does not support that
at this scale, and the `ManyClassClassifier` decomposition adds real latency.

**Recommendation:** worth a proper empirical benchmark (protocol in §6). Do not adopt it as a
drop-in phenotyper without first measuring the `ManyClassClassifier` accuracy/runtime trade-off on a
patient-held-out split.

> **Grounding note.** The dataset *schema* below (column names, the 28 cell types, patient/region
> structure) was read directly from the study's own analysis notebook. The raw single-cell CSV
> (`main_fcs_csv.csv`) is hosted only on Mendeley, which is unreachable from this environment, so
> per-class cell *frequencies* were **not** independently recomputed here; cell counts are quoted
> from the publication and flagged as such.

---

## 2. The task and the dataset

**Per-cell phenotyping** is the workhorse step of a multiplexed-imaging (CODEX, IMC, MIBI, CyCIF)
pipeline: after segmentation and per-cell marker quantification, each cell must be assigned a type
(tumor, CD8⁺ T cell, macrophage subset, stroma, …) from its ~dozens of protein-marker intensities.
It is a supervised, tabular, multi-class classification problem — exactly TabPFN's shape, except for
the class count and row count.

**Case-study dataset — Schürch et al. 2020, CRC CODEX** (Mendeley `mpjzbtfgfr`; TCIA
`CRC_FFPE-CODEX_CELLNEIGHS`; analysis code in `nolanlab/NeighborhoodCoordination`):

| Property | Value | Source |
|---|---|---|
| Patients | 35 (17 CLR/"Follicular", 18 DII/"Diffuse") | publication |
| Tissue regions | 140 (four TMA spots/patient) | publication |
| Protein markers | 56 | publication |
| Cells | ~2–3 × 10⁵ (order 10⁵; exact count not independently verified here) | publication |
| **Cell types (`ClusterName`)** | **28** | study notebook (verified) |

**Column schema** (from `Neighborhoods/Neighborhood Identification.ipynb`):
`X:X`, `Y:Y` (spatial coordinates); `File Name` (tissue region, e.g. `reg064_A`); `ClusterName`
(cell-type label); `patients`; `groups` (1 = CLR, 2 = DII); the 56 marker-intensity columns; and a
derived `neighborhood10`.

**The 28 `ClusterName` cell types:** tumor cells; CD11c⁺ DCs; tumor cells / immune cells; smooth
muscle; lymphatics; adipocytes; undefined; CD4⁺ T cells CD45RO⁺; CD8⁺ T cells; CD68⁺CD163⁺
macrophages; plasma cells; Tregs; immune cells / vasculature; stroma; CD68⁺ macrophages GzmB⁺;
vasculature; nerves; CD11b⁺CD68⁺ macrophages; granulocytes; CD68⁺ macrophages; NK cells; CD11b⁺
monocytes; immune cells; CD4⁺ T cells GATA3⁺; CD163⁺ macrophages; CD3⁺ T cells; CD4⁺ T cells; B
cells.

Two things about this label set matter for the evaluation:
1. **28 ≫ 10** — the class count is the crux of the whole analysis (§4.1).
2. Several labels are **ambiguous or hierarchical** ("undefined", "tumor cells / immune cells",
   "immune cells / vasculature", plus many correlated macrophage subsets). This caps the achievable
   accuracy of *any* classifier and shapes how the metrics should be read (§4.5).

---

## 3. TabPFN: capabilities and hard constraints

TabPFN (Prior-data Fitted Network) is a transformer pre-trained on millions of synthetic tabular
tasks that performs **in-context learning**: it takes the entire labelled training set as context in
a single forward pass and predicts the test rows — no gradient training, no hyperparameter tuning.
Its v2 release (Hollmann et al., *Nature*, 2025) is strong on small/medium tabular data and produces
**well-calibrated** probabilities.

**The constraints that govern this task:**

| Constraint | TabPFN v2 | Implication for CODEX phenotyping |
|---|---|---|
| Max classes | **10 (hard, architectural)** | 28 cell types → **cannot fit** without an extension |
| Training/context rows | ~10,000 (v2.5 ≈ 50,000) | ~10⁵ cells → must **subsample the context** |
| Features | ~500 | 56 markers → **no problem** |
| Compute | transformer forward pass; GPU strongly preferred | large predict sets → batch inference; watch latency |
| Training | none (in-context) | zero tuning is the headline upside |

The 10-class limit is not a soft guideline — it is the size of the model's output head
(`MAX_NUMBER_OF_CLASSES`). This is the fact that decides whether TabPFN is usable for phenotyping at
all, and the reason the rest of this report leans on `tabpfn-extensions`.

---

## 4. Fit analysis — frictions specific to cell phenotyping

### 4.1 Class count — the crux (blocking without an extension)

28 cell types exceed the 10-class head. Options, best first:

- **`ManyClassClassifier` (recommended).** Output-coding wrapper (see §5) that decomposes 28 classes
  into a codebook of ≤10-class TabPFN sub-problems and reassembles the full posterior. Keeps all 28
  native labels; costs multiple TabPFN inferences per prediction.
- **Coarse lineage grouping.** Collapse the 28 types into ≤10 lineages (epithelial/tumor, T cell,
  B/plasma, myeloid/macrophage, granulocyte, NK, vascular/lymphatic, stroma/muscle, nerve/other).
  Fits vanilla TabPFN and is often what a downstream neighborhood analysis actually needs — but
  throws away the fine subsets that make spatial proteomics valuable.
- **Hierarchical two-stage** (lineage with TabPFN, then subset within lineage) — more moving parts,
  more places to leak.
- **TabPFN v2.5** raises the *row* limit but does **not** remove the 10-class cap; it is not a fix
  here on its own.

### 4.2 Sample count — manageable via context subsampling

~10⁵ cells ≫ TabPFN's ~10k context. Standard pattern: draw a **stratified** subsample (a few
thousand cells, sampled to preserve rare types) as the in-context "training" set, then predict all
remaining cells in batches. Key study to run: **sensitivity of accuracy — especially rare-class
recall — to context size and sampling scheme.** Rare types (NK cells, nerves, adipocytes) are the
first casualties of naïve subsampling.

### 4.3 Feature count — a non-issue

56 markers ≪ 500. No dimensionality handling required. (`interpretability` feature selection, §5,
could still trim the panel for speed/robustness, but it is optional.)

### 4.4 Leakage — the real methodological trap

Cells from one patient/region share staining batch, tissue architecture, and marker background, so
they are far from i.i.d. A random cell-level split places near-duplicate neighbors in both train and
test and **inflates accuracy for every method**, TabPFN included. Because TabPFN literally memorizes
its context, it is at least as exposed to this as trees. **Mandatory:** patient-level *grouped*
splits / grouped CV (`GroupKFold`/`LeaveOneGroupOut` on `patients`). Report the naïve-vs-grouped gap
— it is usually large and is the number a reviewer will ask for.

### 4.5 Label provenance — read the accuracy accordingly

`ClusterName` is not gold-standard truth: it was produced by the authors' own unsupervised
clustering plus manual annotation (hence "undefined" and the compound labels). So the benchmark
measures **"can TabPFN reproduce this clustering from marker intensities,"** not "does TabPFN find
the biologically correct type." High accuracy mostly means the labels were linearly/near-linearly
recoverable from markers; low accuracy on ambiguous classes is partly irreducible label noise. Favor
**per-class F1** and **confusion structure** over headline accuracy, and expect the compound/undefined
classes to bound the ceiling.

### 4.6 Batch effects and normalization

Marker intensities drift across regions/patients. Normalization (arcsinh/z-score per marker, or per
region) affects TabPFN and baselines alike; fix one scheme and apply it inside the CV fold to avoid
leakage. TabPFN's `unsupervised` outlier module (§5) can pre-flag segmentation artifacts before
phenotyping.

---

## 5. TabPFN ecosystem — `tabpfn-extensions` (PriorLabs)

The extensions package is what makes TabPFN practical here. Modules confirmed in the current source
tree (`src/tabpfn_extensions/`): `many_class`, `interpretability`, `unsupervised`, `embedding`,
`tabebm`, `pval_crt`, `survival`, `cp_missing_data`, `scoring`, `benchmarking`, `post_hoc_ensembles`,
`hpo`, `misc`.

| Module | What it does | Relevance to phenotyping |
|---|---|---|
| **`many_class`** | `ManyClassClassifier`: output-coding (ECOC/codebook) wrapper over a base TabPFN | **Enabling** — lifts the 10-class cap so all 28 types fit. Central to the GO verdict. |
| `interpretability` | SHAP values + feature selection | Which markers drive each phenotype; can trim the 56-marker panel. |
| `unsupervised` | outlier / anomaly detection, data generation | QC step: flag mis-segmented / artefactual cells before phenotyping. |
| `tabebm` | energy-based synthetic-data augmentation | Oversample rare cell types to fight class imbalance. |
| `embedding` | extract TabPFN sample embeddings | Cell embeddings for downstream clustering / neighborhood analysis. |
| `survival`, `pval_crt`, `cp_missing_data`, `scoring` | survival models, feature p-values, missing-data conformal prediction, metrics | Adjacent (e.g. patient-level survival), not core to per-cell phenotyping. |
| `post_hoc_ensembles` (AutoTabPFN), `hpo` (TunedTabPFN) | ensembling / tuning | **Deprecated / scheduled for removal — do not build on these.** |

**`ManyClassClassifier` API (from source).**

```python
from tabpfn import TabPFNClassifier
from tabpfn_extensions.many_class import ManyClassClassifier

clf = ManyClassClassifier(
    estimator=TabPFNClassifier(),   # base ≤10-class model
    alphabet_size=None,             # inferred from the checkpoint's MAX_NUMBER_OF_CLASSES (=10)
    n_estimators=None,              # codebook size; auto from #classes & alphabet if None
    n_estimators_redundancy=4,      # extra codebook columns for error-correction
    random_state=0,
)
clf.fit(X_context, y_context)       # 28-class labels OK
proba = clf.predict_proba(X_test)
```

It builds an error-correcting **codebook**: each "estimator" is a ≤10-way TabPFN over a grouping of
the 28 classes, and predictions are decoded across the codebook (redundancy = error correction). The
**cost** is `n_estimators` TabPFN inferences per prediction — the runtime/accuracy knob to measure in
the benchmark. Note: **no `rf_pfn` / random-forest-TabPFN module exists in the current tree**, so
large-data handling relies on context subsampling (§4.2) and/or v2.5's higher row limit, not a
bundled tree wrapper.

---

## 6. Recommended benchmark protocol

To turn this feasibility review into a decision, run:

- **Task:** predict `ClusterName` (28 classes) from the 56 marker-intensity columns.
- **Models:**
  - TabPFN + `ManyClassClassifier` (primary).
  - TabPFN on a ≤10-class coarse-lineage relabeling (to isolate the extension's overhead/accuracy cost).
  - Baselines: **RandomForest**, **XGBoost/LightGBM** (tuned — the real bar to clear), **logistic
    regression** (linear reference), **kNN** (gating-like reference).
- **Split:** patient-level **`GroupKFold`** (or `LeaveOneGroupOut`) on `patients`. Also report the
  naïve random-split number *alongside* it to quantify leakage (§4.4).
- **Normalization:** fixed scheme (e.g. per-marker arcsinh + z-score) fit **inside** each fold.
- **Context handling:** stratified subsample to TabPFN's row budget; sweep context size
  (e.g. 1k / 5k / 10k) and record the rare-class effect.
- **Metrics:** **balanced accuracy** and **macro-F1** (headline, imbalance-robust), **per-class F1**
  and the **confusion matrix** (where does it fail — expect the compound/undefined classes),
  **ROC-AUC OvR**, **calibration/ECE** (TabPFN's advertised strength), and **wall-clock**
  fit+predict per method (where `ManyClassClassifier` will cost the most).
- **Repeats:** multiple seeds / CV folds → report mean ± CI, not point estimates.
- **Rare-class focus:** separate table for the low-frequency types — that is where subsampling and
  the codebook are most likely to hurt.

---

## 7. Recommendation and trade-offs

**Adopt for evaluation; do not yet adopt as a drop-in phenotyper.** Concretely:

- **Do run the §6 benchmark.** The interesting, decision-relevant question is not "does TabPFN work"
  (with `ManyClassClassifier` it *runs*), but **"how close does it get to a tuned XGBoost on a
  patient-held-out split, and at what latency, with better calibration?"**
- **Best-fit scenarios for TabPFN here:** zero-tuning first-pass phenotyping; small cohorts or small
  marker panels; well-calibrated probabilities as a second opinion / QC flag over an existing
  gating or clustering pipeline; coarse-lineage typing (fits vanilla TabPFN, no extension needed).
- **Costs / caveats to weigh:** `ManyClassClassifier` multiplies inference cost by the codebook size;
  ~10⁵–10⁶ cells need batched prediction and a GPU; the "TabPFN beats GBDTs" narrative is a
  *small-data* result and should not be assumed at CODEX scale; and the labels themselves are
  clustering-derived, so treat accuracy as agreement-with-a-pipeline, not ground truth.

**Suggested next steps:** (1) obtain `main_fcs_csv.csv` from Mendeley into the working environment;
(2) implement the §6 protocol as a small notebook; (3) report the grouped-split leaderboard with
calibration and runtime; (4) if TabPFN+`ManyClassClassifier` lands within a few points of tuned
XGBoost with better calibration and acceptable latency, promote it to a recommended baseline.

---

## 8. Sources

- Schürch et al. (2020), *Coordinated Cellular Neighborhoods Orchestrate Antitumoral Immunity at the
  Colorectal Cancer Invasive Front*, **Cell**.
  [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0092867420308709) ·
  [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7479520/)
- Dataset: Mendeley Data [`mpjzbtfgfr`](https://data.mendeley.com/datasets/mpjzbtfgfr/1); TCIA
  [`CRC_FFPE-CODEX_CELLNEIGHS`](https://www.cancerimagingarchive.net/collection/crc_ffpe-codex_cellneighs/).
- Analysis code / schema:
  [`nolanlab/NeighborhoodCoordination`](https://github.com/nolanlab/NeighborhoodCoordination)
  (`Neighborhoods/Neighborhood Identification.ipynb` — verified column names and the 28 `ClusterName`
  types).
- TabPFN v2: Hollmann, Müller, et al. (2025), *Accurate predictions on small data with a tabular
  foundation model*, **Nature**. Overview: [TabPFN — Wikipedia](https://en.wikipedia.org/wiki/TabPFN).
- Extensions: [`PriorLabs/tabpfn-extensions`](https://github.com/PriorLabs/tabpfn-extensions)
  (`many_class.ManyClassClassifier` — signature and ECOC/codebook behavior verified from source).
- Tabular-foundation-model landscape / limits:
  [The state of Tabular Foundation Models (2026)](https://mindfulmodeler.substack.com/p/the-state-of-tabular-foundation-models);
  [TabICL (large-data ICL)](https://arxiv.org/html/2502.05564v1).
- Context on CODEX cell typing / dataset use:
  [Strategies for Accurate Cell Type Identification in CODEX (PMC)](https://ncbi.nlm.nih.gov/pmc/articles/PMC8415085);
  [TopKAT, Patterns 2025](https://www.cell.com/patterns/fulltext/S2666-3899\(25\)00304-6).
