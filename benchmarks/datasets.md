# Spatial-proteomics datasets for phenotyping benchmarks

A curated set of **publicly available, per-cell, cell-type-labelled** multiplexed
spatial-proteomics datasets to test the phenotyping harness on — beyond the
Schürch CRC CODEX case study. Each row has what the harness needs: a per-cell
table of **marker intensities**, a **cell-type label** column, a **sample/patient**
column (for grouped splits), and usually spatial coordinates.

Selection criteria: (1) segmented single-cell table available (not just images);
(2) published cell-type / phenotype labels; (3) multiple patients or samples;
(4) a real download. Platforms span CODEX, IMC, MIBI-TOF, and CyCIF/Orion so the
benchmark probes robustness across technologies and tissues, not one slide.

## Summary

| Dataset | Platform | Tissue | Markers | Cell types | Cells | Samples | Label field | Access |
|---|---|---|---|---|---|---|---|---|
| **Schürch 2020** (current) | CODEX | CRC | 56 | 28 | ~0.25 M | 35 pts | `ClusterName` | Mendeley `mpjzbtfgfr` |
| **Jackson 2020** | IMC | Breast | ~35 (45 ch) | ~classes/metaclusters | 285,851 | ~350 pts (Basel+Zurich) | cluster/metacluster | Zenodo `3518284` |
| **Damond 2019** | IMC | Pancreas (T1D) | 33 | islet/immune/exocrine/stromal types | ~0.25 M (full) | 12 T1D + 6 ctrl | `cell_type`/`cell_category` | `imcdatasets` / Mendeley `cydmwsfztj` |
| **Hoch 2022** | IMC | Melanoma | ~40 | immune/tumor/stromal types | ~0.5 M | 69 pts | cell type | `imcdatasets` / Zenodo |
| **Keren 2018** | MIBI-TOF | TNBC (breast) | 36 | ~17 immune/tumor types | ~200 K | 41 pts | cell type | Ionpath MIBI-Share / Angelo lab |
| **Risom 2022** | MIBI-TOF | Breast DCIS | 37 | 16 cell classes | 69,151 | 79 resections | cell class | HTAN / Angelo lab |
| **Hickey 2023** | CODEX | Intestine | 57 | ~20+ types | ~2.6 M | 8–9 donors, 8 regions | cell type | Dryad `pk0p2ngrf` |
| **Lin 2023 (Orion)** | CyCIF/Orion | CRC | 18 | tumor/immune/stromal types | large | 74 resections | cell type | tissue-atlas / AWS S3 |
| **Hartmann (squidpy `mibitof`)** | MIBI-TOF | CRC | 36 | `Cluster` | 3,309 | 3 donors | `Cluster` | `sq.datasets.mibitof()` |
| **Jackson subset (squidpy `imc`)** | IMC | Breast | 34 | `cell type` | 4,668 | 1 image | `cell type` | `sq.datasets.imc()` |

*Counts are from the source publications/packages; verify against the file you
download (some entries are cohort totals, some are curated subsets).*

## Easiest programmatic sources (recommended starting point)

Two ecosystems package several of these as ready-to-load, already-labelled objects
— far less work than raw portal downloads.

**Bodenmiller `imcdatasets` (R / Bioconductor)** — curated, labelled IMC datasets
as `SpatialExperiment` objects; export to a harness CSV in a few lines:

```r
# BiocManager::install("imcdatasets")
library(imcdatasets); library(SummarizedExperiment)
spe <- Damond_2019_Pancreas(data_type = "spe")   # or JacksonFischer_2020_BreastCancer(), HochSchulz_2022_Melanoma()
df <- as.data.frame(t(assay(spe, "exprs")))       # cells x markers
cd <- as.data.frame(colData(spe))
df$ClusterName <- cd$cell_type                    # label (check colData names)
df$patients    <- cd$patient_id                   # group
df[c("X:X","Y:Y")] <- spatialCoords(spe)
write.csv(df, "damond_pancreas.csv", row.names = FALSE)
```
Datasets in the package include `Damond_2019_Pancreas`, `JacksonFischer_2020_BreastCancer`,
`HochSchulz_2022_Melanoma`, `ZanotelliBodenmiller_2020_Spheroids`, and an IMMUcan example.

