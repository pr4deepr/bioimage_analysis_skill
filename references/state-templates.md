# State Templates

Formats for the persistent state files. Store in `.bioimage-analysis/` directory.

---

## STATE.md

Claude's working memory. **Always read this first on activation.** Update after every
significant action.

### Template

```markdown
# Bioimage Analysis State

## Environment
- conda_path: C:/Users/.../miniconda3/condabin/conda.bat
- analysis_env: stardist
  - path: C:/Users/.../.conda/envs/stardist
  - python: C:/Users/.../.conda/envs/stardist/python.exe
  - stardist: 0.8.5
  - skimage: 0.22.0
  - napari: none
- viewer_env: everyday_env
  - path: C:/Users/.../.conda/envs/everyday_env
  - python: C:/Users/.../.conda/envs/everyday_env/python.exe
  - napari: 0.5.0
  - napari_mcp: 0.0.4
- other_envs_checked: [cellpose, napari-lattice]

## Viewer
- napari_available: true
- napari_mcp_installed: true
- viewer_connected: false
- fallback: matplotlib

## Current Analysis
- image: C:\Users\Pradeep\Desktop\stardist_neuron\img_hu.tif
- image_info: 1024x1024, uint16, single channel, Hu staining
- analysis_plan: .bioimage-analysis/ANALYSIS.md
- current_step: segmentation
- step_status: completed

## History
- [2026-03-12 13:02] Environment scan: found stardist env, everyday_env with napari
- [2026-03-12 13:05] Assessed image: Hu staining, 1024x1024, custom model found
- [2026-03-12 13:06] Segmentation: 132 neurons (pretrained 2D_versatile_fluo, prob=0.48)
- [2026-03-12 13:08] User requested napari visualization
- [2026-03-12 13:09] Connected to napari via everyday_env
```

### Update Rules

**When to update STATE.md:**
- After environment scan completes (write env section)
- After viewer connection attempt (update viewer section)
- After image assessment (write current analysis section)
- After each analysis step (append to history, update current_step)
- After errors (log in history with error details)

**How to update:** Read the current STATE.md, modify the relevant section, write it
back. Don't rewrite the whole file — preserve history.

**On re-activation:** If STATE.md exists and is recent (check history timestamps),
trust it. Don't re-scan environments. Only re-scan if:
- STATE.md is missing
- User asks to re-scan
- A tool fails (env may have changed)

---

## ANALYSIS.md

The analysis plan. Generated during the assess/plan step. Referenced during execution.

### Template

```markdown
# Analysis Plan

## Objective
[Biological question in one sentence]

## Data
- [file path]: [dimensions], [dtype], [description]
- Custom model: [path, if found]
- Number of images: [N]
- Conditions: [treatment groups, if applicable]

## Pipeline
1. **Preprocessing**: [specific steps, or "none needed"]
2. **Segmentation**: [tool, model, starting parameters]
3. **QC**: [what to check — overlay, counts, distributions]
4. **Measurement**: [what to extract — count, area, intensity, etc.]
5. **Export**: [output format — labels.tif, measurements.csv, etc.]

## Environment
- Analysis: [env name] ([tool] [version])
- Viewer: [env name] (napari [version])

## Notes
- [Anything specific — missing config, dense regions, expected challenges]
```

### Update Rules

**Create ANALYSIS.md** after the assess step, before execution begins.

**Update ANALYSIS.md** if the plan changes during iteration (e.g., switched from
custom model to pretrained, changed parameters after QC).

**Don't delete ANALYSIS.md** after completion — it serves as a record of what was done.

---

## Directory Structure

```
.bioimage-analysis/
├── STATE.md              # Working memory (auto-updated)
├── ANALYSIS.md           # Analysis plan (generated, updated)
└── steps/                # Per-step summaries (future use)
    ├── 01-preprocess/
    ├── 02-segment/
    └── 03-measure/
```

Create `.bioimage-analysis/` in the working directory or alongside the data.
If the user has a specific project directory, use that. Otherwise use the directory
containing the image.

---

## Reading State on Activation

On every activation, the first thing to do is:

```
1. Look for .bioimage-analysis/STATE.md
   ├─ Found → read it
   │   ├─ Has env info? → don't re-scan, use cached
   │   ├─ Has viewer info? → check if still connected
   │   ├─ Has current analysis? → offer to continue
   │   └─ napari_available but not connected? → offer to connect
   └─ Not found → first run, proceed with assess workflow
```

This is how Claude "remembers" across sessions. STATE.md is the memory.
