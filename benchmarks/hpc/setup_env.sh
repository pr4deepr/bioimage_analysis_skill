#!/usr/bin/env bash
# One-time setup for the TabPFN benchmark on HPC. Run on a LOGIN NODE.
#
#   bash setup_env.sh
#
# Creates the conda env and pre-caches TabPFN's gated weights so the (offline)
# compute node can run. Edit the CONFIG block for your cluster.
set -euo pipefail

# ------------------------------ CONFIG ------------------------------------- #
ENV_NAME="tabpfn-bench"
# Shared, node-visible cache for HuggingFace weights (persist across jobs):
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
# Your HuggingFace read token (accept terms first at
# https://huggingface.co/Prior-Labs/tabpfn_3). Prefer setting it in your shell:
#   export HF_TOKEN=hf_xxx
# --------------------------------------------------------------------------- #

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer mamba if available (faster), else conda.
if command -v mamba >/dev/null 2>&1; then CONDA=mamba; else CONDA=conda; fi
echo "[setup] using $CONDA"

if conda env list | grep -qE "^\s*${ENV_NAME}\s"; then
  echo "[setup] env '${ENV_NAME}' already exists — skipping create"
else
  echo "[setup] creating env '${ENV_NAME}' from environment.yml"
  "$CONDA" env create -f "$HERE/environment.yml"
fi

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "[setup] versions:"
python -c "import torch,sklearn,xgboost,tabpfn; print('torch',torch.__version__,'cuda?',torch.cuda.is_available()); print('sklearn',sklearn.__version__,'xgboost',xgboost.__version__,'tabpfn',tabpfn.__version__)"

echo "[setup] pre-fetching TabPFN weights into HF_HOME=$HF_HOME"
mkdir -p "$HF_HOME"
python "$HERE/prefetch_tabpfn.py"

echo "[setup] done. Submit the job with:  sbatch run_benchmark.slurm /path/to/main_fcs_csv.csv"
