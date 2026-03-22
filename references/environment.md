# Environment

How to find tools and check versions. Designed to be fast — check the active env
first, scan others only if needed.

---

## Quick Path (90% of cases)

Most users already have an active conda/mamba environment. Check it first.

```python
import sys, os, glob

def check_active_env():
    """Check what's available in the currently active Python environment.
    Returns a dict of package_name -> bool (installed or not).
    Takes milliseconds — no imports, just filesystem checks."""

    sp_dirs = glob.glob(os.path.join(sys.prefix, "lib", "python*", "site-packages")) + \
              glob.glob(os.path.join(sys.prefix, "Lib", "site-packages"))
    if not sp_dirs:
        return {}

    sp = sp_dirs[0]
    packages = {}
    for pkg in ['napari', 'napari_mcp', 'cellpose', 'stardist',
                'skimage', 'bioio', 'nnunetv2', 'tifffile']:
        packages[pkg] = os.path.isdir(os.path.join(sp, pkg))
    return packages
```

Or as a one-liner shell command:

```bash
ls "$(python -c 'import site; print(site.getsitepackages()[0])')" 2>/dev/null | grep -E "^(napari|cellpose|stardist|skimage|bioio|nnunetv2|tifffile)$"
```

**If the active env has what you need → use it. Done.** No further scanning.

---

## Broader Scan (only when active env is missing tools)

Only run this if the active environment is missing a required package (e.g., user
needs Cellpose but the active env doesn't have it).

### Step 1: List conda environments

```python
import subprocess, json
result = subprocess.run(["conda", "env", "list", "--json"],
    capture_output=True, text=True, timeout=10)
env_paths = json.loads(result.stdout).get("envs", [])
```

If `conda` not found, try `mamba env list --json`.

### Step 2: Filesystem check on candidates

Check `site-packages/` for the specific package you need. Don't scan everything —
just look for what's missing.

```python
import os, glob

def find_package_in_envs(env_paths, package_name):
    """Find which conda envs have a specific package installed.
    Milliseconds per env — no Python startup needed."""
    matches = []
    for env_path in env_paths:
        sp_dirs = glob.glob(os.path.join(env_path, "Lib", "site-packages")) + \
                  glob.glob(os.path.join(env_path, "lib", "python*", "site-packages"))
        if not sp_dirs:
            continue
        if os.path.isdir(os.path.join(sp_dirs[0], package_name)):
            matches.append(env_path)
    return matches
```

### Step 3: Version check (only on the env you'll use)

```python
def get_version(env_python, package_name):
    """Get exact version of one package. Only call on the env you chose."""
    result = subprocess.run([env_python, "-c",
        f"import {package_name}; print({package_name}.__version__)"],
        capture_output=True, text=True, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else None
```

Where to find the env's Python:
```
Windows:   {env_path}/python.exe
Linux/Mac: {env_path}/bin/python
```

---

## Never Blind-Install

Before running `pip install` or `conda install`:

1. Check the active env (Quick Path above)
2. If missing, scan other envs (Broader Scan above)
3. Only install if no existing env has the package
4. Install into the correct env, not whatever is active
5. Prefer `conda install` over `pip install` in conda envs

**If the user says "I use my cellpose env for this" → trust them, activate that
env, skip scanning.**

---

## Version Gotchas

Check before recommending any specific model or API.

| Tool | Gotcha |
|---|---|
| Cellpose 2.x | Models: `cyto`, `cyto2`, `nuclei`. No `cyto3`. |
| Cellpose 3.x | Adds `cyto3`. Previous models still work. |
| Cellpose 4.x | New architecture — old model names may not exist. |
| StarDist | Pretrained models stable across versions. |
| scikit-image | Generally stable. Minor moves between 0.19→0.22. |
| napari | Plugin API changed between 0.4.x and 0.5.x. |
| nnUNetv2 | Completely different from v1 — different CLI, dataset format. |
| BioIO | Successor to aicsimageio. Check which is installed. |

---

## napari Viewer Setup

> See: cookbook-visualization.md § napari Setup & Connection

napari-mcp is **opt-in**, not required. matplotlib is the default viewer.
Only set up napari-mcp if the user wants interactive exploration or already
has napari running.

---

## FIJI (optional)

fiji_mcp (github.com/NicoKiaru/fiji_mcp) — proof-of-concept MCP server for FIJI.
Only suggest for users who specifically want FIJI or need FIJI-specific plugins
(TrackMate, MorphoLibJ).

---

## Tools Quick Reference

### Python
- **BioIO** — read microscopy formats (CZI, LIF, ND2, OME-TIFF)
- **scikit-image** — thresholding, morphology, watershed, regionprops
- **scipy.ndimage** — labeling, distance transforms
- **napari** — viewer, QC overlays, annotation (Labels layer)
- **Cellpose** — DL instance segmentation, pretrained models
- **StarDist** — DL segmentation for nuclei, very fast
- **nnUNetv2** — self-configuring DL segmentation, train on your data
- **tifffile** — fallback TIFF reader, always available

### FIJI
- **Bio-Formats** — read proprietary formats (built-in)
- **Threshold / Analyze Particles** — classical segmentation + measurement
- **MorphoLibJ** — advanced morphological operations
- **StarDist plugin** — StarDist in FIJI without Python
