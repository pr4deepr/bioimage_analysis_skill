#!/usr/bin/env python3
"""Validate bioimage analysis skill: integrity checks and conciseness guards.

Usage:
    python3 validate-skill.py          # Integrity only (for pre-commit hook). Exit 2 if broken.
    python3 validate-skill.py --warn   # All checks, always exit 0. JSON output for Claude context.
    python3 validate-skill.py --full   # All checks. Exit 2 if integrity fails. Warnings to stderr.
"""
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# Resolve project root — works whether called from hooks dir or project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT = SCRIPT_DIR.parent.parent  # .claude/hooks/ -> .claude/ -> project root
if not (PROJECT / "SKILL.md").exists():
    PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))

SKILL_FILES = {
    "SKILL.md": 100,
    "references/bioimage_utils.py": 880,
    "references/cookbook-pipeline.md": 570,
    "references/segmentation.md": 340,
    "references/environment.md": 145,
    "references/measurements.md": 90,
    "references/visualization.md": 85,
    "references/quality-control.md": 50,
    "references/preprocessing.md": 40,
}
TOTAL_BUDGET = 2200


def check_integrity():
    """Return list of integrity errors (empty = clean)."""
    errors = []

    # 1. Dead file references: scan all .md and .py for references/X
    ref_pattern = re.compile(r'references/[\w_-]+\.(?:py|md)')
    all_files = list((PROJECT / "references").glob("*")) + [PROJECT / "SKILL.md", PROJECT / "README.md"]
    for fpath in all_files:
        if fpath.suffix not in (".md", ".py") or not fpath.exists():
            continue
        text = fpath.read_text()
        for match in ref_pattern.finditer(text):
            ref = match.group()
            if not (PROJECT / ref).exists():
                errors.append(f"Dead reference: {fpath.name} -> {ref}")

    # 2. Dead function references in SKILL.md
    skill_text = (PROJECT / "SKILL.md").read_text()
    func_refs = set(re.findall(r'`(\w+)\(\)`', skill_text))
    class_refs = set(re.findall(r'`(ResultsManager)`', skill_text))
    all_refs = func_refs | class_refs

    utils_path = PROJECT / "references" / "bioimage_utils.py"
    if utils_path.exists():
        utils_text = utils_path.read_text()
        defined = set(re.findall(r'^(?:def|class)\s+(\w+)', utils_text, re.MULTILINE))
        for name in all_refs:
            if name not in defined:
                errors.append(f"SKILL.md references `{name}` but it's not defined in bioimage_utils.py")

    # 3. Orphaned files: every file in references/ should be in SKILL.md
    for fpath in (PROJECT / "references").iterdir():
        if fpath.name.startswith("__") or fpath.is_dir():
            continue
        # Match either "references/filename" or bare "filename" in the reference section
        if f"references/{fpath.name}" not in skill_text and fpath.name not in skill_text:
            errors.append(f"Orphaned file: references/{fpath.name} not listed in SKILL.md")

    # 4. README consistency: files listed in README's tree should exist
    readme_path = PROJECT / "README.md"
    if readme_path.exists():
        readme_text = readme_path.read_text()
        # Match lines like "├── bioimage_utils.py" or "└── visualization.md"
        tree_files = re.findall(r'[├└]── ([\w_-]+\.(?:py|md))', readme_text)
        for fname in tree_files:
            candidate = PROJECT / "references" / fname
            if not candidate.exists() and not (PROJECT / fname).exists():
                errors.append(f"README.md lists {fname} but file doesn't exist")

    return errors


def check_conciseness():
    """Return list of conciseness warnings (never errors)."""
    warnings = []

    # 1. Per-file line budget
    total = 0
    for rel_path, budget in SKILL_FILES.items():
        fpath = PROJECT / rel_path
        if not fpath.exists():
            continue
        lines = len(fpath.read_text().splitlines())
        total += lines
        if lines > budget:
            warnings.append(
                f"Over budget: {rel_path} has {lines} lines (budget: {budget})")

    # 2. Total budget
    if total > TOTAL_BUDGET:
        warnings.append(
            f"Total skill size: {total} lines (budget: {TOTAL_BUDGET})")

    # 3. Duplication detection: find 6+ consecutive lines shared between files
    file_lines = {}
    for rel_path in SKILL_FILES:
        fpath = PROJECT / rel_path
        if fpath.exists():
            file_lines[rel_path] = fpath.read_text().splitlines()

    window = 6
    seen_blocks = {}  # hash -> (file, line_num)
    for rel_path, lines in file_lines.items():
        for i in range(len(lines) - window + 1):
            block = tuple(line.strip() for line in lines[i:i + window])
            if all(b == "" for b in block):
                continue
            h = hash(block)
            if h in seen_blocks and seen_blocks[h][0] != rel_path:
                other_file, other_line = seen_blocks[h]
                dup_msg = (f"Duplicated code ({window}+ lines): "
                           f"{rel_path}:{i+1} and {other_file}:{other_line+1}")
                if dup_msg not in warnings:
                    warnings.append(dup_msg)
            else:
                seen_blocks[h] = (rel_path, i)

    # 4. Prose-to-code ratio for .md files (skip cookbooks — they're meant to be code-heavy)
    for rel_path in SKILL_FILES:
        if not rel_path.endswith(".md") or "cookbook" in rel_path:
            continue
        fpath = PROJECT / rel_path
        if not fpath.exists():
            continue
        text = fpath.read_text()
        lines = text.splitlines()
        in_code = False
        code_lines = 0
        total_lines = len(lines)
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                code_lines += 1
        if total_lines > 20 and code_lines / total_lines > 0.70:
            pct = code_lines / total_lines * 100
            warnings.append(
                f"High code ratio: {rel_path} is {pct:.0f}% code "
                f"({code_lines}/{total_lines} lines) — consider moving to .py")

    return warnings


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    integrity_errors = check_integrity()

    if mode == "--warn":
        conciseness_warnings = check_conciseness()
        all_issues = integrity_errors + conciseness_warnings
        if all_issues:
            context = "Skill validation: " + "; ".join(all_issues)
            print(json.dumps({
                "hookSpecificOutput": {"additionalContext": context}
            }))
        sys.exit(0)

    elif mode == "--full":
        conciseness_warnings = check_conciseness()
        for e in integrity_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        for w in conciseness_warnings:
            print(f"WARNING: {w}", file=sys.stderr)
        if not integrity_errors and not conciseness_warnings:
            print("All checks passed.", file=sys.stderr)
        sys.exit(2 if integrity_errors else 0)

    else:
        # Default: integrity only, for pre-commit gate
        for e in integrity_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2 if integrity_errors else 0)


if __name__ == "__main__":
    main()
