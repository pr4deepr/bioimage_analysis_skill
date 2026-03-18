# Bioimage Analysis Skill Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bioimage analysis skill actionable with runnable code patterns, a leaner core, adaptive user model, robust napari verification, slash commands, and a background env scanner subagent.

**Architecture:** Lean SKILL.md (~150 lines) as orchestrator pointing to task-oriented cookbook files and improved reference files. Cookbooks contain complete, runnable code blocks. Existing conceptual references get inline snippets and cross-references. SKILL.md frontmatter defines slash commands.

**Tech Stack:** Markdown skill files for Claude Code. Code patterns target Python (scikit-image, Cellpose, StarDist, napari, matplotlib, tifffile, BioIO, pandas).

**Spec:** `docs/superpowers/specs/2026-03-18-skill-improvement-design.md`

**Parallelization:** Tasks 1-4 (cookbooks) are independent and can run in parallel. Tasks 6-11 (reference updates) can run in parallel after their respective cookbook dependencies. Task 5 (SKILL.md) depends on Tasks 1-4. Task 12 (README) depends on all others.

---

## File Map

### Files to Create
- `references/cookbook-io.md` — image reading/writing patterns (TIFF, CZI, LIF, ND2, metadata, saving)
- `references/cookbook-segmentation.md` — runnable segmentation code (threshold, watershed, Cellpose, StarDist, post-processing)
- `references/cookbook-visualization.md` — dual napari/matplotlib patterns for every visual + robust napari launch
- `references/cookbook-measurements.md` — regionprops, intensity, export, stats, plots

### Files to Rewrite
- `SKILL.md` — rewrite from scratch: lean core with 4 rules, adaptive user model, slash commands in frontmatter, workflow phases, reference pointers

### Files to Update (add inline code, cross-references)
- `references/measurements.md` — add inline code snippets per measurement type, cross-refs to cookbook
- `references/preprocessing.md` — add inline code snippets per technique
- `references/quality-control.md` — add code for each QC check (napari + matplotlib)
- `references/segmentation.md` — remove duplicate code, add cross-refs to cookbook
- `references/environment.md` — minor cleanup, remove napari launch patterns (moved to cookbook-visualization)
- `references/state-templates.md` — add step_status pattern, validation rule

### Files to Update Last
- `README.md` — update to reflect new structure, slash commands, updated rules

---

### Task 1: Write cookbook-io.md

**Files:**
- Create: `references/cookbook-io.md`

This is a standalone file with no dependencies on other tasks. Contains complete, runnable code patterns for image I/O.

- [ ] **Step 1: Write cookbook-io.md**

Write `references/cookbook-io.md` with these sections and complete code blocks:

**Structure:**
```
# Image I/O Cookbook
## Reading Images
### TIFF with tifffile
### TIFF with skimage.io
### Proprietary formats with BioIO (CZI, LIF, ND2, OME-TIFF)
### Metadata extraction (pixel size, channels, dimensions)
## Writing / Saving
### Save label mask as TIFF
### Save overlay as PNG
### Save measurements as CSV
```

**Requirements for each code block:**
- Complete imports at the top of each block
- Clear variable names (`image`, `labels`, `pixel_size_um`, `measurements_df`)
- Inline comments explaining what each step does (for non-Python users)
- Input/output description above each block
- For BioIO: show how to extract individual channels from multi-channel data
- For metadata: show how to get pixel size from TIFF tags and from BioIO
- For CSV: use pandas DataFrame with meaningful column names and units in headers

- [ ] **Step 2: Review and verify**

Read the file back. Check:
- Every code block has imports
- Variable names are consistent across blocks (same image loaded in reading can be used in writing examples)
- Comments are helpful for someone who knows microscopy but not Python
- No placeholder code — everything is runnable

- [ ] **Step 3: Commit**

```bash
git add references/cookbook-io.md
git commit -m "feat: add cookbook-io.md with image read/write patterns"
```

---

### Task 2: Write cookbook-segmentation.md

**Files:**
- Create: `references/cookbook-segmentation.md`

