"""
Phase 2 (Alt text): Detect and classify markdown image references.

Implements the 3-step classifier from ALT_TEXT_ARCHITECTURE.md:
1. Alt present and not the filename placeholder -> has_alt, skip.
2. Alt empty AND path matches a configured decorative glob -> decorative, skip.
3. Everything else (filename-placeholder alt, or empty alt that doesn't
   match any decorative pattern) -> generate.

Also handles two checks that happen before classification:
- External sources (http/https) -> skip + warn, no fetch.
- Broken references (file doesn't exist) -> a separate issue type
  (AltTextIssue with source='broken_reference'), no LLM call.

Design principles (mirrors agents/candidate_finder.py and
agents/seo_optimizer.py):
- Deterministic: exact line numbers, no LLM guessing
- Transparent: classify before spending a Groq call
- Reuses agents.parsing.parse_headings_from_markdown / is_in_code_block
  rather than reimplementing heading or fence detection
"""

import re
from glob import glob
from pathlib import Path
from typing import List, Set, Tuple

from agents.documents import AltTextCandidate, AltTextIssue, DocumentInput, HeadingNode
from agents.parsing import is_in_code_block

_IMAGE_REF = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
_IMAGE_REF_ANY = re.compile(r'!\[[^\]]*\]\([^)]*\)')
_HTML_TAG = re.compile(r'<[^>]+>')
_TITLE_SUFFIX = re.compile(r'^(\S+)(?:\s+["\'].*["\'])?$')


def find_image_references(lines: List[str]) -> List[Tuple[int, str, str]]:
    """
    Find every markdown image reference in a document, skipping fenced
    code blocks (so documentation-about-markdown isn't treated as a real
    image reference).

    Args:
        lines: Document lines (0-indexed list, as stored on DocumentInput)

    Returns:
        List of (line_number, alt_text, image_path) tuples, 1-indexed
        line numbers, in document order. image_path has any trailing
        `"title"` syntax stripped.
    """
    refs: List[Tuple[int, str, str]] = []
    for line_idx, line in enumerate(lines):
        line_number = line_idx + 1
        if is_in_code_block(lines, line_number):
            continue
        for match in _IMAGE_REF.finditer(line):
            alt_text = match.group(1)
            raw_target = match.group(2).strip()
            title_match = _TITLE_SUFFIX.match(raw_target)
            image_path = title_match.group(1) if title_match else raw_target
            refs.append((line_number, alt_text, image_path))
    return refs


def is_external_image(image_path: str) -> bool:
    """Check if an image path is an external http(s) URL (skip + warn, no fetch)."""
    return image_path.lower().startswith(("http://", "https://"))


def resolve_image_path(doc_relpath: str, image_ref: str, docs_root: Path) -> Path:
    """
    Resolve a markdown image reference to an absolute filesystem path.

    image_ref is treated as relative to the referencing markdown file's
    own directory — the standard markdown/Zensical convention (see the
    docs-engineering-overview.md path fix earlier in this project).

    Args:
        doc_relpath: DocumentInput.file_path (relative to docs_root)
        image_ref: The path as written in the markdown image syntax
        docs_root: Absolute path to the docs/ directory

    Returns:
        Resolved absolute Path (may not exist — callers check that)
    """
    doc_dir = (docs_root / doc_relpath).parent
    return (doc_dir / image_ref).resolve()


def normalize_to_docs_root(abs_path: Path, docs_root: Path) -> str:
    """
    Express an absolute path relative to docs_root, for reporting and
    decorative_paths matching. Falls back to the absolute path string if
    it somehow falls outside docs_root entirely.
    """
    try:
        return str(abs_path.relative_to(docs_root.resolve()))
    except ValueError:
        return str(abs_path)


