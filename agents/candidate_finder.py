"""
Phase 2: Find term candidates using Python regex pre-scan.

This module implements the Python-based pre-scan that:
1. Scans documents for glossary terms (case-insensitive)
2. Detects variants (case, punctuation, abbreviations)
3. Skips multiline code blocks (``` ... ```)
4. Captures exact line numbers and context
5. Returns Candidate objects for Groq validation

Design principles:
- Deterministic: exact line numbers (no LLM guessing)
- Transparent: classify match type for understanding
- Pragmatic: let Groq decide severity (we just flag)
- Fast: single pass through documents
"""

import re
from typing import List, Dict, Set, Tuple

from agents.documents import DocumentInput, Candidate


def is_in_code_block(lines: List[str], line_number: int) -> bool:
    """
    Check if a line is inside a multiline code block (``` ... ```).

    Args:
        lines: Full list of lines from document (0-indexed)
        line_number: 1-indexed line number to check

    Returns:
        True if line is inside a code block, False otherwise
    """
    line_idx = line_number - 1  # Convert to 0-indexed

    # Count backtick fences before this line
    fence_count = 0
    for i in range(line_idx):
        line = lines[i]
        # Count triple backticks (opening/closing fence)
        fence_count += line.count("```")

    # If even number of fences seen, we're outside a block (or at opening)
    # If odd number of fences, we're inside a block
    return fence_count % 2 == 1


def normalize_term(term: str) -> str:
    """
    Normalize a term for case-insensitive comparison.

    Args:
        term: Raw term string

    Returns:
        Lowercase normalized version
    """
    return term.lower()


def extract_context(text: str, match_start: int, match_end: int, window: int = 40) -> str:
    """
    Extract context snippet around a match.

    Args:
        text: Full text to extract from
        match_start: Start index of match
        match_end: End index of match
        window: Characters before/after to include

    Returns:
        Context snippet with ellipsis if truncated
    """
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)

    before = "..." if start > 0 else ""
    after = "..." if end < len(text) else ""

    snippet = text[start:end].replace("\n", " ").strip()
    return f"{before}{snippet}{after}"


def classify_match_type(canonical: str, found: str) -> str:
    """
    Classify the type of mismatch between canonical and found variant.

    Args:
        canonical: Canonical term from glossary
        found: Variant found in document

    Returns:
        Match type: "case_mismatch", "punctuation_variant", "abbreviation", "unknown"
    """
    can_lower = canonical.lower()
    found_lower = found.lower()

    # Case only differs
    if canonical != found and can_lower == found_lower:
        return "case_mismatch"

    # Remove punctuation and compare
    can_clean = re.sub(r'[-\s./]', '', can_lower)
    found_clean = re.sub(r'[-\s./]', '', found_lower)

    if can_clean == found_clean:
        return "punctuation_variant"

    # Check if found is abbreviation of canonical
    # (e.g., "api" of "API", "pr" of "pull request")
    if found_lower in can_lower or found_lower == can_clean:
        return "abbreviation"

    # Doesn't fit known patterns
    return "unknown"