Standalone. Contains complete segmentation code patterns with version annotations for DL tools.

- [ ] **Step 1: Write cookbook-segmentation.md**

Write `references/cookbook-segmentation.md` with these sections:

**Structure:**
```
# Segmentation Cookbook
## Classical Approaches
### Otsu thresholding + connected components
### Adaptive thresholding (uneven illumination)
### Threshold + distance transform + watershed (touching objects)
## Deep Learning — Cellpose
### Cellpose >= 3.0 (cyto2, cyto3, nuclei)
### Cellpose 2.x (cyto, cyto2, nuclei)
### Cellpose with custom model
## Deep Learning — StarDist
### StarDist (2D_versatile_fluo)
### StarDist with custom model
## Post-Processing
### Filter small objects by area
### Remove edge-touching objects
### Fill holes
### Smooth boundaries (morphological closing)
### Combined post-processing pipeline
```

**Requirements:**
- Every code block: complete imports, input description, output description, key parameters with comments explaining what they control
- Version annotations: `# Cellpose >= 3.0` or `# Cellpose 2.x` at top of each DL block
- For Cellpose: explain `diameter`, `flow_threshold`, `cellprob_threshold` in comments
- For StarDist: explain `prob_thresh`, `nms_thresh` in comments
- For classical: explain threshold method choice in comments
- Post-processing: show as individual steps AND as a combined pipeline function
- Each section starts with a 1-2 line "When to use" note

- [ ] **Step 2: Review and verify**

Read the file back. Check:
- Version annotations present on all DL blocks
- Parameters are explained in comments, not just named
- Post-processing pipeline is composable (each step works independently)
- Classical approaches come before DL (simple first)

- [ ] **Step 3: Commit**

```bash
git add references/cookbook-segmentation.md
git commit -m "feat: add cookbook-segmentation.md with runnable segmentation patterns"
```

---

### Task 3: Write cookbook-visualization.md

**Files:**
- Create: `references/cookbook-visualization.md`

Standalone. The most critical cookbook — contains the visual feedback loop patterns and robust napari launch/verification.

- [ ] **Step 1: Write cookbook-visualization.md**

Write `references/cookbook-visualization.md` with these sections:

**Structure:**
```
# Visualization Cookbook

## napari Launch & Verification
### Install napari-mcp
### Launch napari-mcp (Windows)
### Launch napari-mcp (macOS/Linux)
### Verify connection (check-before-first-use)
### Handle launch failure

## Showing Results — napari
### Add raw image
### Add segmentation overlay (labels on image)
### Side-by-side comparison
### QC overlay (outlines colored by measurement)
### Take screenshot via MCP

## Showing Results — matplotlib
### Show raw image
### Show segmentation overlay
### Side-by-side comparison
### QC overlay
### Save figure

## Measurement Visualizations (both viewers)
### Histogram of object areas
### Histogram of intensities
### Box plot per condition
```

**Requirements:**
- **napari launch section** implements the check-before-first-use pattern from spec Section 6:
  1. Launch with stderr to temp file
  2. Wait 5 seconds, check process alive, read stderr if dead
  3. Attempt MCP `session_information()` once
  4. Update STATE.md only on confirmed success
  5. Show actual error on failure
  6. Pattern for retry at next visual step
- **Handle launch failure section** must cover two spec edge cases (Section 10):
  - pip install failure: if `pip install napari-mcp` fails (corporate/HPC network restrictions), suggest `conda install` or manual installation, then proceed with matplotlib
  - napari version mismatch: check napari version from STATE.md before installing napari-mcp; if napari < 0.5.0, warn about potential incompatibility
- **Every visual pattern** has both napari AND matplotlib versions — clearly labeled, same visual result
- napari patterns use MCP tool calls (document the expected tool names and parameters)
- matplotlib patterns produce publication-quality figures (proper axes, labels, colorbars)
- Include a "which viewer" decision snippet that reads STATE.md viewer_connected field

- [ ] **Step 2: Review and verify**

