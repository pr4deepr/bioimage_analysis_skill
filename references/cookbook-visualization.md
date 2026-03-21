# Visualization Cookbook

Visual feedback is core to this skill. Every analysis step produces visual output
that the user evaluates before proceeding.

**Default viewer: matplotlib** — always available, publication-quality, zero setup.
**Upgrade: napari-mcp** — interactive overlays, opt-in when the user wants it or
already has napari running.

---

## Showing Results — matplotlib (default)

All matplotlib patterns produce publication-quality figures with proper axes,
labels, titles, and colorbars. These work everywhere.

### Show raw image

```python
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(8, 8))
im = ax.imshow(raw, cmap="gray")
ax.set_title("Raw image")
ax.set_xlabel("X (pixels)")
ax.set_ylabel("Y (pixels)")
plt.colorbar(im, ax=ax, label="Intensity", shrink=0.8)
plt.tight_layout()
plt.savefig("analysis/raw_preview.png", dpi=150, bbox_inches="tight")
plt.show()
```

### Show segmentation overlay

```python
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

fig, ax = plt.subplots(figsize=(8, 8))

# Show raw image
ax.imshow(raw, cmap="gray")

# Overlay labels with transparency — mask out background (label 0)
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")

ax.set_title(f"Segmentation overlay ({labels.max()} objects)")
ax.set_xlabel("X (pixels)")
ax.set_ylabel("Y (pixels)")
plt.tight_layout()
plt.savefig("analysis/segmentation_overlay.png", dpi=150, bbox_inches="tight")
plt.show()
```

### Side-by-side comparison

```python
import matplotlib.pyplot as plt
import numpy as np

fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharex=True, sharey=True)

# Left: first result
axes[0].imshow(raw, cmap="gray")
labels1_masked = np.ma.masked_where(labels_v1 == 0, labels_v1)
axes[0].imshow(labels1_masked, cmap="tab20", alpha=0.4, interpolation="none")
axes[0].set_title(f"v1: {labels_v1.max()} objects")
axes[0].set_xlabel("X (pixels)")
axes[0].set_ylabel("Y (pixels)")

# Right: second result
axes[1].imshow(raw, cmap="gray")
labels2_masked = np.ma.masked_where(labels_v2 == 0, labels_v2)
axes[1].imshow(labels2_masked, cmap="tab20", alpha=0.4, interpolation="none")
axes[1].set_title(f"v2: {labels_v2.max()} objects")
axes[1].set_xlabel("X (pixels)")

plt.tight_layout()
plt.savefig("analysis/comparison.png", dpi=150, bbox_inches="tight")
plt.show()
```

### QC overlay (outlines colored by measurement)

```python
import matplotlib.pyplot as plt
import numpy as np
from skimage.measure import regionprops
from skimage.segmentation import find_boundaries

props = regionprops(labels, intensity_image=raw)
areas = {p.label: p.area for p in props}

# Build a float image where each object has its measurement value
measurement_map = np.zeros_like(labels, dtype=float)
for label_id, area in areas.items():
    measurement_map[labels == label_id] = area

# Find boundaries for outline-only display
boundaries = find_boundaries(labels, mode="outer")
outline_map = np.where(boundaries & (labels > 0), measurement_map, np.nan)

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(raw, cmap="gray")

# Overlay outlines colored by measurement
im = ax.imshow(outline_map, cmap="viridis", interpolation="none")
cbar = plt.colorbar(im, ax=ax, label="Area (px²)", shrink=0.8)
ax.set_title("QC: object outlines colored by area")
ax.set_xlabel("X (pixels)")
ax.set_ylabel("Y (pixels)")
plt.tight_layout()
plt.savefig("analysis/qc_overlay.png", dpi=150, bbox_inches="tight")
plt.show()
```

### Save figure

```python
import matplotlib.pyplot as plt

# After creating any figure...
plt.savefig(
    "analysis/figure_name.png",
    dpi=300,                  # publication quality
    bbox_inches="tight",      # no whitespace clipping
    facecolor="white",        # white background (not transparent)
    pad_inches=0.1
)

# Also save as PDF for vector graphics (papers, posters)
plt.savefig(
    "analysis/figure_name.pdf",
    bbox_inches="tight",
    facecolor="white",
    pad_inches=0.1
)

plt.close()  # Free memory after saving
```

---

## napari-mcp (opt-in upgrade)

napari-mcp (github.com/royerlab/napari-mcp) connects Claude to a napari viewer via
MCP. **Only set this up if:**
- The user explicitly wants interactive napari visualization
- The user already has napari running
- The analysis requires interactive annotation (e.g., training data creation)

### When to offer napari

Offer once, early in the conversation: "I'll use matplotlib for visuals. If you'd
like interactive napari viewing, I can help set that up." Then move on.

### Setup

napari-mcp has **two modes**:

| Mode | When to use | How it works |
|------|------------|--------------|
| **Standalone** | User doesn't have napari open yet | MCP server launches its own napari viewer |
| **Plugin** | User already has napari running | napari plugin starts a bridge server |

**Step 1: Check if already registered**

```bash
claude mcp list
```

If `napari-mcp` appears → skip to verification.

**Step 2: Install and register**

```bash
# Install into the napari environment
{viewer_python} -m pip install napari-mcp

# Register (automated — recommended)
napari-mcp-install install claude-code

# Or manual registration:
claude mcp add napari-mcp -- {viewer_python} -m napari_mcp
```

If install fails (corporate/HPC network), don't stall — use matplotlib.

**Step 3: Verify**

```
MCP tool: session_information
Arguments: {}
```

If it works → napari is connected. If it fails → use matplotlib, move on.

### napari MCP tools (16 tools in standalone mode)

**Session:** `session_information`, `init_viewer`, `close_viewer`
**Layers:** `add_layer`, `list_layers`, `get_layer`, `remove_layer`, `set_layer_properties`, `reorder_layer`, `apply_to_layers`, `save_layer_data`
**Viewer:** `configure_viewer`
**Utilities:** `screenshot`, `execute_code`, `install_packages`, `read_output`

Plugin mode only exposes 3 tools: `session_information`, `add_layer`, `execute_code`.

### Direct napari launch (fallback without MCP)

When MCP registration fails, launch napari directly with data pre-loaded.
Claude cannot interact with this viewer after launch — use matplotlib for output.

```python
import subprocess

viewer_python = "/path/to/napari/env/bin/python"

script = f'''
import tifffile, napari
image = tifffile.imread("{image_path}")
labels = tifffile.imread("{labels_path}")
viewer = napari.Viewer()
viewer.add_image(image, name="raw", colormap="gray")
viewer.add_labels(labels, name="segmentation")
napari.run()
'''

subprocess.Popen([viewer_python, "-c", script], start_new_session=True)
```

### Handle setup failure

If napari-mcp fails at any step, **don't stall**:
1. Tell the user what failed (show the actual error)
2. Continue with matplotlib — this is the default, not a fallback
3. Offer to try napari setup again later if the user wants

---

## Measurement Visualizations

Measurement plots are always matplotlib — napari is for spatial overlays,
matplotlib is for statistical plots.

### Histogram of object areas

```python
import matplotlib.pyplot as plt
import numpy as np
from skimage.measure import regionprops

props = regionprops(labels)
areas = [p.area for p in props]

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(areas, bins=30, edgecolor="black", linewidth=0.5, color="#4C72B0")
ax.axvline(np.median(areas), color="red", linestyle="--", label=f"Median: {np.median(areas):.0f} px²")
ax.set_xlabel("Area (px²)")
ax.set_ylabel("Count")
ax.set_title(f"Object area distribution (n={len(areas)})")
ax.legend()
plt.tight_layout()
plt.savefig("analysis/histogram_areas.png", dpi=150, bbox_inches="tight")
plt.show()
```

### Histogram of intensities

```python
import matplotlib.pyplot as plt
import numpy as np
from skimage.measure import regionprops

props = regionprops(labels, intensity_image=raw)
mean_intensities = [p.mean_intensity for p in props]

fig, ax = plt.subplots(figsize=(8, 5))
ax.hist(mean_intensities, bins=30, edgecolor="black", linewidth=0.5, color="#55A868")
ax.axvline(
    np.median(mean_intensities), color="red", linestyle="--",
    label=f"Median: {np.median(mean_intensities):.1f}"
)
ax.set_xlabel("Mean intensity (a.u.)")
ax.set_ylabel("Count")
ax.set_title(f"Object intensity distribution (n={len(mean_intensities)})")
ax.legend()
plt.tight_layout()
plt.savefig("analysis/histogram_intensities.png", dpi=150, bbox_inches="tight")
plt.show()
```

### Box plot per condition

```python
import matplotlib.pyplot as plt
import pandas as pd

# Assume measurements_df has columns: 'condition', 'area', 'mean_intensity'
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Area by condition
measurements_df.boxplot(column="area", by="condition", ax=axes[0],
                        grid=False, patch_artist=True,
                        boxprops=dict(facecolor="#4C72B0", alpha=0.7))
axes[0].set_title("Area by condition")
axes[0].set_xlabel("Condition")
axes[0].set_ylabel("Area (px²)")
axes[0].get_figure().suptitle("")

# Intensity by condition
measurements_df.boxplot(column="mean_intensity", by="condition", ax=axes[1],
                        grid=False, patch_artist=True,
                        boxprops=dict(facecolor="#55A868", alpha=0.7))
axes[1].set_title("Mean intensity by condition")
axes[1].set_xlabel("Condition")
axes[1].set_ylabel("Mean intensity (a.u.)")
axes[1].get_figure().suptitle("")

plt.tight_layout()
plt.savefig("analysis/boxplot_conditions.png", dpi=150, bbox_inches="tight")
plt.show()
```