**squidpy (Python)** — small, fully-labelled AnnData objects, great for a fast
end-to-end smoke run of the whole pipeline:

```python
import squidpy as sq
adata = sq.datasets.mibitof()   # 3309 cells, 36 markers, obs["Cluster"], obs["library_id"]
# adata = sq.datasets.imc()     # 4668 cells, 34 markers, obs["cell type"]
```
Then convert with `prepare_dataset.py` (below) and run the harness.

## Converting to the harness format

`tabpfn_phenotyping_benchmark.py` reads a flat CSV: marker columns + a label
column + a group column (+ optional `X:X`/`Y:Y`). Use
[`prepare_dataset.py`](./prepare_dataset.py) to turn an AnnData `.h5ad` into that
CSV:

```bash
python prepare_dataset.py --h5ad mibitof.h5ad --label-obs Cluster \
    --group-obs library_id --out mibitof_cells.csv
# then:
python tabpfn_phenotyping_benchmark.py --csv mibitof_cells.csv \
    --label-col cell_label --group-col group --dry-run
```
For R/`SpatialExperiment` objects, export a CSV as shown above (or `saveRDS` →
CSV). The harness is schema-robust: any numeric columns that aren't the known
metadata become markers.

## Access / network notes

- **On HPC or a workstation**, all of the above are directly downloadable.
- **Inside a restricted environment** (e.g. Claude Code on the web — only PyPI and
  GitHub reachable), Zenodo / Dryad / Mendeley / Ionpath / scverse download hosts
  are blocked, so fetch these on your cluster and `scp`/`rsync` them, or mirror a
  file into a GitHub repo and pass its raw/LFS URL to `--csv` (see `README.md`).
- Licenses vary (mostly CC-BY / CC0 for the data deposits) — check each deposit
  before redistribution; this catalog links to sources rather than vendoring data.

## Sources

- Schürch 2020, *Cell* — CRC CODEX: [Mendeley `mpjzbtfgfr`](https://data.mendeley.com/datasets/mpjzbtfgfr/1)
- Jackson & Fischer 2020, *Nature* — breast IMC: [Zenodo `3518284`](https://zenodo.org/records/3518284)
- Damond 2019, *Cell Metabolism* — pancreas/T1D IMC: [imcdatasets](https://bodenmillergroup.github.io/imcdatasets/reference/Damond_2019_Pancreas.html) · [Mendeley `cydmwsfztj`](https://data.mendeley.com/datasets/cydmwsfztj/2)
- Hoch 2022, *Science Immunology* — melanoma IMC: [imcdatasets](https://bodenmillergroup.github.io/imcdatasets/)
- Keren 2018, *Cell* — TNBC MIBI-TOF: [paper](https://www.cell.com/fulltext/S0092-8674(18)31100-0) · [Ionpath MIBI-Share](https://mibi-share.ionpath.com)
- Risom 2022, *Cell* — DCIS MIBI-TOF: [paper](https://scholar.google.com/scholar_lookup?doi=10.1016/j.cell.2021.12.023)
- Hickey 2023, *Nature* — intestine CODEX (HuBMAP): [Dryad `pk0p2ngrf`](https://datadryad.org/dataset/doi:10.5061/dryad.pk0p2ngrf)
- Lin 2023, *Cell* — Orion CRC CyCIF: [tissue-atlas](https://www.tissue-atlas.org/atlas-datasets/lin-chen-campton-2023/) · [labsyspharm/orion-crc](https://github.com/labsyspharm/orion-crc)
- squidpy datasets: [`mibitof`](https://squidpy.readthedocs.io/en/stable/api/squidpy.datasets.mibitof.html) · [`imc`](https://squidpy.readthedocs.io/en/stable/api/squidpy.datasets.imc.html)
- Bodenmiller [`imcdatasets`](https://bioconductor.org/packages/release/data/experiment/html/imcdatasets.html) (R/Bioconductor)
