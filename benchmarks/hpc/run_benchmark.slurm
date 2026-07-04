#!/usr/bin/env bash
#SBATCH --job-name=tabpfn-bench
#SBATCH --partition=gpu            # <-- CHANGE to your GPU partition
#SBATCH --account=CHANGE_ME        # <-- CHANGE to your allocation/account (or remove)
#SBATCH --gres=gpu:1               # 1 GPU (remove for a CPU-only run)
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=tabpfn-bench-%j.out
#SBATCH --error=tabpfn-bench-%j.err
#
# Submit AFTER running setup_env.sh on a login node (which caches TabPFN weights).
#
#   sbatch run_benchmark.slurm /path/to/main_fcs_csv.csv [OUT_DIR]
#
# Runs the patient-grouped benchmark (baselines + TabPFN/ManyClassClassifier).
set -euo pipefail

# ------------------------------ CONFIG ------------------------------------- #
ENV_NAME="tabpfn-bench"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"  # must match setup_env.sh
export HF_HUB_OFFLINE=1                                # compute node has no internet
export TOKENIZERS_PARALLELISM=false
# If your cluster exposes CUDA via modules, load it here (match environment.yml):
# module load cuda/12.1
# --------------------------------------------------------------------------- #

DATA_CSV="${1:?usage: sbatch run_benchmark.slurm /path/to/main_fcs_csv.csv [OUT_DIR]}"
OUT_DIR="${2:-results_${SLURM_JOB_ID:-local}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../tabpfn_phenotyping_benchmark.py"

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "[run] node=$(hostname)  data=$DATA_CSV  out=$OUT_DIR"
python -c "import torch; print('[run] CUDA available:', torch.cuda.is_available())"

srun python "$SCRIPT" \
    --csv "$DATA_CSV" \
    --out "$OUT_DIR" \
    --folds 5 \
    --context 10000 \
    --leakage-check

echo "[run] done -> $OUT_DIR/{leaderboard.csv,per_class_f1.csv,results.md}"