Read the file back. Check:
- napari launch captures stderr, verifies connection with actual MCP call, never claims connected without proof
- Every napari pattern has a matplotlib equivalent
- matplotlib figures have proper labels, titles, colorbars
- The viewer decision snippet is clear and reusable

- [ ] **Step 3: Commit**

```bash
git add references/cookbook-visualization.md
git commit -m "feat: add cookbook-visualization.md with dual viewer patterns and robust napari launch"
```

---

### Task 4: Write cookbook-measurements.md

**Files:**
- Create: `references/cookbook-measurements.md`

Standalone. Contains measurement extraction, export, and basic statistical visualization.

- [ ] **Step 1: Write cookbook-measurements.md**

Write `references/cookbook-measurements.md` with these sections:

**Structure:**
```
# Measurements Cookbook

## Morphology Measurements
### Basic regionprops (area, eccentricity, solidity, perimeter)
### Calibrated measurements (pixels to um)

## Intensity Measurements
### Mean, max, integrated intensity per object
### Multi-channel intensity (measure channel B using channel A labels)
### Background-subtracted intensity (annular region)

## Spatial Measurements
### Nearest-neighbor distance
### Local density (neighbor count within radius)

## Export
### Measurements to CSV with units
### Summary statistics table

## Basic Plots
### Box plot per condition
### Histogram of areas
### Scatter: area vs intensity
```

**Requirements:**
- regionprops: show how to create props and extract into a pandas DataFrame in one pattern
- Calibrated measurements: show pixel_size conversion with comment about checking metadata
- Multi-channel intensity: show how to use labels from one channel to measure another
- Annular background: show dilation + subtraction method with scikit-image
- CSV export: include units in column names (e.g., `area_um2`, `mean_intensity_au`)
- Plots: use matplotlib with publication-ready styling (labeled axes, appropriate font sizes)

- [ ] **Step 2: Review and verify**

Read the file back. Check:
- DataFrame creation from regionprops is clear and complete
- Units are included in column names
- Plots have labeled axes
- Background subtraction method is correct (dilate labels, subtract from mask, measure annular region)

- [ ] **Step 3: Commit**

```bash
git add references/cookbook-measurements.md
git commit -m "feat: add cookbook-measurements.md with extraction, export, and plot patterns"
```

---

### Task 5: Rewrite SKILL.md

**Files:**
- Rewrite: `SKILL.md`

Depends on Tasks 1-4 (cookbooks must exist to reference). This is the core skill file — rewrite from scratch to be lean (~150 lines max).

- [ ] **Step 1: Read current SKILL.md**

Read the current `SKILL.md` to understand what to preserve vs cut.

- [ ] **Step 2: Write new SKILL.md**

Rewrite `SKILL.md` with this structure (~150 lines max):

```
---
name: bioimage-analysis
description: >
  Guide users through image segmentation and measurement for biological
  microscopy data. Covers classical (scikit-image, FIJI) and deep learning
  (Cellpose, StarDist, nnUNetv2) approaches. Use this skill when users mention:
  cell segmentation, nucleus detection, object measurement, scikit-image,
  Cellpose, StarDist, napari, FIJI, image quantification, morphological
  measurements, intensity measurements, fluorescence analysis, or any task
  involving identifying and measuring objects in microscopy images.
commands:
  - name: bio
    description: Start bioimage analysis workflow
  - name: bio:plan
    description: Assess image and create analysis plan
  - name: bio:run
    description: Execute existing analysis plan
  - name: bio:qc
    description: Run QC checklist on segmentation results
  - name: bio:measure
    description: Extract measurements from labels
  - name: bio:status
    description: Show current analysis state
---

# Bioimage Analysis

Four rules:
1. **Look first, then propose.** ...
2. **Close the feedback loop.** ...
3. **Ask focused questions, then execute.** ...
4. **Show results in the best available viewer.** ...

---

## User Interaction
[Adaptive model: gauge from context, question budget 2-3, never ask
technical questions, adapt code presentation, report in scientific terms]

---

## Persistent State
[Brief — STATE.md and ANALYSIS.md, check on activation, reference
state-templates.md for formats]

---

## On Activation
[Check STATE.md, spawn env scanner if first run, greet user, start asking
questions, offer napari if available but not connected]

---

## Workflow
### 1. Assess
### 2. Connect viewer
### 3. Execute
### 4. Iterate
### 5. Measure & export

[Each phase: 3-5 lines max. Reference cookbook files for code.
Reference quality-control.md for QC. Every visual step: check
viewer_connected, use napari or matplotlib accordingly.]

---

## Slash Commands
[Table: /bio, /bio:plan, /bio:run, /bio:qc, /bio:measure, /bio:status
with one-line behavior descriptions]

---

## Reference Files
[List of all reference and cookbook files with one-line descriptions]
```

