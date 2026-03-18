# Visualization Cookbook

Visual feedback is core to this skill. Every analysis step produces visual output
that the user evaluates before proceeding. napari is preferred (interactive overlays),
matplotlib is the first-class fallback (always available, publication-quality).

---

## napari Setup & Connection

napari-mcp (github.com/royerlab/napari-mcp) connects Claude to a napari viewer via
MCP. It has **two modes** — choose based on the user's situation:

| Mode | When to use | How it works |
|------|------------|--------------|
| **Standalone** | User doesn't have napari open yet | MCP server launches its own napari viewer |
| **Plugin** | User already has napari running | napari plugin starts a bridge server that connects to the existing session |

### Step 1: Check if napari-mcp is already registered

```bash
claude mcp list
```

If `napari-mcp` appears → skip to Step 3 (verify connection).

### Step 2: Install and register napari-mcp

**Install napari-mcp into the napari environment:**

```bash
# Use the Python from the napari environment (full absolute path)
{viewer_python} -m pip install napari-mcp
```

If pip fails (corporate/HPC network):
- Try: `conda install -c conda-forge napari-mcp`
- Or: download wheel from PyPI, then `pip install napari_mcp-*.whl`
- If all fail: proceed with matplotlib, update STATE.md `fallback: matplotlib`

**Check napari version compatibility:**

```bash
{viewer_python} -c "import napari; print(napari.__version__)"
```

If napari < 0.5.0, warn the user: napari-mcp may not work. Suggest upgrading.

**Register with Claude Code using the automated installer (recommended):**

```bash
napari-mcp-install install claude-code
```

This auto-detects the napari environment and writes the correct MCP server config.
The installer handles Python path resolution, transport settings, and config file
location automatically.

**Manual registration (if the installer is not available):**

```bash
claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp
```

Where `{viewer_python}` is the **full absolute path** to the Python executable in the
napari environment (e.g., `/home/user/.conda/envs/napari-env/bin/python`).

After registering, Claude Code manages the MCP server lifecycle automatically —
it starts the server when needed and stops it when done.

### Step 3: Verify connection

**The proof of connection is a successful MCP tool call.** Call `session_information()`
to confirm napari is running and responsive:

```
MCP tool: session_information
Arguments: {}
```

If the call succeeds:
- Update STATE.md: `viewer_connected: true`, `mcp_registered: true`
- The napari viewer window should be open (standalone mode launches it automatically)

If the call fails:
- Check `/mcp` in Claude Code to see server status and error messages
- Verify the Python path is correct and napari-mcp is installed in that environment
- Fall back to matplotlib, update STATE.md: `viewer_connected: false`

### Plugin mode (user already has napari open)

If the user already has a napari viewer running:

1. User opens napari's menu: **Plugins → napari-mcp: MCP Server Control**
2. User clicks **"Start Server"** — this starts a bridge server in the existing session
3. Register in Claude Code with the installer: `napari-mcp-install install claude-code`
4. Verify with `session_information()` — the response includes the existing viewer's state

Plugin mode is preferred when the user has data already loaded in napari or has a
specific viewer layout they want to keep.

### Direct napari launch (fallback without MCP)

When MCP registration is not possible or fails, launch napari directly with data
pre-loaded. Claude cannot interact with this viewer after launch — use matplotlib
for Claude's visual output.

```python
import subprocess

viewer_python = state["viewer_env"]["python"]  # from STATE.md

# Build a script that opens napari with the image and labels
script = f'''
import tifffile, napari
image = tifffile.imread("{image_path}")
labels = tifffile.imread("{labels_path}")
viewer = napari.Viewer()
viewer.add_image(image, name="raw", colormap="gray")
viewer.add_labels(labels, name="segmentation")
napari.run()
'''

# Launch in background — user can interact, Claude uses matplotlib
subprocess.Popen([viewer_python, "-c", script], start_new_session=True)
```

### Handle setup failure

If napari-mcp setup fails at any step, **don't stall**:
1. Tell the user what failed and why (show the actual error)
2. Offer to try fixing it or proceed with matplotlib
3. Update STATE.md: `viewer_connected: false, fallback: matplotlib`
4. Continue analysis using matplotlib for all visuals

---

## Which Viewer? — Decision Logic

Before every visual step, check STATE.md for `viewer_connected`:

- `viewer_connected: true` → use napari MCP tools
- `viewer_connected: false` or missing → use matplotlib

If napari is available but not yet connected, attempt `session_information()` once.
If it succeeds, update STATE.md and use napari. If it fails, use matplotlib for this
step — don't block the analysis.

---

## Showing Results — napari

All napari operations use MCP tool calls. napari-mcp exposes **16 tools** organized
into four categories:

**Session management:**
- `session_information` — check connection, get viewer state and layer info
- `init_viewer` — initialize a new napari viewer (standalone mode does this automatically)
- `close_viewer` — shut down the viewer

