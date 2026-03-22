# Results Management

How to organize analysis outputs so they stay navigable across multiple runs,
iterations, and images. Every analysis uses a **run folder** with **step folders**
inside, plus an **HTML manifest** that auto-opens in the browser.

---

## Directory Structure

```
analysis/
├── run_001_stardist_nuclei/
│   ├── 01_raw/
│   │   └── raw_preview.png
│   ├── 02_segmentation/
│   │   ├── labels.tif
│   │   └── segmentation_overlay.png
│   ├── 03_qc/
│   │   ├── qc_overlay.png
│   │   ├── qc_report.txt
│   │   └── histogram_areas.png
│   ├── 04_measurements/
│   │   ├── measurements.csv
│   │   └── boxplot_area.png
│   └── manifest.html          ← auto-opens in browser
├── run_002_cellpose_retry/
│   └── ...
└── index.html                 ← overview of all runs
```

**Naming convention:** `run_NNN_short_description/` where NNN auto-increments
and the description summarizes the approach (e.g., `stardist_nuclei`,
`cellpose_diameter30`, `threshold_retry`).

---

## Results Manager

Use this at the start of every analysis. It creates the folder structure and
provides `save()` and `show()` methods that route files to the right step folder.

```python
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime


class ResultsManager:
    """Manages analysis outputs: run folders, step folders, manifest.

    Usage:
        results = ResultsManager("analysis", "stardist_nuclei")
        results.save_figure(fig, "raw_preview.png", step="01_raw")
        results.save_data(labels, "labels.tif", step="02_segmentation")
        results.log("Segmented 247 nuclei with StarDist 2D_versatile_fluo")
        results.write_manifest()  # auto-opens in browser
    """

    STEPS = [
        "01_raw",
        "02_segmentation",
        "03_qc",
        "04_measurements",
    ]

    def __init__(self, base_dir="analysis", description="analysis"):
        self.base = Path(base_dir)
        self.base.mkdir(exist_ok=True)

        # Auto-increment run number
        existing = sorted(self.base.glob("run_*"))
        next_num = 1
        if existing:
            try:
                last_num = int(existing[-1].name.split("_")[1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = len(existing) + 1

        self.run_name = f"run_{next_num:03d}_{description}"
        self.run_dir = self.base / self.run_name
        self.run_dir.mkdir(exist_ok=True)

        # Create step folders
        for step in self.STEPS:
            (self.run_dir / step).mkdir(exist_ok=True)

        # Log entries for manifest
        self._log = []
        self._files = []  # (step, filename, description)
        self._params = {}
        self._qc_results = None

        self.log(f"Run started: {description}")

    def step_dir(self, step):
        """Get path to a step folder. Creates it if it doesn't exist."""
        d = self.run_dir / step
        d.mkdir(exist_ok=True)
        return d

    def save_figure(self, fig, filename, step, description="", dpi=150, show=True):
        """Save a matplotlib figure to the correct step folder and auto-open."""
        path = self.step_dir(step) / filename
        fig.savefig(str(path), dpi=dpi, bbox_inches="tight", facecolor="white")
        import matplotlib.pyplot as plt
        plt.close(fig)
        self._files.append((step, filename, description))
        self.log(f"Saved {step}/{filename}" + (f" — {description}" if description else ""))
        if show:
            self._open_file(path)
        return path

    def save_image(self, array, filename, step, description=""):
        """Save a numpy array as TIFF (for labels, masks, etc.)."""
        import numpy as np
        import tifffile
        path = self.step_dir(step) / filename
        tifffile.imwrite(str(path), array.astype(np.int32), compression="zlib")
        self._files.append((step, filename, description))
        self.log(f"Saved {step}/{filename}" + (f" — {description}" if description else ""))
        return path

    def save_csv(self, df, filename, step, description=""):
        """Save a pandas DataFrame as CSV."""
        path = self.step_dir(step) / filename
        df.to_csv(str(path), index=False)
        self._files.append((step, filename, description))
        self.log(f"Saved {step}/{filename} ({len(df)} rows)" +
                 (f" — {description}" if description else ""))
        return path

    def save_text(self, text, filename, step):
        """Save plain text (QC reports, logs, etc.)."""
        path = self.step_dir(step) / filename
        path.write_text(text)
        self._files.append((step, filename, ""))
        return path

    def set_params(self, **kwargs):
        """Record analysis parameters for the manifest."""
        self._params.update(kwargs)

    def set_qc(self, qc_results):
        """Record QC results for the manifest."""
        self._qc_results = qc_results

    def log(self, message):
        """Add a timestamped log entry."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}] {message}")

    def write_manifest(self, show=True):
        """Write an HTML manifest summarizing this run and auto-open it."""
        html = self._build_manifest_html()
        manifest_path = self.run_dir / "manifest.html"
        manifest_path.write_text(html)

        # Also update the top-level index
        self._update_index()

        if show:
            self._open_file(manifest_path)
        return manifest_path

    def _open_file(self, path):
        """Open a file with the OS default application."""
        path = str(Path(path).resolve())
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _build_manifest_html(self):
        """Build an HTML page summarizing this run."""
        params_html = ""
        if self._params:
            rows = "\n".join(
                f"<tr><td><code>{k}</code></td><td>{v}</td></tr>"
                for k, v in self._params.items()
            )
            params_html = f"""
            <h2>Parameters</h2>
            <table><thead><tr><th>Parameter</th><th>Value</th></tr></thead>
            <tbody>{rows}</tbody></table>"""

        qc_html = ""
        if self._qc_results:
            qc_rows = []
            for name, result in self._qc_results.items():
                status = "PASS" if result["passed"] else "WARN"
                color = "#2d7d2d" if result["passed"] else "#c0392b"
                qc_rows.append(
                    f'<tr><td style="color:{color};font-weight:bold">{status}</td>'
                    f'<td>{name}</td><td>{result["message"]}</td></tr>'
                )
            qc_html = f"""
            <h2>QC Results</h2>
            <table><thead><tr><th>Status</th><th>Check</th><th>Details</th></tr></thead>
            <tbody>{"".join(qc_rows)}</tbody></table>"""

        # Group files by step
        steps_html = ""
        files_by_step = {}
        for step, fname, desc in self._files:
            files_by_step.setdefault(step, []).append((fname, desc))

        for step in self.STEPS:
            if step not in files_by_step:
                continue
            step_label = step.split("_", 1)[1].replace("_", " ").title()
            items = []
            for fname, desc in files_by_step[step]:
                if fname.endswith((".png", ".jpg", ".jpeg")):
                    items.append(
                        f'<div class="img-card">'
                        f'<a href="{step}/{fname}" target="_blank">'
                        f'<img src="{step}/{fname}" alt="{fname}"></a>'
                        f'<p>{fname}</p>'
                        f'{"<p class=desc>" + desc + "</p>" if desc else ""}'
                        f'</div>'
                    )
                else:
                    items.append(
                        f'<div class="file-card">'
                        f'<a href="{step}/{fname}">{fname}</a>'
                        f'{"<span class=desc> — " + desc + "</span>" if desc else ""}'
                        f'</div>'
                    )
            steps_html += f"<h2>{step_label}</h2><div class='gallery'>{''.join(items)}</div>"

        log_html = "<br>".join(self._log)

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{self.run_name}</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 1200px; margin: 0 auto; padding: 20px; background: #fafafa; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
    h2 {{ color: #555; margin-top: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    th {{ background: #f0f0f0; }}
    .gallery {{ display: flex; flex-wrap: wrap; gap: 16px; }}
    .img-card {{ max-width: 350px; }}
    .img-card img {{ max-width: 100%; border: 1px solid #ccc; border-radius: 4px; }}
    .img-card p {{ margin: 4px 0; font-size: 13px; color: #666; }}
    .file-card {{ padding: 8px 12px; background: #fff; border: 1px solid #ddd;
                  border-radius: 4px; }}
    .file-card a {{ font-family: monospace; }}
    .desc {{ color: #888; font-size: 12px; }}
    .log {{ background: #fff; border: 1px solid #ddd; padding: 12px; font-family: monospace;
            font-size: 12px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }}
</style></head>
<body>
<h1>{self.run_name}</h1>
{params_html}
{qc_html}
{steps_html}
<h2>Log</h2>
<div class="log">{log_html}</div>
</body></html>"""

    def _update_index(self):
        """Update the top-level analysis/index.html with all runs."""
        runs = sorted(self.base.glob("run_*"))
        rows = []
        for run_dir in runs:
            manifest = run_dir / "manifest.html"
            name = run_dir.name
            link = f'<a href="{name}/manifest.html">{name}</a>' if manifest.exists() else name

            # Count files
            n_files = sum(1 for _ in run_dir.rglob("*") if _.is_file() and _.name != "manifest.html")

            # Check QC status from log if available
            rows.append(f"<tr><td>{link}</td><td>{n_files} files</td></tr>")

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Analysis Runs</title>
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 900px; margin: 0 auto; padding: 20px; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #f0f0f0; }}
    tr:hover {{ background: #f5f5f5; }}
</style></head>
<body>
<h1>Analysis Runs</h1>
<table>
<thead><tr><th>Run</th><th>Contents</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body></html>"""

        (self.base / "index.html").write_text(html)
```

