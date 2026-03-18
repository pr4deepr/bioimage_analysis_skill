# Environment

How to find tools, check versions, and connect to a viewer. Designed to be fast —
filesystem checks first, Python calls only when needed.

---

## Background Worker Pattern

**First: check if `.bioimage-analysis/STATE.md` exists.** If it has recent env info,
skip scanning entirely — use the cached results.

If no STATE.md or env info is missing, spawn this on activation:

```
Background worker:
1. List conda env names + paths          (~1 sec)
2. Pick 2-3 candidates by name           (instant)
3. Filesystem check: ls site-packages/   (~1 sec total)
4. Python version check on winners only  (~5 sec)
5. Write results to .bioimage-analysis/STATE.md
6. Report to foreground
```

The foreground conversation can peek at partial results — "I can see you have a
stardist env, still checking details..."

---

## Step 1: List Environment Paths

One call. Get paths so we can inspect the filesystem directly.

```python
import subprocess, json
result = subprocess.run(["conda", "env", "list", "--json"],
    capture_output=True, text=True, timeout=10)
env_paths = json.loads(result.stdout).get("envs", [])
```

If `conda` not found, try:
- `mamba env list --json`
- Windows: `C:/Users/<user>/miniconda3/condabin/conda.bat env list --json`

---

## Step 2: Pick 2-3 Candidates by Name

Match the user's task to env names. Always include any env named `napari`.

| User mentions | Check env named |
|---|---|
| stardist, neurons | `stardist` + `napari` |
| cellpose, cells | `cellpose` + `napari` |
| nnunet, segmentation | `nnunet`, `monai` + `napari` |
| general | `bioimage`, `imaging`, `everyday` + `napari` |

Also check the currently active environment if it doesn't match the above.

**Maximum 3 environments. Not more.**

---

## Step 3: Filesystem Check (fast first-pass)

Check `site-packages/` for known folder names. No Python startup, no import overhead.

### Paths

```
Windows:   {env_path}/Lib/site-packages/
Linux/Mac: {env_path}/lib/python*/site-packages/
```

### Check pattern

```python
import os, glob

def check_site_packages(env_path):
    """Check what's installed by looking at folders. Milliseconds."""
    # Find site-packages
    candidates = glob.glob(os.path.join(env_path, "Lib", "site-packages")) + \
                 glob.glob(os.path.join(env_path, "lib", "python*", "site-packages"))
    if not candidates:
        return {}

    sp = candidates[0]
    packages = {}
    for pkg_folder in ['napari', 'napari_mcp', 'cellpose', 'stardist',
                        'skimage', 'bioio', 'nnunetv2', 'tifffile']:
        packages[pkg_folder] = os.path.isdir(os.path.join(sp, pkg_folder))
    return packages
```

Or as a single shell command:

```bash
# Windows
dir /b "{env_path}\Lib\site-packages" | findstr /i "napari cellpose stardist skimage bioio nnunetv2"

# Linux/Mac
ls "{env_path}/lib/python*/site-packages/" | grep -E "^(napari|cellpose|stardist|skimage|bioio|nnunetv2)$"
```

### Result

After this step you know which envs have which packages — but not versions.

```
stardist env:  stardist ✓, skimage ✓, napari ✗, napari_mcp ✗
everyday env:  napari ✓, napari_mcp ✗, skimage ✓
```

This is enough to route: analysis in stardist env, display in everyday env.

---

## Step 4: Python Version Check (only on winners)

Run Python only on the 1-2 envs you'll actually use. One call per env.

```python
def get_versions(env_python):
    """Get exact versions. Only call this on envs you'll use."""
    result = subprocess.run([env_python, "-c",
        "import importlib;"
        "[print(f'{p}={getattr(importlib.import_module(p),\"__version__\",\"?\")}')"
        " if importlib.util.find_spec(p) else print(f'{p}=none')"
        " for p in ['napari','napari_mcp','cellpose','stardist','skimage','bioio']]"],
        capture_output=True, text=True, timeout=15)
    return result.stdout
```

### Where to find env Python

```
Windows:   {env_path}/python.exe
Linux/Mac: {env_path}/bin/python
```

---

## Step 5: Write STATE.md

Write scan results to `.bioimage-analysis/STATE.md` so future activations skip scanning.

```python
import os
from datetime import datetime

os.makedirs(".bioimage-analysis", exist_ok=True)

state = f"""# Bioimage Analysis State

## Environment
- conda_path: {conda_path}
- analysis_env: {analysis_env_name}
  - path: {analysis_env_path}
  - python: {analysis_python}
  - {tool_versions_formatted}
- viewer_env: {viewer_env_name}
  - path: {viewer_env_path}
  - napari: {napari_version}
  - napari_mcp: {mcp_version or 'none'}
- other_envs_checked: [{', '.join(checked_names)}]

## Viewer
- napari_available: {napari_found}
- napari_mcp_installed: {mcp_installed}
- viewer_connected: false

## History
- [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Environment scan complete
"""

with open(".bioimage-analysis/STATE.md", "w") as f:
    f.write(state)
```

See `references/state-templates.md` for full STATE.md format and update rules.

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

> See: cookbook-visualization.md § napari Launch & Verification

For the canonical napari-mcp install, launch, connection verification, and fallback patterns.

---

## FIJI (optional)

fiji_mcp (github.com/NicoKiaru/fiji_mcp) — proof-of-concept MCP server for FIJI.
More manual setup. Only suggest for users who specifically want FIJI or need
FIJI-specific plugins (TrackMate, MorphoLibJ).

For most users, napari is the better path for viewer connection.

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
