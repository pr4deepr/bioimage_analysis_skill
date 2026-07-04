#!/usr/bin/env python3
"""Pre-download TabPFN's gated weights into the shared HF cache.

Run this ON A LOGIN NODE (or anywhere with internet + your HuggingFace token),
BEFORE submitting the SLURM job. Compute nodes are usually offline; caching the
weights here lets the job run with HF_HUB_OFFLINE=1.

Prerequisites (one-time):
  1. Accept the model terms in a browser: https://huggingface.co/Prior-Labs/tabpfn_3
  2. export HF_TOKEN=hf_xxx           # a read token from huggingface.co/settings/tokens
  3. export HF_HOME=/shared/path/hf   # a path visible from the compute nodes

Then:  python prefetch_tabpfn.py
"""
import os
import sys

import numpy as np


def main() -> int:
    hf_home = os.environ.get("HF_HOME", "(unset — using default ~/.cache/huggingface)")
    if not (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")):
        print("WARNING: no HF_TOKEN set — gated download will fail. "
              "Set HF_TOKEN and accept terms at "
              "https://huggingface.co/Prior-Labs/tabpfn_3", file=sys.stderr)
    print(f"[prefetch] HF_HOME = {hf_home}")

    from tabpfn import TabPFNClassifier

    # A trivial fit triggers the checkpoint download into the HF cache.
    X = np.random.RandomState(0).randn(32, 5)
    y = (X[:, 0] > 0).astype(int)
    print("[prefetch] downloading + loading TabPFN checkpoint ...")
    clf = TabPFNClassifier(device="cpu")
    clf.fit(X, y)
    clf.predict(X[:4])
    print("[prefetch] OK — weights cached. Compute nodes can now run with "
          "HF_HUB_OFFLINE=1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