---

## Usage in a Pipeline

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tifffile
from stardist.models import StarDist2D
from csbdeep.utils import normalize
from skimage.measure import regionprops_table, regionprops, label as relabel
from skimage.segmentation import clear_border

# ── Initialize results ──
results = ResultsManager("analysis", "stardist_nuclei")

# ── 1. Read ──
image = tifffile.imread("nuclei.tif")
pixel_size_um = 0.325
results.set_params(image="nuclei.tif", pixel_size_um=pixel_size_um)

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
ax.set_title("Raw image")
results.save_figure(fig, "raw_preview.png", step="01_raw", description="Input image")

# ── 2. Segment ──
image_norm = normalize(image, pmin=1, pmax=99.8)
model = StarDist2D.from_pretrained("2D_versatile_fluo")
labels, details = model.predict_instances(image_norm, prob_thresh=0.5, nms_thresh=0.3)
results.set_params(model="StarDist 2D_versatile_fluo", prob_thresh=0.5, nms_thresh=0.3)
results.log(f"Segmented: {labels.max()} objects")

# Post-process
labels = clear_border(labels)
labels = relabel(labels > 0, connectivity=1)
results.log(f"After cleanup: {labels.max()} objects")

# Save labels + overlay
results.save_image(labels, "labels.tif", step="02_segmentation",
                   description=f"{labels.max()} objects")

