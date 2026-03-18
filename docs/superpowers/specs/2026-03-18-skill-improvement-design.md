# Bioimage Analysis Skill Improvement — Design Spec

**Date:** 2026-03-18
**Status:** Approved
**Scope:** Add actionable code patterns, lean core, adaptive user model, robust napari, subagent, slash commands

---

## 1. Problem Statement

The bioimage analysis skill has strong conceptual references but lacks runnable code patterns Claude can directly execute. The core SKILL.md mixes workflow, rules, and examples. The user interaction model is too restrictive (one question max) and assumes expert users. napari launch is unreliable — claims "connected" without verification.

## 2. Design Principles

1. **Visual feedback loop is core.** Every analysis step produces visual output → user evaluates → iterate. napari is the primary feedback mechanism, not just a display tool.
2. **Biology-first communication.** Report results in scientific terms matching the user's language. "132 Hu+ neurons, mean soma area 245 um2" not "132 objects, mean area 245."
3. **Adaptive to user level.** Assume users understand microscopy/biology but may not know Python. Gauge Python comfort from context and adapt code presentation.
4. **Runnable code patterns.** Every technique has a complete, copy-paste code block with imports and clear variable names.
5. **Lean core, rich references.** SKILL.md is workflow and rules only (~150 lines max). All code lives in cookbooks and references.

## 3. Core SKILL.md Restructure

### 3.1 Four Rules (replaces current three)

1. **Look first, then propose.** Assess the image and context before running anything.
2. **Close the feedback loop.** Every step that produces output → show it visually (napari preferred, matplotlib always available) → assess it yourself → ask user to evaluate before proceeding. Never say "check the output."
3. **Ask focused questions, then execute.** Up to 2-3 questions to understand the biological question and data. Infer everything else from context. Never ask technical implementation questions.
4. **Show results in the best available viewer.** napari for interactive feedback, matplotlib for inline results. Both are first-class.

### 3.2 User Interaction Model

**Gauge user from context clues:**
- File paths, terminology, how they describe their problem
- "Segment the nuclei using StarDist" → minimal questions, they know what they want
- "I have microscopy images and need to analyze them" → more guidance needed

**Question budget: up to 3 focused questions, then execute.**

