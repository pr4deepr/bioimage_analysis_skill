# Visualization Cookbook

Visual feedback is core to this skill. Every analysis step produces visual output
that the user evaluates before proceeding. napari is preferred (interactive overlays),
matplotlib is the first-class fallback (always available, publication-quality).

---

## napari Launch & Verification

### Install napari-mcp

Read STATE.md to find the viewer env Python path. Install into that env.

```python
import subprocess

viewer_python = state["viewer_env"]["python"]  # from STATE.md

result = subprocess.run(
    [viewer_python, "-m", "pip", "install", "napari-mcp"],
    capture_output=True, text=True, timeout=120
)

if result.returncode != 0:
    # See "Handle launch failure" section below
    print(f"pip install failed:\n{result.stderr}")
```

### Launch napari-mcp (Windows)

Launch as a detached process with stderr captured to a temp file so we can read
error messages if the process dies.

```python
import subprocess, tempfile, os

viewer_python = state["viewer_env"]["python"]  # from STATE.md

# Create temp file for stderr capture
stderr_file = os.path.join(tempfile.gettempdir(), "napari_mcp_stderr.log")

with open(stderr_file, "w") as err_f:
    proc = subprocess.Popen(
        f'start "" "{viewer_python}" -m napari_mcp',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=err_f
    )
```

### Launch napari-mcp (macOS/Linux)

```python
import subprocess, tempfile, os

viewer_python = state["viewer_env"]["python"]  # from STATE.md

stderr_file = os.path.join(tempfile.gettempdir(), "napari_mcp_stderr.log")

with open(stderr_file, "w") as err_f:
    proc = subprocess.Popen(
        [viewer_python, "-m", "napari_mcp"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=err_f
    )
```

### Verify connection (check-before-first-use)

**This is the critical pattern.** Never claim napari is connected without proof.
The proof is a successful MCP response from `session_information()`.

```python
import time, os

# Step 1: Wait for napari to start up
time.sleep(5)

# Step 2: Check if process is still alive (Windows: poll the PID)
# If the process died, read stderr for the actual error
stderr_file = os.path.join(tempfile.gettempdir(), "napari_mcp_stderr.log")

# On Windows with `start`, proc.poll() returns immediately (it's the shell).
# Instead, check if napari_mcp_stderr.log has error content:
if os.path.exists(stderr_file):
    with open(stderr_file, "r") as f:
        stderr_content = f.read().strip()
    if "Error" in stderr_content or "Traceback" in stderr_content:
        # Process died — report the actual error
        print(f"napari-mcp failed to start:\n{stderr_content}")
        # Update STATE.md: viewer_connected: false
        # Fall back to matplotlib
```

```python
# Step 3: Attempt MCP connection — this is the PROOF
# Call the napari-mcp tool session_information() via MCP
# Expected MCP tool call:
#   tool: session_information
#   args: {}
# Expected response: JSON with napari version, viewer state, etc.

# If session_information() returns a valid response:
#   → Connection confirmed
#   → Update STATE.md: viewer_connected: true
#   → Append to history: "[timestamp] Connected to napari via MCP"

# If session_information() times out or errors:
#   → Connection failed
#   → Update STATE.md: viewer_connected: false, fallback: matplotlib
#   → Append to history: "[timestamp] napari MCP connection failed: {error}"
#   → Use matplotlib for this visual step
#   → Retry MCP before the NEXT visual step (see retry pattern below)
```

**Retry pattern for subsequent visual steps:**

```python
# Before each visual step, check STATE.md viewer_connected field.
# If false and napari was attempted but failed:
#   1. Try session_information() one more time (napari may have finished loading)
#   2. If success → update STATE.md viewer_connected: true, use napari
#   3. If failure → use matplotlib, don't retry again until next analysis session
```

### Handle launch failure

**pip install failure (corporate/HPC network restrictions):**

```python
result = subprocess.run(
    [viewer_python, "-m", "pip", "install", "napari-mcp"],
    capture_output=True, text=True, timeout=120
)

if result.returncode != 0:
    stderr = result.stderr
    if "SSL" in stderr or "proxy" in stderr or "network" in stderr:
        # Network restriction — suggest alternatives
        msg = (
            "pip install failed (likely network restriction).\n"
            "Options:\n"
            "  1. conda install -c conda-forge napari-mcp\n"
            "  2. Download wheel manually from PyPI and: pip install napari_mcp-*.whl\n"
            "  3. Proceed without napari — I'll use matplotlib for all visuals."
        )
    else:
        msg = f"pip install napari-mcp failed:\n{stderr}\nProceeding with matplotlib."

    print(msg)
    # Update STATE.md: napari_mcp_installed: false, viewer_connected: false, fallback: matplotlib
```

**napari version mismatch:**

```python
# Read napari version from STATE.md before installing napari-mcp
napari_version = state["viewer_env"].get("napari", "none")

if napari_version != "none":
    major_minor = tuple(int(x) for x in napari_version.split(".")[:2])
    if major_minor < (0, 5):
        print(
            f"WARNING: napari {napari_version} detected. napari-mcp requires >= 0.5.0.\n"
            f"napari-mcp may not work correctly. Consider upgrading napari first:\n"
            f"  pip install 'napari>=0.5.0'\n"
            f"Proceeding with matplotlib as fallback."
        )
        # Update STATE.md: viewer_connected: false, fallback: matplotlib
```

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
