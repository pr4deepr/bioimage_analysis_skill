# Environment

## Quick Environment Check

No background scanner needed. Run inline:

```bash
# Find the active Python
which python  # Linux/Mac
where python  # Windows

# Check what's installed (one call)
python -c "
import importlib, subprocess
for pkg in ['cellpose','stardist','skimage','napari','napari_mcp','bioio','tifffile','nnunetv2']:
    spec = importlib.util.find_spec(pkg)
    if spec:
        mod = importlib.import_module(pkg)
        print(f'{pkg}={getattr(mod, \"__version__\", \"installed\")}')
    else:
        print(f'{pkg}=not found')
"
```

If the active env doesn't have what's needed, ask the user which Python/env to use.

---

## GPU Detection

Check before recommending DL segmentation — CPU inference on large datasets can take hours.

```bash
python -c "
try:
    import torch
    print(f'CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)}')
        print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
except ImportError:
    print('torch not installed — cannot check GPU. DL tools (Cellpose, StarDist) need PyTorch.')
"
```

If no GPU: warn user that DL segmentation will be slow on large datasets. Cellpose on CPU: ~30-60s per 1024x1024 image. StarDist is faster (~5-10s). For large batches without GPU, consider classical methods first.

---

## Version Gotchas

**Use `validate_model_for_version()` from `bioimage_utils.py`** to catch
incompatibilities before writing code:

```python
from bioimage_utils import validate_model_for_version
check = validate_model_for_version("cellpose", "cyto3")
# {"valid": False, "message": "Cellpose 2.x does not have cyto3...", "suggestion": "cyto2"}
```

The function checks Cellpose version vs model names, nnUNet v1 vs v2,
aicsimageio vs bioio rename, and StarDist availability.

Reference table (the function encodes this logic):

| Tool | Gotcha |
|---|---|
| Cellpose 2.x | Models: `cyto`, `cyto2`, `nuclei`, `livecell`. No `cyto3`. Use `models.Cellpose(model_type=...)`. |
| Cellpose 3.x | Adds `cyto3`. All 2.x models still work. Same API as 2.x. |
| Cellpose 4.x | **Breaking**: `models.Cellpose` removed → use `models.CellposeModel`. `diameter` ignored (size-invariant). `channels` removed. Weights are bfloat16. See segmentation.md for 4.x code. |
| StarDist | Pretrained models stable across versions. **Requires** explicit normalization via `csbdeep.utils.normalize()`. |
| scikit-image | Generally stable. Minor moves between 0.19→0.22. |
| napari | Plugin API changed between 0.4.x and 0.5.x. |
| nnUNetv2 | Completely different from v1 — different CLI, dataset format. |
| BioIO | Successor to aicsimageio. Check which is installed. |

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `CUDA out of memory` | Image too large or batch too big for GPU VRAM | Set `gpu=False`, reduce image size, or process in tiles |
| `ValueError: ndim` (StarDist) | Passed 3D array to 2D model or vice versa | Check image dimensions; extract single Z-slice or max-project |
| `ModuleNotFoundError: bioio_czi` | BioIO reader plugin not installed | `pip install bioio-czi` (or -lif, -nd2 for other formats) |
| `No module named 'cellpose'` | Wrong Python env active | Activate the correct conda env first |
| Cellpose returns empty masks | Diameter estimate way off, or wrong channels | Set `diameter` manually; check `channels` argument |
| StarDist predicts nothing | Input not normalized or wrong dtype | Use `csbdeep.utils.normalize(image)` before prediction |

---

## napari-mcp Setup

napari-mcp must be **registered as an MCP server in Claude Code** — not just launched as a subprocess.

```bash
# Check if already registered
claude mcp list

# Install into the napari environment
{viewer_python} -m pip install napari-mcp

# Register as MCP server (use full absolute path to Python)
claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp

# Verify — look for napari tools (session_information, add_image, add_labels, take_screenshot)
```

If napari < 0.5.0, warn: napari-mcp may not work. Suggest upgrading.

If setup fails at any step: tell the user what failed, proceed with matplotlib for all visuals.

---

## Tools Quick Reference

| Tool | Purpose |
|---|---|
| BioIO | Read proprietary microscopy formats (CZI, LIF, ND2, OME-TIFF) |
| scikit-image | Thresholding, morphology, watershed, regionprops |
| Cellpose | DL instance segmentation, pretrained + custom models |
| StarDist | DL segmentation for nuclei, very fast |
| nnUNetv2 | Self-configuring DL segmentation, requires custom training |
| napari | Interactive viewer, QC overlays, annotation |
| tifffile | Fallback TIFF reader, always available |
