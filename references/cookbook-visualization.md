# Visualization Cookbook

Visual feedback is core to this skill. Every analysis step produces visual output
that the user evaluates before proceeding. napari is preferred (interactive overlays),
matplotlib is the first-class fallback (always available, publication-quality).

---

## napari Setup & Connection

napari-mcp must be **registered as an MCP server in Claude Code** — not just launched as
a subprocess. Simply running `python -m napari_mcp` does NOT make MCP tools available.

### Step 1: Check if napari-mcp is already registered

Use the Bash tool to check existing MCP servers:

```bash
claude mcp list
```

If `napari` appears in the list → skip to Step 3 (verify connection).

### Step 2: Install and register napari-mcp

This is a two-part process: install the package, then register the MCP server.

**Install napari-mcp into the napari environment:**

```bash
# Use the Python from the napari environment
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

**Register napari-mcp as an MCP server in Claude Code:**

```bash
claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp
```

Where `{viewer_python}` is the **full path** to the Python executable in the napari
environment (e.g., `C:/Users/Pradeep/.conda/envs/napari-lattice/python.exe`).

**Important:** Use the full absolute path to the Python executable, not just `python`.
This ensures Claude Code uses the correct environment regardless of PATH settings.

After registering, the MCP tools become available in the current session. No restart
needed — Claude Code picks up new MCP servers dynamically.

### Step 3: Verify connection

**The proof of connection is a successful MCP tool call.** Use the `ToolSearch` tool
to check if napari-mcp tools are available:

```
ToolSearch: query="napari" max_results=5
```

If napari tools appear (e.g., `session_information`, `add_image`, `add_labels`):
- Call `session_information()` to confirm napari is running and responsive
- Update STATE.md: `viewer_connected: true`, `mcp_registered: true`

If no napari tools found after registration:
- The MCP server may not have started. Check if napari window opened.
- Try `/mcp` in Claude Code to see server status
- If server shows error: check that the Python path is correct
- Fall back to matplotlib, update STATE.md: `viewer_connected: false`

### Step 4: Launch napari (if not already running)

napari-mcp starts napari automatically when Claude Code connects to the MCP server.
If napari is not opening:

```bash
# Manual launch as a last resort — opens napari but without MCP connection
{viewer_python} -c "import napari; viewer = napari.Viewer(); napari.run()" &
```

This gives the user a viewer but Claude cannot push layers to it programmatically.
Use matplotlib for Claude's visual output and tell the user to load files manually.

### Direct napari launch (fallback without MCP)

When MCP registration is not possible or fails, launch napari directly with data
pre-loaded. Claude cannot interact with this viewer after launch.

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
1. Tell the user what failed and why
2. Offer to try fixing it or proceed with matplotlib
3. Update STATE.md: `viewer_connected: false, fallback: matplotlib`
4. Continue analysis using matplotlib for all visuals

---

## Which Viewer? — Decision Snippet

Use this before every visual step. Reads STATE.md and routes to the correct code path.

```python
def get_viewer_mode(state_path=".bioimage-analysis/STATE.md"):
    """Read STATE.md and return 'napari' or 'matplotlib'.

    Call this before every visualization step.
    If napari was expected but not yet connected, attempt one MCP retry.
    """
    # Parse STATE.md for viewer_connected field
    with open(state_path, "r") as f:
        content = f.read()

    viewer_connected = "viewer_connected: true" in content
    napari_available = "napari_available: true" in content

    if viewer_connected:
        return "napari"

    if napari_available and not viewer_connected:
        # One retry — napari may have finished starting
        # Call session_information() via MCP
        # If success: update STATE.md viewer_connected: true, return "napari"
        # If failure: return "matplotlib"
        pass

    return "matplotlib"
```

**Usage at every visual step:**

```python
viewer = get_viewer_mode()

if viewer == "napari":
    # Use MCP tool calls (add_image, add_labels, etc.)
    ...
elif viewer == "matplotlib":
    # Use matplotlib code paths below
    ...
```

---

## Showing Results — napari

All napari operations use MCP tool calls. The expected tool names are:
- `session_information` — check connection, get viewer state
- `add_image` — add a raw image layer
- `add_labels` — add a label/segmentation layer
- `take_screenshot` — capture the current viewer as an image

### Add raw image

```
MCP tool: add_image
Arguments:
  name: "raw"
  data: <numpy array or path to image file>
  colormap: "gray"         # optional, default gray
  contrast_limits: [low, high]  # optional, auto-computed if omitted
```

After adding, call `take_screenshot` to capture the view for evaluation.

### Add segmentation overlay (labels on image)

Show labels on top of the raw image. napari renders labels as a transparent
colored overlay automatically.

```
# Step 1: Add the raw image (if not already added)
MCP tool: add_image
Arguments:
  name: "raw"
  data: <raw image array>
  colormap: "gray"

# Step 2: Add the labels layer on top
MCP tool: add_labels
Arguments:
  name: "segmentation"
  data: <label array, dtype int32>

# Step 3: Screenshot to evaluate
MCP tool: take_screenshot
```

The labels layer sits on top of the image layer with transparency. Each label ID
gets a unique color. No extra code needed for the overlay effect.

### Side-by-side comparison

For comparing two results (e.g., two parameter sets), add both as separate layers
and toggle visibility, or use napari's grid mode:

```
# Add first result
MCP tool: add_labels
Arguments:
  name: "segmentation_v1"
  data: <labels_v1>

# Add second result
MCP tool: add_labels
Arguments:
  name: "segmentation_v2"
  data: <labels_v2>

# User can toggle layers in napari's layer list
# Screenshot each separately for evaluation
MCP tool: take_screenshot
```

### QC overlay (outlines colored by measurement)

Color each object by a measurement value (e.g., area) for quality assessment.
This requires building a colored label image in Python, then sending it.

```python
import numpy as np
from skimage.measure import regionprops

# Build a measurement-colored image
props = regionprops(labels, intensity_image=raw)
colored = np.zeros_like(labels, dtype=float)
for p in props:
    colored[labels == p.label] = p.area  # or any measurement

# Send as image layer with a colormap
# MCP tool: add_image
# Arguments:
#   name: "area_overlay"
#   data: colored
#   colormap: "viridis"
#   contrast_limits: [min_area, max_area]

# Also keep the raw image underneath for context
```

### Take screenshot via MCP

```
MCP tool: take_screenshot
Arguments: {}

# Returns: image data (PNG bytes or numpy array)
# Use this to evaluate results programmatically or show in conversation
```

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