fig, ax = plt.subplots(figsize=(8, 8))
ax.imshow(image, cmap="gray")
labels_masked = np.ma.masked_where(labels == 0, labels)
ax.imshow(labels_masked, cmap="tab20", alpha=0.4, interpolation="none")
ax.set_title(f"Segmentation: {labels.max()} objects")
results.save_figure(fig, "overlay.png", step="02_segmentation",
                    description="Segmentation overlay")

# ── 3. QC ──
# (run_qc_checks from quality-control.md)
# qc = run_qc_checks(labels, image)
# results.set_qc(qc)
# results.save_text(print_qc_report(qc), "qc_report.txt", step="03_qc")

fig, ax = plt.subplots(figsize=(8, 5))
areas = [p.area * pixel_size_um**2 for p in regionprops(labels)]
ax.hist(areas, bins=30, edgecolor="black", linewidth=0.5, color="#4C72B0")
ax.set_xlabel("Area (µm²)")
ax.set_ylabel("Count")
ax.set_title(f"Size distribution (n={len(areas)})")
results.save_figure(fig, "histogram_areas.png", step="03_qc",
                    description="Object size distribution")

# ── 4. Measure & Export ──
props = pd.DataFrame(regionprops_table(
    labels, intensity_image=image,
    properties=("label", "area", "eccentricity", "solidity",
                "mean_intensity", "max_intensity"),
))
props["area_um2"] = props["area"] * (pixel_size_um ** 2)
results.save_csv(props, "measurements.csv", step="04_measurements",
                 description=f"{len(props)} objects measured")

# ── Write manifest (auto-opens in browser) ──
results.write_manifest()
```

---

## Cleaning Up Old Runs

After iterating, there will be many runs. To clean up:

```python
import shutil
from pathlib import Path

def cleanup_runs(base_dir="analysis", keep_last=3):
    """Delete all but the last N runs. Keeps the most recent ones."""
    runs = sorted(Path(base_dir).glob("run_*"))
    to_delete = runs[:-keep_last] if len(runs) > keep_last else []
    for run_dir in to_delete:
        print(f"Deleting {run_dir.name}")
        shutil.rmtree(run_dir)
    # Regenerate index
    # (re-run ResultsManager._update_index or just delete and re-create)
```

Or manually: delete any `run_NNN_*` folder you don't need. The index.html
regenerates on the next run.

---

## Tips

- **One run per parameter attempt.** Ran StarDist with prob=0.5 and it was too aggressive? Start a new run with prob=0.3. Now you can compare both manifests.
- **Description matters.** Use `ResultsManager("analysis", "cellpose_diam40")` not `ResultsManager("analysis", "test2")`. You'll thank yourself later.
- **The manifest is the entry point.** When reviewing results, open `manifest.html` — it has thumbnails, parameters, QC status, and links to all files.
- **Auto-open behavior:** `save_figure()` opens each image as it's saved (immediate feedback). `write_manifest()` opens the summary at the end. Set `show=False` to suppress auto-opening during batch runs.
