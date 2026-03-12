# Bioimage Analysis Skill

A Claude skill for biological image segmentation and measurement. Guides you from raw microscopy images to quantitative results — with automatic environment detection, napari viewer integration, and persistent state across sessions.

## What It Does

- **Assesses your images** — reads metadata, scans directory for models and context
- **Finds your tools** — scans conda environments by name, checks versions
- **Connects to napari** — installs the connector, launches the viewer, shows results directly
- **Runs analysis** — segmentation, measurement, QC with visual feedback
- **Remembers state** — environment info and analysis progress persist across sessions

Supports scikit-image, Cellpose, StarDist, nnUNetv2, napari, FIJI, and more.

## Install

### Claude Code

Copy the skill folder into your Claude Code skills directory:

```bash
# Global (all projects)
git clone https://github.com/pr4deepr/bioimage-analysis-skill.git
cp -r bioimage-analysis-skill ~/.claude/skills/bioimage-analysis

# Local (current project only)
cp -r bioimage-analysis-skill .claude/skills/bioimage-analysis
```

Then restart Claude Code. The skill triggers automatically when you mention image analysis, segmentation, cell counting, etc.

### Claude Desktop

Claude Desktop doesn't load skills directly, but you can reference the skill files in your system prompt or use the SKILL.md content as a project prompt.


## Quick Start

Just describe what you need:

```
I'd like to count enteric neurons in: "C:\path\to\img_hu.tif"
```

The skill will:
1. Read your image and check the directory for context (custom models, etc.)
2. Scan your conda environments for the right tools
3. Offer to connect to napari for visual feedback
4. Propose a plan, ask for one confirmation, then execute

## How It Works

### Three Rules

1. **Look first, then propose.** Assess image and context before running anything.
2. **Show results in the best available viewer.** Find napari, connect to it, use it.
3. **Infer from context, don't interrogate.** One confirmation, then execute.

### Persistent State

The skill creates a `.bioimage-analysis/` directory with:

- **STATE.md** — cached environment scan, viewer status, analysis history. Loaded on every activation so Claude doesn't re-scan or forget about napari.
- **ANALYSIS.md** — the analysis plan. Persists across sessions so Claude knows the full context.

### Environment Detection

- Scans conda/mamba environments by **name** first (e.g., an env named `cellpose` is checked before generic ones)
- Uses **filesystem checks** (`ls site-packages/`) for speed — no Python startup overhead
- Runs Python version checks only on the 1-2 environments that matter
- Results cached in STATE.md — subsequent activations skip scanning

### napari Integration

Uses [napari-mcp](https://github.com/royerlab/napari-mcp) to connect Claude to your napari viewer. Claude can:
- Push images and labels directly into napari
- Take screenshots to evaluate segmentation results
- Iterate based on what it sees — no "please check the output"

If napari-mcp isn't installed, the skill offers to set it up (`pip install napari-mcp`).

## Files

```
bioimage-analysis/
├── SKILL.md                         # Core skill (202 lines)
└── references/
    ├── environment.md               # Env scanning, versions, napari setup
    ├── state-templates.md           # STATE.md and ANALYSIS.md formats
    ├── segmentation.md              # Segmentation approaches
    ├── measurements.md              # Feature extraction and pitfalls
    ├── preprocessing.md             # Image preparation
    └── quality-control.md           # Validation checklist
```

## Supported Tools

### Python
- **scikit-image** — thresholding, morphology, watershed, regionprops
- **Cellpose** — DL instance segmentation (cells, nuclei)
- **StarDist** — DL segmentation for nuclei
- **nnUNetv2** — self-configuring DL segmentation
- **napari** — viewer, QC, annotation
- **BioIO** — read microscopy formats (CZI, LIF, ND2, OME-TIFF)

### FIJI
- **Bio-Formats**, **Threshold**, **Analyze Particles**, **MorphoLibJ**, **StarDist plugin**

## Roadmap

- [x] Core skill with three rules
- [x] Persistent state (STATE.md, ANALYSIS.md)
- [x] Environment scanning with filesystem-first detection
- [x] napari-mcp integration
- [ ] Subagent architecture (env scanner, executor, QC verifier)
- [ ] `/bio:*` slash commands (plan, execute, verify, progress, quick)
- [ ] FIJI MCP integration (fiji_mcp)
- [ ] Example analyses with test data

## Resources

- [napari-mcp](https://github.com/royerlab/napari-mcp) — napari MCP server
- [fiji_mcp](https://github.com/NicoKiaru/fiji_mcp) — FIJI MCP server (proof of concept)
- [forum.image.sc](https://forum.image.sc) — bioimage analysis community forum
- [get-shit-done](https://github.com/gsd-build/get-shit-done) — architecture inspiration

## Contributing

Contributions welcome — especially:
- New segmentation approaches in `references/segmentation.md`
- Tool-specific tips in `references/environment.md`
- Example analyses with test data
- Bug reports from real usage

## License

BSD-3-Clause