**Key requirements:**
- ~150 lines max (current is 203)
- NO code examples in SKILL.md — all code in cookbooks
- 4 rules (not 3): add "Close the feedback loop"
- User interaction section: adaptive model, 2-3 questions, scientific language
- Viewer: napari preferred, matplotlib first-class, offer setup once
- Every workflow phase references the relevant cookbook/reference file
- Slash commands table
- Subagent: In "On Activation" section, document the env scanner subagent pattern — use `Agent` tool with `run_in_background: true`, writes to STATE.md, main conversation notified on completion, fallback to quick inline check if env needed before agent finishes
- Key Behaviors to preserve in rules or workflow: "Start simple" (thresholding before DL), "Don't over-tune", "forum.image.sc" (search early), "Connect back to biology". Drop "One question max" (replaced by 2-3 question budget).

- [ ] **Step 3: Verify line count and completeness**

Count lines. Must be <= 150. Check that:
- All 4 rules are present with explanations
- User interaction model covers gauging, question budget, code presentation, scientific terms
- All 6 slash commands are listed
- All cookbook and reference files are listed
- Workflow phases reference cookbooks, not inline code
- Subagent spawn is mentioned in On Activation

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "feat: rewrite SKILL.md — lean core with 4 rules, slash commands, adaptive user model"
```

---

### Task 6: Update references/segmentation.md

**Files:**
- Modify: `references/segmentation.md`

Depends on Task 2 (cookbook-segmentation.md must exist). Remove code that now lives in cookbook, add cross-references.

- [ ] **Step 1: Read current segmentation.md**

Read `references/segmentation.md` and identify code blocks or pseudo-code that duplicates cookbook-segmentation.md.

- [ ] **Step 2: Update segmentation.md**

Changes:
- Keep all conceptual content (when to use, decision flow, generalization warnings, escalation path)
- Remove any code blocks that duplicate cookbook-segmentation.md content
- Add cross-references after each approach section:
  ```
  > See: cookbook-segmentation.md § Otsu thresholding + connected components
  ```
- Keep the pretrained model table (Cellpose models, StarDist models, etc.) — this is reference, not code
- Keep the post-processing descriptions but add cross-ref to cookbook post-processing section
- Keep "Choosing Between Approaches" and "Generalization" sections unchanged

- [ ] **Step 3: Commit**

```bash
git add references/segmentation.md
git commit -m "refactor: segmentation.md — remove code duplication, add cookbook cross-refs"
```

---

### Task 7: Update references/measurements.md

**Files:**
- Modify: `references/measurements.md`

Depends on Task 4 (cookbook-measurements.md must exist for cross-refs).

- [ ] **Step 1: Read current measurements.md**

Read `references/measurements.md`.

- [ ] **Step 2: Add inline snippets and cross-references**

Changes:
- After each measurement in the Morphology table, add a short inline snippet (imports excluded, 2-4 lines):
  ```python
  # Area in calibrated units
  areas_um2 = [p.area * (pixel_size ** 2) for p in props]
  ```
- After each measurement in the Intensity table, add inline snippet:
  ```python
  # Mean intensity per object
  mean_intensities = [p.mean_intensity for p in props]
  ```
- After the Morphology section: `> See: cookbook-measurements.md § Morphology Measurements`
- After the Intensity section: `> See: cookbook-measurements.md § Intensity Measurements`
- After the Spatial section: `> See: cookbook-measurements.md § Spatial Measurements`
- Keep all pitfalls content unchanged — it's excellent
- Keep "Choosing What to Measure" unchanged

- [ ] **Step 3: Commit**

```bash
git add references/measurements.md
git commit -m "enhance: measurements.md — add inline code snippets and cookbook cross-refs"
```

---

### Task 8: Update references/preprocessing.md

**Files:**
- Modify: `references/preprocessing.md`

Standalone update — no cookbook dependency (preprocessing doesn't have its own cookbook, snippets go inline).

- [ ] **Step 1: Read current preprocessing.md**

Read `references/preprocessing.md`.

- [ ] **Step 2: Add inline code snippets**

After each technique's description, add a short inline snippet (3-6 lines, imports excluded). Specifically:

**Illumination correction:**
```python
# Flat-field correction: divide image by illumination estimate
corrected = image / illumination_image * illumination_image.mean()
```

**Background subtraction — rolling ball:**
```python
from skimage.restoration import rolling_ball
background = rolling_ball(image, radius=50)
background_removed = image - background
```

**Background subtraction — top-hat:**
```python
from skimage.morphology import disk, white_tophat
background_removed = white_tophat(image, footprint=disk(radius))
```

**Noise reduction — Gaussian:**
```python
from skimage.filters import gaussian
smoothed = gaussian(image, sigma=1.0)
```

**Noise reduction — median:**
```python
from skimage.filters import median
from skimage.morphology import disk
denoised = median(image, footprint=disk(3))
```

**Intensity normalization — percentile:**
```python
import numpy as np
p1, p99 = np.percentile(image, (1, 99))
normalized = np.clip((image - p1) / (p99 - p1), 0, 1).astype(np.float32)
```

**Channel extraction:**
```python
# For multi-channel array with shape (C, Y, X)
dapi_channel = image[0]  # first channel
marker_channel = image[1]  # second channel
```

Keep the existing "Preprocessing Order" section unchanged.

- [ ] **Step 3: Commit**

```bash
git add references/preprocessing.md
git commit -m "enhance: preprocessing.md — add inline code snippets for each technique"
```

---

### Task 9: Update references/quality-control.md

**Files:**
- Modify: `references/quality-control.md`

Depends on Task 3 (cookbook-visualization.md for cross-refs to viewer patterns).

- [ ] **Step 1: Read current quality-control.md**

Read `references/quality-control.md`.

- [ ] **Step 2: Add code for each QC check**

After each of the 6 QC checks, add a code block showing how to perform it. Both napari and matplotlib where visual output is involved.

**1. Visual Overlay:**
```python
# matplotlib
fig, ax = plt.subplots(figsize=(10, 10))
ax.imshow(image, cmap='gray')
ax.contour(labels > 0, colors='cyan', linewidths=0.5)
ax.set_title(f'Segmentation overlay — {labels.max()} objects')
plt.tight_layout()
```
```
> napari: See cookbook-visualization.md § Add segmentation overlay
```

**2. Object Count Sanity:**
```python
n_objects = labels.max()
print(f"Automated count: {n_objects}")
# Compare with manual count from a few representative fields
```

**3. Size Distribution:**
```python
from skimage.measure import regionprops
import matplotlib.pyplot as plt
areas = [p.area * pixel_size**2 for p in regionprops(labels)]
fig, ax = plt.subplots()
ax.hist(areas, bins=50, edgecolor='black')
ax.set_xlabel('Area (um²)')
ax.set_ylabel('Count')
ax.set_title('Object size distribution')
```

**4. Edge Cases:**
```python
# Find images with highest/lowest counts for inspection
from collections import Counter
# counts_per_image = {filename: labels.max() for each image}
# sorted_counts = sorted(counts_per_image.items(), key=lambda x: x[1])
# Inspect: sorted_counts[:3] (lowest) and sorted_counts[-3:] (highest)
```

**5. Measurement Distributions:**
```python
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].hist(areas, bins=50)
axes[0].set_title('Area distribution')
axes[1].hist(mean_intensities, bins=50)
axes[1].set_title('Mean intensity distribution')
axes[2].hist(eccentricities, bins=50)
axes[2].set_title('Eccentricity distribution')
plt.tight_layout()
```

**6. Batch Effects:**
```python
# Plot same measurement across batches for control condition
import pandas as pd
control_data = df[df['condition'] == 'control']
fig, ax = plt.subplots()
control_data.boxplot(column='area_um2', by='batch', ax=ax)
ax.set_title('Area by batch (controls only)')
ax.set_ylabel('Area (um²)')
```

Keep the diagnostic table unchanged.

- [ ] **Step 3: Commit**

```bash
git add references/quality-control.md
git commit -m "enhance: quality-control.md — add code for each QC check"
```

---

### Task 10: Update references/environment.md

**Files:**
- Modify: `references/environment.md`

Depends on Task 3 (cookbook-visualization.md must contain the canonical napari launch patterns).

- [ ] **Step 1: Read current environment.md**

Read `references/environment.md`.

- [ ] **Step 2: Update environment.md**

Changes:
- Keep: Background Worker Pattern, Steps 1-5, Version Gotchas, Tools Quick Reference
- **Remove** the "Napari Viewer Setup" section (lines 202-247) — this is now in cookbook-visualization.md
- **Replace** removed section with a cross-reference:
  ```
  ## napari Viewer Setup

  > See: cookbook-visualization.md § napari Launch & Verification

  For the canonical napari launch, verification, and fallback patterns.
  ```
- Keep the FIJI section unchanged
- Minor cleanup: ensure the background worker pattern mentions writing `step_status` fields

- [ ] **Step 3: Commit**

```bash
git add references/environment.md
git commit -m "refactor: environment.md — move napari launch to cookbook, add cross-ref"
```

---

### Task 11: Update references/state-templates.md

**Files:**
- Modify: `references/state-templates.md`

Standalone update.

- [ ] **Step 1: Read current state-templates.md**

Read `references/state-templates.md`.

- [ ] **Step 2: Add step_status pattern and validation rule**

Changes:
- In the STATE.md template, add `step_status` field under "Current Analysis":
  ```
  ## Current Analysis
  - image: ...
  - image_info: ...
  - analysis_plan: .bioimage-analysis/ANALYSIS.md
  - current_step: segmentation
  - step_status: in_progress | completed
  ```
- In "Update Rules", add:
  ```
  **Before starting each step:** set `step_status: in_progress`
  **After completing each step:** set `step_status: completed`
  **On re-activation with step_status: in_progress:** the step was interrupted.
  Offer to retry or skip.
  ```
- Add new section "Validation Rules":
  ```
  ## Validation Rules

  On reading STATE.md, check for required sections (Environment, Viewer, History).
  If any are missing or unparseable, treat STATE.md as corrupted — delete it and
  re-scan from scratch. Don't attempt to recover partial state.
  ```

- [ ] **Step 3: Commit**

```bash
git add references/state-templates.md
git commit -m "enhance: state-templates.md — add step_status pattern and validation rules"
```

---

### Task 12: Update README.md

**Files:**
- Modify: `README.md`

Depends on all previous tasks. Update to reflect new structure.

- [ ] **Step 1: Read current README.md**

Read `README.md`.

- [ ] **Step 2: Update README.md**

Changes:
- Update "Three Rules" → "Four Rules" with new rule descriptions
- Add "Slash Commands" section showing the 6 commands
- Update "Files" tree to include the 4 new cookbook files
- Update "How It Works" section to mention adaptive user model
- Update "Persistent State" to mention step_status and validation
- Update roadmap: check off items that are now complete (subagent, slash commands)
- Keep install instructions, supported tools, resources, contributing, license unchanged

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for new skill structure, 4 rules, slash commands"
```
