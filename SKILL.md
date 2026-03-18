---
name: bioimage-analysis
description: >
  Guide users through image segmentation and measurement for biological
  microscopy data. Covers classical (scikit-image, FIJI) and deep learning
  (Cellpose, StarDist, nnUNetv2) approaches. Use this skill when users mention:
  cell segmentation, nucleus detection, object measurement, scikit-image,
  Cellpose, StarDist, napari, FIJI, image quantification, morphological
  measurements, intensity measurements, fluorescence analysis, or any task
  involving identifying and measuring objects in microscopy images. Even if the
  user just says "I have microscopy images and need to analyze them", use this skill.
commands:
  - name: bio
    description: Start bioimage analysis workflow
  - name: bio:qc
    description: Run QC checklist on segmentation results
---

# Bioimage Analysis

Four rules:
1. **Look first, then propose.** Assess the image and context before running anything.
2. **Close the feedback loop.** Every step that produces output: show it visually (napari preferred, matplotlib always available), assess it yourself, ask user to evaluate before proceeding. Never say "check the output."
3. **Ask focused questions, propose the plan, then execute after approval.** Up to 2-3 questions to understand the biological question and data. Infer everything else from context. Then present a concrete analysis plan with expected outputs and wait for the user to approve before running anything.
4. **Show results in the best available viewer.** If napari MCP tools are available, use them. Otherwise use matplotlib. Offer napari setup once if available but not connected.

## User Interaction

- Gauge user level from context: terminology, file paths, how they describe their problem
- "Segment nuclei using StarDist" → minimal questions, they know what they want
- "I have microscopy images" → more guidance needed
- Question budget: up to 3 focused questions, then propose the plan
- Priority: (1) biological question, (2) what's in the image, (3) how results will be used
- Never ask: technical implementation, environment, or "would you like me to..." questions
- Adapt: biology terms → run directly, explain in scientific terms. Code terms → show code
- Report results in scientific language matching the user's domain

## Workflow

### 1. Assess
Read the image, scan directory for context (custom models, configs, other images). Check the active Python environment inline — run `which python` or `where python`, then check installed packages with a quick `python -c "import ..."`. No background scanner needed.

### 2. Propose (CRITICAL — do not skip)
Present the analysis plan to the user and **wait for explicit approval** before executing. The proposal must include:

```
## Proposed Analysis

**Your question:** [biological question in one sentence]

**What I see:** [channels, dimensions, bit depth, approximate object count, number of images, conditions]

**Proposed pipeline:**
1. [Preprocessing step, or "none needed"]
2. [Segmentation tool + model + why this choice]
3. [What to measure and why]
4. [Export format]

**Expected outputs:**
- [specific files, formats, organization]

**Does this plan look right?** Should I use a different approach, measure different things, or organize outputs differently?
```

Only proceed after the user approves or modifies the plan.

### 3. Execute
Run pipeline step by step. After every visual step: push to napari or show matplotlib. Present results as preliminary — "Here's a first pass, does this look right?" Reference `references/segmentation.md` for approaches and version-specific code.

### 4. Iterate
Adjust and re-run based on feedback. If not working after 2-3 tries: try a different tool, try interactive annotation, custom training (last resort). Start simple: thresholding before DL, pretrained before custom, defaults before tuning. Don't over-tune — if parameters need drastic per-image adjustment, the approach is wrong.

**When stuck, search [forum.image.sc](https://forum.image.sc).** This is the primary community forum for bioimage analysis — actively monitored by developers of Cellpose, StarDist, napari, QuPath, CellProfiler, and other tools. Search for similar modalities, error messages, or workflows. Suggest users post there for expert advice on genuinely difficult problems.

### 5. Measure & Export
Save organized outputs (labels, QC overlays, CSV tables). Reference `references/measurements.md` for extraction patterns and pitfalls. Connect back to biology — answering the biological question is the endpoint, not raw measurements. Reference `references/quality-control.md` for validation. Check versions before recommending features — see `references/environment.md`.

## Slash Commands

| Command    | Behavior                                                    |
|------------|-------------------------------------------------------------|
| `/bio`     | Start bioimage analysis — assess image, propose pipeline, execute after approval |
| `/bio:qc`  | Run QC checklist on current segmentation results            |

## Reference Files

- `references/environment.md` — version gotchas, GPU detection, napari-mcp setup
- `references/segmentation.md` — approaches, decision tree, version-specific DL code, post-processing
- `references/measurements.md` — what to measure, biological meaning, pitfalls
- `references/preprocessing.md` — when and how to preprocess, recommended order
- `references/quality-control.md` — validation checklist and diagnostic table
- `references/visualization.md` — napari-mcp setup and connection