def resolve_decorative_paths(decorative_patterns: List[str], docs_root: Path) -> Set[str]:
    """
    Expand agents.yaml's decorative_paths globs into a set of docs_root-
    relative paths, via the real filesystem.

    Uses glob.glob(..., recursive=True) — the same mechanism
    agents/scan.py already uses for source patterns — rather than a
    hand-rolled string matcher, so `**` behaves identically to every
    other glob pattern in this project.

    Args:
        decorative_patterns: Glob patterns from agents.yaml's
            alt_text_generator.config.decorative_paths, relative to docs/
        docs_root: Absolute path to the docs/ directory

    Returns:
        Set of docs_root-relative path strings matched by any pattern
    """
    decorative: Set[str] = set()
    for pattern in decorative_patterns:
        pattern_abs = str(docs_root / pattern)
        for matched in glob(pattern_abs, recursive=True):
            decorative.add(normalize_to_docs_root(Path(matched).resolve(), docs_root))
    return decorative


def classify_alt_text(alt_text: str, image_filename: str, is_decorative_path: bool) -> str:
    """
    3-step classifier per ALT_TEXT_ARCHITECTURE.md.

    Args:
        alt_text: Alt text as written in the markdown
        image_filename: The image's basename, including extension
            (e.g. "docs-engineering-overview.png")
        is_decorative_path: Whether the image's path matches a configured
            decorative_paths glob

    Returns:
        "has_alt" | "decorative" | "generate"
    """
    stripped = alt_text.strip()
    if stripped != "" and stripped != image_filename:
        return "has_alt"
    if stripped == "" and is_decorative_path:
        return "decorative"
    return "generate"


def _find_enclosing_heading_index(headings: List[HeadingNode], image_line: int):
    """Index of the nearest heading at or before image_line, or None."""
    enclosing_idx = None
    for i, h in enumerate(headings):
        if h.line_number <= image_line:
            enclosing_idx = i
        else:
            break
    return enclosing_idx


def _trim_outward(lines: List[str], center_idx: int, word_cap: int) -> List[str]:
    """
    Keep lines nearest center_idx (the image's own line), growing outward
    until word_cap is reached — trims from the section's edges first, not
    a blind head/tail cut, so text closest to the image survives longest.
    """
    if not lines:
        return lines

    total_words = sum(len(l.split()) for l in lines)
    if total_words <= word_cap:
        return lines

    kept = {center_idx}
    word_count = len(lines[center_idx].split())
    lo, hi = center_idx - 1, center_idx + 1

    while word_count < word_cap and (lo >= 0 or hi < len(lines)):
        if hi < len(lines):
            w = len(lines[hi].split())
            if word_count + w <= word_cap:
                kept.add(hi)
                word_count += w
            hi += 1
        if lo >= 0:
            w = len(lines[lo].split())
            if word_count + w <= word_cap:
                kept.add(lo)
                word_count += w
            lo -= 1

    return [lines[i] for i in sorted(kept)]


def _strip_noise(lines: List[str]) -> str:
    """Strip fenced code blocks, image references, and raw HTML from
    section text before it's sent as LLM context."""
    cleaned_lines = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _IMAGE_REF_ANY.sub("", line)
        line = _HTML_TAG.sub("", line)
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()
    return re.sub(r'\n{3,}', '\n\n', text)


