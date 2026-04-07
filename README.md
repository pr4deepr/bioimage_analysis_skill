# Bioimage Analysis Skill

A Claude Code skill for biological image segmentation and measurement. Guides users from raw microscopy images to quantitative results with napari viewer integration and callable decision logic.

## What It Does

- **Assesses images** — reads metadata, checks directory for models and context
- **Picks the right tool** — callable decision logic selects segmentation approach based on object type, modality, and morphology
- **Catches version pitfalls** — validates model names against installed package versions (Cellpose 2→3→4, nnUNet v1→v2, aicsimageio→bioio)
- **Connects to napari** — MCP-based viewer integration for visual feedback
- **Runs analysis** — end-to-end pipelines for single images, batch, large 2D (tiled), and 3D/timelapse
- **Checks your work** — programmatic pitfall detection before measurements, QC checklist

Supports scikit-image, Cellpose, StarDist, nnUNetv2, napari, BioIO, and more.

## Install

### Claude Code

```bash
# Global (all projects)
git clone https://github.com/pr4deepr/bioimage-analysis-skill.git
cp -r bioimage-analysis-skill ~/.claude/skills/bioimage-analysis

# Local (current project only)
cp -r bioimage-analysis-skill .claude/skills/bioimage-analysis
```

The skill triggers automatically when you mention image analysis, segmentation, cell counting, etc.

## Quick Start

Just describe what you need:

```
I'd like to count enteric neurons in: /path/to/img_hu.tif
```

The skill will:
1. Read your image and check the directory for context
2. Check the active Python environment for installed tools
3. Propose an analysis plan and wait for your approval
4. Execute step by step with visual feedback at each stage

## How It Works

### Four Rules

1. **Look first, then propose.** Assess image and context before running anything.
2. **Close the feedback loop.** Show results visually, evaluate them, ask the user before proceeding.
3. **Ask focused questions, propose the plan, execute after approval.** Up to 2-3 questions, then a concrete plan the user approves.
4. **Show results in the best available viewer.** napari via MCP if available, matplotlib otherwise.

### napari Integration

Uses [napari-mcp](https://github.com/royerlab/napari-mcp) to connect Claude to napari via MCP:
- **Standalone**: napari-mcp launches its own viewer when Claude connects
- **Plugin**: connects to an already-running napari session

Setup: see `references/visualization.md` and `references/environment.md`.

## Slash Commands

| Command | What it does |
|---|---|
| `/bio` | Start full workflow — assess, propose, execute |
| `/bio:qc` | Run QC checklist on segmentation results |

## Files

```
bioimage-analysis/
├── SKILL.md                         # Core skill definition and workflow
└── references/
    ├── bioimage_utils.py            # Callable decision logic and ResultsManager
    ├── segmentation.md              # Approaches, version-specific code, large data
    ├── environment.md               # Version gotchas, GPU, napari-mcp setup
    ├── measurements.md              # What to measure, biological meaning, pitfalls
    ├── preprocessing.md             # When and how to preprocess
    ├── quality-control.md           # Validation checklist
    ├── visualization.md             # napari-mcp and matplotlib patterns
    └── cookbook-pipeline.md          # End-to-end pipelines (single, batch, tiled, 3D)
```

### `bioimage_utils.py` functions

| Function | Purpose |
|---|---|
| `pick_segmentation_tool()` | Select tool/model based on object type, modality, morphology |
| `validate_model_for_version()` | Check model name against installed package version |
| `clean_labels()` | Post-process labels: remove border objects, filter small fragments |
| `detect_measurement_pitfalls()` | Check for edge objects, saturation, missing calibration |
| `estimate_memory()` | Estimate RAM usage, warn if data won't fit |
| `ResultsManager` | Organize outputs into timestamped folders with manifest |

## Supported Tools

- **scikit-image** — thresholding, morphology, watershed, regionprops
- **Cellpose** (2.x / 3.x / 4.x) — DL instance segmentation
- **StarDist** — DL segmentation for convex objects (nuclei)
- **nnUNetv2** — self-configuring DL segmentation (custom training)
- **napari** — interactive viewer, QC overlays, annotation
- **BioIO** — read microscopy formats (CZI, LIF, ND2, OME-TIFF) with lazy dask loading

## Resources

- [napari-mcp](https://github.com/royerlab/napari-mcp) — napari MCP server
- [forum.image.sc](https://forum.image.sc) — bioimage analysis community forum
- [fiji_mcp](https://github.com/NicoKiaru/fiji_mcp) — FIJI MCP server (proof of concept)

## Contributing

Contributions welcome — especially:
- New segmentation approaches in `references/segmentation.md`
- Tool-specific tips in `references/environment.md`
- Example analyses with test data
- Bug reports from real usage

## License

BSD-3-Clause
