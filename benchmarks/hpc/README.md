# Running the benchmark on HPC

Scripts to run `../tabpfn_phenotyping_benchmark.py` on a SLURM cluster.

## Which environment to create

A **conda/mamba environment named `tabpfn-bench`** (Python 3.11) with a
**CUDA-matched PyTorch**, plus `tabpfn`, `tabpfn-extensions`, `xgboost`,
`scikit-learn`, `pandas`, `numpy`, `matplotlib`, `tabulate`. The full spec is in
[`environment.yml`](./environment.yml).

- **Use a GPU node.** `ManyClassClassifier` runs many TabPFN inferences per
  prediction (ECOC codebook over 28 classes), so CPU on ~10⁵ cells is slow.
  A single GPU, 8 CPUs, 32 GB RAM, and a few hours is a reasonable request.
- **Match PyTorch to the cluster CUDA.** If the default `torch` wheel mismatches
  the node driver, uncomment the `--extra-index-url` line in `environment.yml`
  and set the tag (`cu121`, `cu124`, …) to match `nvidia-smi` on a GPU node
  (or `module load cuda/...`). A CPU-only run works too (cpu wheel) — just slower.
- **Baselines need none of the GPU/TabPFN parts** — logreg/kNN/RF/XGBoost run on
  the core stack alone, so you get a leaderboard even if TabPFN is unavailable.

## The one HPC gotcha: TabPFN's gated, offline-unfriendly weights

TabPFN downloads a **gated** checkpoint from HuggingFace
(`Prior-Labs/tabpfn_3`). Compute nodes are usually offline, so you must cache the
weights **once on a login node** and point the job at that cache:

1. Accept the terms in a browser: <https://huggingface.co/Prior-Labs/tabpfn_3>
2. On a login node: `export HF_TOKEN=hf_xxx` and
   `export HF_HOME=/shared/path/hf` (a path the compute nodes can read).
3. Run `setup_env.sh` — it creates the env and pre-fetches the weights into
   `HF_HOME`.
4. The job (`run_benchmark.slurm`) sets `HF_HUB_OFFLINE=1` and reuses that cache.

## Workflow

```bash
# on a LOGIN NODE (has internet)
export HF_TOKEN=hf_xxx
export HF_HOME=$HOME/.cache/huggingface   # or a shared/scratch path
bash setup_env.sh                          # create env + cache TabPFN weights

# submit the job (GPU node)
sbatch run_benchmark.slurm /path/to/main_fcs_csv.csv results_crc
```

Edit the `#SBATCH` header in [`run_benchmark.slurm`](./run_benchmark.slurm) for
your cluster: `--partition`, `--account`, and (if CUDA comes from modules) the
`module load cuda/...` line. Outputs land in the given `OUT_DIR`:
`leaderboard.csv`, `per_class_f1.csv`, `results.md`.

## Getting the data onto the cluster

`main_fcs_csv.csv` (Schürch 2020 CRC CODEX, Mendeley `mpjzbtfgfr`). Either
`scp`/`rsync` it to the cluster and pass the local path, or pass an
`http(s)` URL directly (e.g. a GitHub `media.githubusercontent.com` LFS link) —
the harness downloads `--csv URL` itself, and reads `.csv.gz` transparently.

## Files

| File | Purpose |
|------|---------|
| `environment.yml` | conda/mamba env spec (`tabpfn-bench`) |
| `setup_env.sh` | create env + pre-cache TabPFN weights (login node) |
| `prefetch_tabpfn.py` | the weight-caching step (called by `setup_env.sh`) |
| `run_benchmark.slurm` | SLURM job: activate env, run the benchmark on a GPU node |