def find_term_in_line(
    line: str, 
    canonical: str,
    line_number: int,
    file_path: str
) -> List[Candidate]:
    """
    Find all instances of a term in a single line.

    Args:
        line: Full text of line
        canonical: Canonical term from glossary
        line_number: 1-indexed line number
        file_path: Relative path to file

    Returns:
        List of Candidate objects for matches found
    """
    candidates = []

    # Case-insensitive search handling multi-word terms and punctuation variants
    # Strategy: search for the term and common punctuation variants
    
    # Generate search patterns: canonical + common variants
    # e.g., "REST API" → search for "REST API", "REST-API", "rest api", etc.
    variants_to_search = [canonical]
    
    # Add hyphenated version if spaces exist
    if ' ' in canonical:
        variants_to_search.append(canonical.replace(' ', '-'))
        variants_to_search.append(canonical.replace(' ', ''))  # No space/hyphen
    
    try:
        for variant_pattern in variants_to_search:
            escaped_term = re.escape(variant_pattern)
            pattern = r'\b' + escaped_term + r'\b'
            
            for match in re.finditer(pattern, line, re.IGNORECASE):
                found_text = match.group()
                
                # Skip if it's an exact match to canonical
                if found_text == canonical:
                    continue
                
                # Skip if we already found this variant (avoid duplicates)
                if any(c.found_variant == found_text for c in candidates):
                    continue
                
                # Create candidate
                match_type = classify_match_type(canonical, found_text)
                context = extract_context(line, match.start(), match.end(), window=40)
                
                candidate = Candidate(
                    file_path=file_path,
                    line_number=line_number,
                    canonical_term=canonical,
                    found_variant=found_text,
                    context_snippet=context,
                    raw_text=line,
                    match_type=match_type,
                )
                candidates.append(candidate)
    except re.error as e:
        # If regex fails, skip this term (e.g., malformed escape)
        print(f"[candidate] Regex error for term '{canonical}': {e}")

    return candidates


def find_term_candidates(
    documents: List[DocumentInput],
    glossary: Dict[str, str],
) -> Dict[str, List[Candidate]]:
    """
    Scan documents for glossary term variants using Python regex.

    This function:
    1. Iterates through each document and line
    2. Skips lines inside multiline code blocks (``` ... ```)
    3. Searches for each glossary term (case-insensitive)
    4. Flags variants that don't match canonical exactly
    5. Classifies match types (case, punctuation, abbreviation)
    6. Returns candidates indexed by file path

    Args:
        documents: List of DocumentInput (from scan_docs)
        glossary: Dictionary of canonical terms

    Returns:
        Dictionary mapping file_path → List[Candidate]
        Example: {
            "docs/index.md": [Candidate(...), Candidate(...)],
            "docs/guides/setup.md": [Candidate(...)],
        }
    """
    print(f"[phase-2] Scanning {len(documents)} document(s) for {len(glossary)} term(s)")

    candidates_by_file: Dict[str, List[Candidate]] = {}

    for doc in documents:
        print(f"[phase-2]   Scanning {doc.file_path}...")
        candidates_by_file[doc.file_path] = []

        # Process each line
        for line_num, line_text in enumerate(doc.lines, start=1):
            # Check if line is in a code block
            if is_in_code_block(doc.lines, line_num):
                continue

            # Search for each glossary term in this line
            for canonical_term in glossary.keys():
                candidates = find_term_in_line(
                    line_text,
                    canonical_term,
                    line_num,
                    doc.file_path,
                )
                candidates_by_file[doc.file_path].extend(candidates)

        candidate_count = len(candidates_by_file[doc.file_path])
        print(f"[phase-2]     Found {candidate_count} candidate(s)")

    total_candidates = sum(len(v) for v in candidates_by_file.values())
    print(f"[phase-2] ✓ Total candidates: {total_candidates}")

    return candidates_by_file


def summarize_candidates(candidates_by_file: Dict[str, List[Candidate]]) -> str:
    """
    Generate a human-readable summary of candidates by match type.

    Args:
        candidates_by_file: Candidates indexed by file path

    Returns:
        Formatted summary string
    """
    # Count by type
    type_counts: Dict[str, int] = {}
    total = 0

    for candidates in candidates_by_file.values():
        for candidate in candidates:
            total += 1
            match_type = candidate.match_type
            type_counts[match_type] = type_counts.get(match_type, 0) + 1

    # Build summary
    summary_lines = [f"Candidates by type:"]
    for match_type in sorted(type_counts.keys()):
        count = type_counts[match_type]
        summary_lines.append(f"  - {match_type}: {count}")

    summary_lines.append(f"Total: {total}")
    return "\n".join(summary_lines)
