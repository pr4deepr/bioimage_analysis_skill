# Visualization

## napari-mcp Setup & Connection

napari-mcp must be **registered as an MCP server in Claude Code** — not just launched.

### Setup

```bash
# 1. Check if already registered
claude mcp list

# 2. Install into napari environment
{viewer_python} -m pip install napari-mcp

# 3. Register (use full absolute path to Python)
claude mcp add --transport stdio napari-mcp -- {viewer_python} -m napari_mcp

# 4. Verify — search for napari tools
```

After registering, MCP tools become available immediately (no restart needed).

If napari < 0.5.0: warn user, napari-mcp may not work.

### napari MCP Tool Names

- `session_information` — check connection, get viewer state
- `add_image` — add a raw image layer (args: name, data, colormap, contrast_limits)
- `add_labels` — add a label/segmentation layer (args: name, data)
- `take_screenshot` — capture current viewer as image

### Typical napari Workflow

```
1. add_image(name="raw", data=image, colormap="gray")
2. add_labels(name="segmentation", data=labels)
3. take_screenshot()  → evaluate overlay
```

For side-by-side comparison: add multiple label layers, toggle visibility.

### Fallback: Direct napari Launch (no MCP)

If MCP registration fails, launch napari directly. Claude cannot interact after launch — use matplotlib for Claude's visual output.

```python
import subprocess
script = f'''
import tifffile, napari
viewer = napari.Viewer()
viewer.add_image(tifffile.imread("{image_path}"), name="raw", colormap="gray")
viewer.add_labels(tifffile.imread("{labels_path}"), name="segmentation")
napari.run()
'''
subprocess.Popen([viewer_python, "-c", script], start_new_session=True)
```

### If Setup Fails

Don't stall. Tell user what failed, proceed with matplotlib for all visuals.

---

## matplotlib (Always Available)

Claude knows matplotlib well. No cookbook needed. Key patterns for bioimage analysis:

- **Segmentation overlay**: `ax.imshow(raw, cmap='gray')` then `ax.imshow(np.ma.masked_where(labels==0, labels), cmap='nipy_spectral', alpha=0.4)`
- **QC overlay with measurement coloring**: build float image where each object = its measurement value, overlay with colorbar
- **Save at publication quality**: `plt.savefig("fig.png", dpi=300, bbox_inches="tight")`
