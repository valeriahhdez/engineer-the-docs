"""
Document scanning with two-pass glob and marker filtering.

This module implements the file discovery stage of the consistency checker:
1. Two-pass glob: positive patterns → negative patterns
2. Marker detection: skip files marked with # --no-{agent-name}
3. Return DocumentInput objects with content and line-indexed representation

Design principles:
- Opt-in: only files in sources list are checked
- Fail-fast: clear error messages for missing directories
- Deterministic: same input always produces same output
"""

import os
import sys
from pathlib import Path
from glob import glob
from typing import List

from agents.documents import DocumentInput


def scan_docs(
    docs_root: str,
    sources: List[str],
    exclude_markers: List[str],
) -> List[DocumentInput]:
    """
    Scan documentation files with two-pass glob and marker filtering.

    This function:
    1. Walks the docs_root directory using glob patterns from sources
    2. Applies two-pass logic: positive patterns first, then filter negations
    3. Respects file-level markers (e.g., # --no-consistency-check at file top)
    4. Returns DocumentInput objects with content and lines

    Two-pass glob logic:
    - Pass 1: Collect files matching positive patterns (e.g., "docs/**/*.md")
    - Pass 2: Remove files matching negative patterns (e.g., "!docs/generated/**/*.md")
    - Order matters: positive patterns evaluated first

    Marker filtering:
    - Only file-level markers are respected (must be first line of file)
    - Example: "# --no-consistency-check" at line 1 skips entire file
    - No section-level exclusions (MVP scope)

    Args:
        docs_root: Root documentation directory (must exist)
        sources: List of glob patterns from agents.yaml
                 Positive patterns: "docs/**/*.md"
                 Negative patterns: "!docs/generated/**/*.md"
        exclude_markers: List of markers to check for (e.g., ["# --no-consistency-check"])

    Returns:
        List of DocumentInput objects (filepath, content, lines)

    Raises:
        FileNotFoundError: If docs_root doesn't exist
        ValueError: If no markdown files found (suggests configuration error)

    Example:
        >>> docs = scan_docs(
        ...     "docs",
        ...     sources=["docs/**/*.md", "!docs/generated/**/*.md"],
        ...     exclude_markers=["# --no-consistency-check"]
        ... )
        >>> print(f"Found {len(docs)} files")
    """
    # Validate docs_root exists
    docs_path = Path(docs_root)
    if not docs_path.exists():
        raise FileNotFoundError(
            f"Documentation root not found: {docs_root}\n"
            f"Expected at: {os.path.abspath(docs_root)}"
        )

    if not docs_path.is_dir():
        raise ValueError(
            f"Documentation root must be a directory: {docs_root}"
        )

    print(f"[scan] Scanning {docs_root}")
    print(f"[scan] Patterns: {len(sources)} source(s)")
    print(f"[scan] Markers: {exclude_markers}")

    # ========================================================================
    # Pass 1: Collect files matching positive patterns
    # ========================================================================
    collected_files = set()

    for pattern in sources:
        # Skip negative patterns for Pass 1
        if pattern.startswith("!"):
            continue

        # Expand glob pattern relative to docs_root
        pattern_abs = str(docs_path / pattern)
        matched = glob(pattern_abs, recursive=True)

        if matched:
            print(f"[scan]   + {pattern}: {len(matched)} file(s)")
            for filepath in matched:
                collected_files.add(filepath)
        else:
            print(f"[scan]   + {pattern}: 0 files (no matches)")

    # ========================================================================
    # Pass 2: Filter out files matching negative patterns
    # ========================================================================
    excluded_files = set()

    for pattern in sources:
        # Only process negative patterns
        if not pattern.startswith("!"):
            continue

        # Remove "!" prefix and expand glob
        neg_pattern = pattern[1:]
        pattern_abs = str(docs_path / neg_pattern)
        matched = glob(pattern_abs, recursive=True)

        if matched:
            print(f"[scan]   - {neg_pattern}: {len(matched)} file(s) excluded")
            for filepath in matched:
                excluded_files.add(filepath)

    # Compute final file list
    final_files = sorted(list(collected_files - excluded_files))

    if not final_files:
        raise ValueError(
            f"No markdown files found in {docs_root} matching patterns: {sources}"
        )

    print(f"[scan] Final: {len(final_files)} file(s) after filtering")

    # ========================================================================
    # Process files: read content, check markers, build DocumentInput
    # ========================================================================
    documents = []

    for filepath in final_files:
        # Read file content
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"[scan] ✗ Failed to read {filepath}: {e}", file=sys.stderr)
            continue

        # Check for file-level markers (first line only)
        lines = content.split("\n")
        first_line = lines[0] if lines else ""

        skip_file = False
        for marker in exclude_markers:
            if first_line.strip().startswith(marker.strip()):
                skip_file = True
                rel_path = os.path.relpath(filepath, docs_root)
                print(f"[scan]   ✗ {rel_path}: marker '{marker}' found, skipping")
                break

        if skip_file:
            continue

        # Build DocumentInput
        rel_path = os.path.relpath(filepath, docs_root)
        doc = DocumentInput(
            file_path=rel_path,
            content=content,
            lines=lines,
        )
        documents.append(doc)
        print(f"[scan]   ✓ {rel_path}")

    print(f"[scan] ✓ Scanned {len(documents)} file(s)")

    return documents


def validate_docs_path(docs_root: str) -> None:
    """
    Validate that docs_root exists and is accessible.

    Args:
        docs_root: Path to documentation root

    Raises:
        FileNotFoundError: If path doesn't exist
        ValueError: If path is not a directory
    """
    docs_path = Path(docs_root)
    if not docs_path.exists():
        raise FileNotFoundError(
            f"Documentation root not found: {docs_root}\n"
            f"Expected at: {os.path.abspath(docs_root)}"
        )

    if not docs_path.is_dir():
        raise ValueError(
            f"Documentation root must be a directory: {docs_root}"
        )