Prioritized question order (ask only what can't be inferred):
1. **What are you trying to learn?** (biological question — drives everything)
2. **What's in the image?** (staining, channels — only if not obvious from filename/metadata)
3. **How will you use the results?** (counts for a paper? sorting cells? — shapes output format)

**Never ask:**
- Technical implementation questions (which threshold method, what parameters)
- Environment questions (what Python version, what OS) — detect these
- "Would you like me to..." — just do it and show results

**Adapt code presentation:**
- User describes in biology terms → run code directly, explain results in biology AND scientific terms
- User writes code or mentions packages → show code, explain technical choices
- When in doubt → run directly, show results, offer to show code if they want

### 3.3 Viewer Philosophy

- napari is the preferred viewer when available — visual feedback loop is core to image analysis
- matplotlib is a first-class alternative: equal code pattern quality and completeness, used whenever napari is unavailable. "First-class" means implementation parity, not equal user-facing priority — prefer napari when connected.
- Offer napari setup once if available but not connected; don't push repeatedly
- Never claim "connected" without proof (see Section 6)

### 3.4 Content Removed from SKILL.md

- All code examples (move to cookbooks)
- Version gotchas (stay in environment.md)
- Detailed key behaviors section (trimmed, integrated into rules)

## 4. New Cookbook Files

Four new files in `references/`. Each contains complete, runnable code patterns organized by task.

### 4.1 cookbook-io.md — Reading and Writing Images

**Patterns:**
- Reading TIFF with tifffile (simplest, always available)
- Reading TIFF with skimage.io
- Reading CZI/LIF/ND2/OME-TIFF with BioIO
- Extracting metadata (pixel size, channels, dimensions)
- Saving label masks as TIFF
- Saving overlays as PNG
- Saving measurements as CSV

**Each pattern:** complete imports, clear variable names, inline comments explaining what's happening.

### 4.2 cookbook-segmentation.md — Runnable Segmentation Code

**Patterns:**
- Otsu thresholding + connected components (simplest)
- Adaptive thresholding for uneven illumination
- Threshold + watershed for touching objects
- Cellpose with pretrained models (cyto2, cyto3, nuclei)
- Cellpose with custom model
- StarDist with pretrained models (2D_versatile_fluo)
- StarDist with custom model
- Post-processing: size filtering, edge removal, hole filling, boundary smoothing

**Each pattern:** complete code block, what it's good for, expected input/output, key parameters to adjust.

**Version annotations:** Each DL code pattern includes a version note at the top specifying which API version it targets (e.g., `# Cellpose >= 3.0` or `# StarDist 0.8.x`). Where APIs differ significantly across versions (Cellpose 2 vs 3 vs 4), provide separate code blocks per version family. Claude checks the version from STATE.md before selecting which block to use.

### 4.3 cookbook-visualization.md — Showing Results

**Dual patterns — every visual has BOTH napari and matplotlib versions:**
- Show raw image
- Show segmentation overlay (labels on raw)
- Show side-by-side comparison (before/after, two channels)
- Show measurement distribution (histogram of areas, intensities)
- Show QC overlay (outlines on raw, colored by a measurement)
- Screenshot and report (napari: take screenshot via MCP; matplotlib: save figure)

**napari launch and verification (robust) — check-before-first-use pattern:**
- Launch napari-mcp in background with stderr capture to temp file
- Wait 5 seconds, then check if process is still alive and read stderr for crash errors
- Attempt MCP connection once (`session_information()`) — clear pass/fail
- Only update STATE.md `viewer_connected: true` after successful MCP response
- If launch fails: show actual error message to user, proceed with matplotlib
- If napari not ready before first visual output is needed: show matplotlib, retry napari connection before next visual step

### 4.4 cookbook-measurements.md — Extraction and Export

**Patterns:**
- scikit-image regionprops: area, eccentricity, solidity, perimeter
- Intensity measurements: mean, max, integrated, SD per channel
- Background-subtracted intensity (annular region method)
- Nearest-neighbor distance and local density
- Export to CSV with proper column names and units
- Summary statistics per condition
- Basic plots: box plot per condition, histogram, scatter

## 5. Updated Existing References

### 5.1 segmentation.md
- Stays as conceptual guide (when to use what approach, decision flow)
- Remove any code that duplicates cookbook-segmentation.md
- Add cross-references to cookbook patterns

### 5.2 measurements.md
- Keep biology interpretation tables and pitfalls (these are excellent)
- Add inline code snippet for each measurement type (short, 3-5 lines)
- Add cross-reference to cookbook-measurements.md for full patterns

**Inline snippet definition:** Imports excluded. Assumes variables (`image`, `labels`, `props`) are already defined. Shows only the core function call and immediate result. Example:
```python
# Area in calibrated units
areas_um2 = [p.area * (pixel_size ** 2) for p in props]
```
Full patterns with imports, setup, and export live in the cookbook files.

**Cross-reference format:** Use a "See:" line pointing to the cookbook file and section:
```
> See: cookbook-measurements.md § Morphology measurements
```

### 5.3 preprocessing.md
- Keep technique descriptions
- Add inline code snippet for each technique (illumination correction, background subtraction, noise reduction, normalization, channel extraction)

### 5.4 quality-control.md
- Keep the 6-point checklist
- Add code for each check: overlay generation, count comparison, histogram plotting, outlier inspection
- Both napari and matplotlib versions where visual

### 5.5 environment.md
- Minor cleanup only
- napari launch patterns move to cookbook-visualization.md (canonical location)
- Keep env scanning logic, version gotchas

### 5.6 state-templates.md
- Add `step_status: in_progress` pattern: update STATE.md with `step_status: in_progress` before starting each analysis step, then `completed` after. On re-activation, if STATE.md shows `in_progress`, Claude knows the step was interrupted and can offer to retry.
- Add STATE.md validation rule: on read, if STATE.md is malformed (missing required sections, unparseable), treat as missing and re-scan. Don't crash on corrupted state.

## 6. Robust napari Launch & Verification

**Problem:** Current pattern uses `subprocess.Popen` with `start ""` on Windows, fires and forgets, no verification. STATE.md gets updated to connected based on hope.

**Solution — check-before-first-use pattern (in cookbook-visualization.md):**

Claude Code executes sequentially — active polling loops are not practical. Instead:

1. **Launch with output capture:** Run napari-mcp in background, capture stderr to a temp file.
2. **Wait 5 seconds, then verify:** Check if the process is still alive. If dead, read stderr and report the actual error to the user.
3. **Attempt MCP connection once:** Call `session_information()` or equivalent. This is the proof of connection.
4. **Never claim connected without proof:** Only update STATE.md `viewer_connected: true` after a successful MCP response.
5. **Show actual errors:** If launch fails, show the error message, not just "falling back to matplotlib."
6. **Retry at next visual step:** If napari wasn't ready before the first visual output, use matplotlib for that step. Retry the MCP connection before the next visual step. This gives napari more startup time without blocking work.
7. **No queuing mechanism needed:** At each visual step, check STATE.md for `viewer_connected`, then execute the napari or matplotlib code path directly.

## 7. Subagent Architecture

**One subagent: Environment Scanner**

- Spawned in background on first activation (no STATE.md found)
- Scans conda/mamba environments, checks packages, finds napari
- Writes results to STATE.md
- Main conversation continues immediately — greets user, asks questions

**Implementation mechanism:** Use Claude Code's `Agent` tool with `run_in_background: true`. The agent runs the env scanning logic from `references/environment.md` (list envs, pick candidates, filesystem check, version check on winners). It writes results directly to `.bioimage-analysis/STATE.md`. The main conversation is notified when the agent completes — no polling needed.

**Communication:** The agent writes to STATE.md as its output channel. The main conversation reads STATE.md when it needs env info (before executing analysis code). If the agent hasn't finished yet and env info is needed, the main conversation runs a quick inline env check for just the immediately-needed tool.

**Flow:**
```
On activation (no STATE.md):
1. Spawn env scanner agent in background (Agent tool, run_in_background: true)
2. Greet user, start asking questions
3. Agent writes STATE.md when done — main conversation is notified
4. By the time questions are answered, env is usually known
5. If env needed before agent finishes: quick inline check for the specific tool needed
```

**Why only one subagent:**
- Analysis is inherently sequential and needs visual feedback loop at every step
- Env scanning is the one clear parallelization win (~10-15 sec, independent of conversation)
- More subagents (batch processor, QC verifier) can be added in future rounds

## 8. Slash Commands

Defined in SKILL.md frontmatter using the `commands:` key. Keyword triggers remain — commands are shortcuts.

**Frontmatter format:**
```yaml
---
name: bioimage-analysis
description: >
  Guide users through image segmentation and measurement...
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
```

| Command | Intent | Behavior |
|---|---|---|
| `/bio` | Full workflow | Same as keyword trigger — assess, plan, execute |
| `/bio:plan` | Plan only | Assess image + write ANALYSIS.md, don't execute |
| `/bio:run` | Execute plan | Read existing ANALYSIS.md, execute pipeline |
| `/bio:qc` | Quality control | Run QC checklist on current segmentation |
| `/bio:measure` | Measure | Extract measurements from existing labels |
| `/bio:status` | Check state | Show STATE.md — env, viewer, progress |

**Design principles:**
- Commands map to workflow phases, not tools
- All commands check STATE.md first
- `/bio` is the catch-all; specific commands are shortcuts
- No command for env scanning (automatic) or napari setup (contextual)
- No per-tool commands (no `/bio:cellpose`) — skill picks the tool

## 9. File Structure After Changes

```
bioimage-analysis/
├── SKILL.md                              # Core skill (~150 lines max)
└── references/
    ├── environment.md                    # Env scanning, versions (minor cleanup)
    ├── state-templates.md                # STATE.md / ANALYSIS.md formats (unchanged)
    ├── segmentation.md                   # Conceptual guide (code moved out)
    ├── measurements.md                   # + inline code snippets
    ├── preprocessing.md                  # + inline code snippets
    ├── quality-control.md                # + code for each QC check
    ├── cookbook-io.md                     # NEW: image read/write patterns
    ├── cookbook-segmentation.md           # NEW: runnable segmentation code
    ├── cookbook-visualization.md          # NEW: napari + matplotlib patterns
    └── cookbook-measurements.md           # NEW: extraction, export, stats
```

## 10. Edge Cases

- **STATE.md corruption:** If STATE.md is malformed on read, treat as missing and re-scan. Don't crash.
- **Interrupted pipeline:** STATE.md uses `step_status: in_progress` before each step, `completed` after. On re-activation with `in_progress`, offer to retry the interrupted step.
- **pip install fails:** If `pip install napari-mcp` fails (corporate/HPC network restrictions), suggest manual installation or conda install, then proceed with matplotlib. Don't stall.
- **napari-mcp / napari version mismatch:** Check napari version from STATE.md before installing napari-mcp. If napari < 0.5.0, warn user about potential incompatibility.

## 11. Out of Scope (Future Rounds)

- Batch processing (multiple images)
- 3D / Z-stack analysis
- Timelapse / object tracking
- Colocalization analysis
- Additional subagents (QC verifier, batch processor)
- FIJI MCP integration
- Example analyses with test data
