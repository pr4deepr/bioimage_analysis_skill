# State Templates

Formats for persistent state files. Store in `.bioimage-analysis/` in the project
directory.

**State files are optional.** They help with multi-session analyses but are not
required for single-session work. Don't create them unless the analysis spans
multiple sessions or the user wants to resume later.

---

## When to Create State Files

**Create ANALYSIS.md:** Always — it's the analysis plan and serves as a record.

**Create STATE.md:** Only when:
- The analysis will span multiple sessions (large dataset, batch processing)
- The user explicitly asks to save progress
- You need to track environment info for a complex multi-env setup

**Skip STATE.md when:**
- Single image, single session analysis
- User just wants quick segmentation + measurements
- Environment is straightforward (one active env has everything)

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
- Python: [env name or path] ([tool] [version])
- Viewer: matplotlib (or napari [version] if connected)

## Notes
- [Anything specific — missing config, dense regions, expected challenges]
```

### Update Rules

- **Create** after the assess step, before execution begins
- **Update** if the plan changes during iteration (e.g., switched tool, changed parameters)
- **Don't delete** after completion — it serves as a record of what was done

---

## STATE.md (multi-session only)

Claude's working memory for long-running analyses. Read this first on re-activation.

### Template

```markdown
# Bioimage Analysis State

## Environment
- python: /path/to/env/bin/python
- packages: cellpose=3.1, skimage=0.22, tifffile=2024.1
- viewer: matplotlib (or napari=0.5.x via napari-mcp)

## Current Analysis
- image: /path/to/image.tif
- analysis_plan: .bioimage-analysis/ANALYSIS.md
- current_step: segmentation
- step_status: in_progress | completed

## History
- [2026-03-12 13:02] Assessed image: DAPI nuclei, 1024x1024, uint16
- [2026-03-12 13:05] Segmentation: StarDist 2D_versatile_fluo, 247 objects
- [2026-03-12 13:08] QC passed, proceeding to measurement
```

### Update Rules

- **When to update:** after each completed step, after errors, after env changes
- **On re-activation with `step_status: in_progress`:** the previous step was interrupted. Offer to retry or skip.
- **Validation:** if STATE.md is malformed, delete and recreate from scratch

---

## Directory Structure

```
.bioimage-analysis/
├── ANALYSIS.md           # Analysis plan (always created)
└── STATE.md              # Working memory (multi-session only)
```

Create `.bioimage-analysis/` in the working directory or alongside the data.