def extract_section_context(
    doc: DocumentInput,
    headings: List[HeadingNode],
    image_line: int,
    word_cap: int,
) -> Tuple[str, str]:
    """
    Build (heading_breadcrumb, context_text) for an image.

    Section-bounded: everything between the nearest enclosing heading and
    the next heading at the same or higher level (or doc end) — not an
    arbitrary line count. Noise-stripped and capped at word_cap words,
    trimming outward from the section's edges first.

    Args:
        doc: The document the image belongs to
        headings: This document's headings (from parse_headings_from_markdown)
        image_line: 1-indexed line number of the image reference
        word_cap: Max words to keep (agents.yaml's context_word_cap)

    Returns:
        (heading_breadcrumb, context_text) — breadcrumb is "" if the
        image appears before any heading
    """
    enclosing_idx = _find_enclosing_heading_index(headings, image_line)

    if enclosing_idx is None:
        breadcrumb = ""
        section_start = 1
        section_end = len(doc.lines) + 1
    else:
        heading = headings[enclosing_idx]
        breadcrumb = " > ".join(heading.ancestors + [heading.text])
        section_start = heading.line_number + 1
        section_end = len(doc.lines) + 1
        for h in headings[enclosing_idx + 1:]:
            if h.level <= heading.level:
                section_end = h.line_number
                break

    section_lines = doc.lines[section_start - 1:section_end - 1]
    image_local_idx = image_line - section_start

    if 0 <= image_local_idx < len(section_lines):
        windowed_lines = _trim_outward(section_lines, image_local_idx, word_cap)
    else:
        # Defensive: shouldn't happen given how section bounds are computed
        windowed_lines = section_lines

    return breadcrumb, _strip_noise(windowed_lines)


def find_alt_text_candidates(
    doc: DocumentInput,
    headings: List[HeadingNode],
    docs_root: Path,
    decorative_paths: Set[str],
    context_word_cap: int,
) -> Tuple[List[AltTextCandidate], List[AltTextIssue], int]:
    """
    Classify every image reference in one document.

    Args:
        doc: Document to scan
        headings: This document's headings (from parse_headings_from_markdown)
        docs_root: Absolute path to the docs/ directory
        decorative_paths: Resolved decorative path set (resolve_decorative_paths())
        context_word_cap: Max words for extracted context (agents.yaml)

    Returns:
        (candidates, broken_issues, total_images) — candidates are
        "generate"-classified images ready for Phase 3 (Groq verification,
        agents/alt_text_verifier.py); broken_issues are already-finalized
        AltTextIssue objects for broken references (source='broken_reference'),
        no LLM call; total_images is every image reference found (including
        has_alt/decorative/external ones that were classified and skipped),
        for accurate "images scanned" reporting.
    """
    candidates: List[AltTextCandidate] = []
    broken_issues: List[AltTextIssue] = []

    image_refs = find_image_references(doc.lines)
    print(f"[alt-text-phase-2]   {doc.file_path}: {len(image_refs)} image reference(s)")

    for line_number, alt_text, image_ref in image_refs:
        if is_external_image(image_ref):
            print(
                f"[alt-text-phase-2]     Line {line_number}: external image "
                f"({image_ref}) — skipped, no fetch"
            )
            continue

        image_abs_path = resolve_image_path(doc.file_path, image_ref, docs_root)
        if not image_abs_path.is_file():
            breadcrumb, _ = extract_section_context(doc, headings, line_number, context_word_cap)
            broken_issues.append(
                AltTextIssue(
                    file_path=doc.file_path,
                    image_path=image_ref,
                    line_number=line_number,
                    heading_breadcrumb=breadcrumb,
                    suggested_alt="",
                    source="broken_reference",
                )
            )
            print(f"[alt-text-phase-2]     Line {line_number}: BROKEN reference ({image_ref})")
            continue

        image_normalized = normalize_to_docs_root(image_abs_path, docs_root)
        image_filename = Path(image_ref).name
        is_decorative = image_normalized in decorative_paths
        classification = classify_alt_text(alt_text, image_filename, is_decorative)

        if classification in ("has_alt", "decorative"):
            continue

        breadcrumb, context_text = extract_section_context(
            doc, headings, line_number, context_word_cap
        )
        candidates.append(
            AltTextCandidate(
                file_path=doc.file_path,
                image_path=image_normalized,
                image_abs_path=str(image_abs_path),
                line_number=line_number,
                alt_text_raw=alt_text,
                heading_breadcrumb=breadcrumb,
                context_text=context_text,
            )
        )
        print(f"[alt-text-phase-2]     Line {line_number}: needs alt text ({image_normalized})")

    return candidates, broken_issues, len(image_refs)
