---
name: bioimage-analysis
description: >
  Guide users through image segmentation and measurement for biological microscopy data.
  Covers classical (scikit-image, FIJI) and deep learning (Cellpose, StarDist, nnUNetv2)
  approaches. Use this skill when users mention: cell segmentation, nucleus detection,
  object measurement, scikit-image, Cellpose, StarDist, napari, FIJI, image quantification,
  morphological measurements, intensity measurements, fluorescence analysis, or any task
  involving identifying and measuring objects in microscopy images. Even if the user just
  says "I have microscopy images and need to analyze them", use this skill.
---

# Bioimage Analysis

Three rules:

1. **Look first, then propose.** Assess the image and context before running anything.
2. **Show results in the best available viewer.** Find napari, connect to it, use it.
3. **Infer from context, don't interrogate.** One confirmation, then execute.

---

## Persistent State

This skill uses two state files to maintain context across steps and sessions.
Store them in `.bioimage-analysis/` in the project or working directory.

### STATE.md — working memory (always loaded)

**On every activation, check for `.bioimage-analysis/STATE.md` and read it first.**
This file is Claude's memory. It contains environment scan results, viewer status,
and history of what's been done. If it exists, you already know the user's setup —
don't re-scan.

**Update STATE.md after every significant action:** env scan, viewer connection,
each analysis step, errors. See `references/state-templates.md` for the format.

If STATE.md doesn't exist, this is a first run — create it during the assess step.

### ANALYSIS.md — the analysis plan (persists across sessions)

Generated during planning. Contains the biological question, data description,
pipeline steps, tool choices, and parameters. Every execution step reads this to
know what to do and why.

If the user returns to a previous analysis, ANALYSIS.md tells Claude the full
context without re-explaining.

---

## On Activation

1. **Check for `.bioimage-analysis/STATE.md`** — if it exists, read it. You may
   already know the environments, viewer status, and analysis progress.
2. **Start talking immediately.** Don't block on env scanning.
3. If STATE.md shows viewer_connected: false but napari_available: true → offer
   to connect before doing anything else.

If this is a first run (no STATE.md): greet the user and ask what they're working
with, while spawning the env scanner in the background.

---

## Workflow

### 1. Assess

**Read the image.** Report shape, dtype, channels. Scan the directory for context —
custom models, config files, other images.

**Find tools.** If STATE.md exists and has env info, use it — don't re-scan. If not,
spawn background env scanner (see `references/environment.md`). Write results to
STATE.md immediately when done.

**Find a viewer.** Check STATE.md for napari status. If napari is available but not
connected, offer to connect NOW — before running any analysis.

**Report everything together.** One message, one confirmation, then execute.

**Write ANALYSIS.md** with the plan:
```
## Objective
Count enteric neurons (Hu+) in fluorescence images

## Data
- img_hu.tif: 1024x1024, uint16, Hu staining
- Custom StarDist model in data directory

## Pipeline
1. Normalize (1st-99th percentile)
2. Segment (custom StarDist model)
3. QC (overlay in napari, check dense ganglia)
4. Measure (count, area, mean intensity)
5. Export (labels.tif + measurements.csv)

## Environment
- analysis: stardist env (StarDist 0.8.5)
- viewer: everyday_env (napari 0.5.0)
```

### 2. Connect viewer

**Read STATE.md** — check `napari_available` and `viewer_connected`.

If napari available but not connected:
- Install napari-mcp if needed: `pip install napari-mcp`
- Launch napari, connect via MCP
- Update STATE.md: `viewer_connected: true`

See `references/environment.md` for install/launch/connect patterns.

Never write standalone viewer scripts. If setup fails, fall back to matplotlib
and update STATE.md: `viewer_connected: false, fallback: matplotlib`.

### 3. Execute

**Read ANALYSIS.md** for what to do. **Read STATE.md** for how to display results.

After every step that produces visual output:

**If STATE.md shows viewer_connected: true** → push to napari, screenshot, evaluate,
report your assessment. Don't say "please check the output."

**If viewer_connected: false** → matplotlib in conversation, or script for local.

**Update STATE.md** after each step:
```
### History
- [13:05] Assessed image: Hu staining, 1024x1024
- [13:06] Connected to napari via everyday_env
- [13:07] StarDist segmentation: 132 neurons detected (custom model, default thresholds)
```

**Present results as preliminary.** "Here's a first pass — does this look right?"

### 4. Iterate

Adjust and re-run based on feedback. Update STATE.md with each attempt.
If not working after 2-3 tries, escalate:
1. Adjust parameters
2. Try different tool/model
3. Search forum.image.sc
4. Interactive annotation (20-50 objects) → fine-tune
5. Custom training — last resort

### 5. Measure and export

Save organized outputs:
```
analysis/
├── 02_segmentation/    # Label masks
├── 03_qc/              # Overlay previews
├── 04_measurements/    # CSV tables
└── analysis_log.md     # Parameters, versions, counts
```

Update STATE.md with final results. Only create folders that are used.

---

## Key Behaviors

### Infer, don't ask

- Custom model in the directory → use it
- File named `img_hu.tif` in `stardist_neuron/` → Hu staining, neuronal
- User said "count neurons" → they want counts
- STATE.md says napari available → offer to connect

One question max. Never present numbered option lists.

### Start simple

Thresholding before DL. Pretrained before custom. Defaults before tuning.

### Don't over-tune

If parameters need drastic per-image adjustment, the approach is wrong.

### Check versions before recommending

Cellpose 2 has no cyto3. Cellpose 4 may have none of the old models.
Read STATE.md env versions. See `references/environment.md` for gotchas.

### forum.image.sc

Search early. Many problems are solved. Suggest user post if genuinely novel.

### Connect back to biology

Answering the biological question is the endpoint, not measurements.

---

## Reference Files

- `references/environment.md` — env scanning, version checks, napari setup
- `references/state-templates.md` — STATE.md and ANALYSIS.md formats
- `references/segmentation.md` — approaches (threshold, Cellpose, StarDist, nnUNet)
- `references/measurements.md` — what to measure, biological meaning, pitfalls
- `references/preprocessing.md` — illumination, background, noise, normalization
- `references/quality-control.md` — validation checklist after segmentation