**Layer operations:**
- `add_layer` — add image, labels, shapes, or points layer (specify `layer_type`)
- `list_layers` — list all layers currently in the viewer
- `get_layer` — get properties of a specific layer
- `remove_layer` — delete a layer
- `set_layer_properties` — change colormap, visibility, opacity, etc.
- `reorder_layer` — change layer stacking order
- `apply_to_layers` — batch operations on multiple layers
- `save_layer_data` — export layer data to disk

**Viewer controls:**
- `configure_viewer` — adjust camera, display mode, theme

**Utilities:**
- `screenshot` — capture current viewer display as image
- `execute_code` — run Python code in the napari environment
- `install_packages` — install packages via pip in the napari environment
- `read_output` — access results from previous code execution

### Add raw image

```
MCP tool: add_layer
Arguments:
  layer_type: "image"
  name: "raw"
  data: <numpy array or path to image file>
  colormap: "gray"         # optional, default gray
  contrast_limits: [low, high]  # optional, auto-computed if omitted
```

After adding, call `screenshot` to capture the view for evaluation.

### Add segmentation overlay (labels on image)

Show labels on top of the raw image. napari renders labels as a transparent
colored overlay automatically.

```
# Step 1: Add the raw image (if not already added)
MCP tool: add_layer
Arguments:
  layer_type: "image"
  name: "raw"
  data: <raw image array>
  colormap: "gray"

# Step 2: Add the labels layer on top
MCP tool: add_layer
Arguments:
  layer_type: "labels"
  name: "segmentation"
  data: <label array, dtype int32>

# Step 3: Screenshot to evaluate
MCP tool: screenshot
```

The labels layer sits on top of the image layer with transparency. Each label ID
gets a unique color. No extra code needed for the overlay effect.

### Side-by-side comparison

For comparing two results (e.g., two parameter sets), add both as separate layers
and toggle visibility, or use napari's grid mode:

```
# Add first result
MCP tool: add_layer
Arguments:
  layer_type: "labels"
  name: "segmentation_v1"
  data: <labels_v1>

# Add second result
MCP tool: add_layer
Arguments:
  layer_type: "labels"
  name: "segmentation_v2"
  data: <labels_v2>

# User can toggle layers in napari's layer list
# Screenshot each separately for evaluation
MCP tool: screenshot
```

### QC overlay (outlines colored by measurement)

Color each object by a measurement value (e.g., area) for quality assessment.
Build a colored image in Python, then send it as an image layer.

```python
import numpy as np
from skimage.measure import regionprops

# Build a measurement-colored image
props = regionprops(labels, intensity_image=raw)
colored = np.zeros_like(labels, dtype=float)
for p in props:
    colored[labels == p.label] = p.area  # or any measurement
```

Then send via MCP:

```
MCP tool: add_layer
Arguments:
  layer_type: "image"
  name: "area_overlay"
  data: <colored array>
  colormap: "viridis"
  contrast_limits: [min_area, max_area]
```

Keep the raw image underneath for context.

### Take screenshot

```
MCP tool: screenshot
Arguments: {}

# Returns: image data (PNG bytes or numpy array)
# Use this to evaluate results programmatically or show in conversation
```

### Execute code in napari environment

For complex operations not covered by individual tools, run code directly:

```
MCP tool: execute_code
Arguments:
  code: "import numpy as np; print(viewer.layers['segmentation'].data.max())"
```

Use `read_output` to retrieve results from previous `execute_code` calls.

---

## Showing Results — matplotlib

All matplotlib patterns produce publication-quality figures with proper axes,
labels, titles, and colorbars. These work regardless of napari availability.

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

### QC overlay

Color each object outline by a measurement value. This is the matplotlib
equivalent of the napari QC overlay.

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

Standard pattern for saving any matplotlib figure at publication quality.

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

## Measurement Visualizations (both viewers)

These patterns work with both napari (via matplotlib in the analysis env) and
standalone matplotlib. Measurement plots are always matplotlib — napari is for
spatial overlays, matplotlib is for statistical plots.

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

For multi-condition experiments (e.g., treated vs control), show distributions
side by side.

```python
import matplotlib.pyplot as plt
import pandas as pd

# Assume measurements_df has columns: 'condition', 'area', 'mean_intensity'
# Built from regionprops across multiple images/conditions

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Area by condition
measurements_df.boxplot(column="area", by="condition", ax=axes[0],
                        grid=False, patch_artist=True,
                        boxprops=dict(facecolor="#4C72B0", alpha=0.7))
axes[0].set_title("Area by condition")
axes[0].set_xlabel("Condition")
axes[0].set_ylabel("Area (px²)")
axes[0].get_figure().suptitle("")  # Remove auto-title from boxplot()

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
