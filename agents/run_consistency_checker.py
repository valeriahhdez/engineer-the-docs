"""
Entry point for the consistency checker agent.

ARCHITECTURE:
  Load config → Scan docs → Find candidates → Verify with Groq → Format output

DISCOVERY and EXECUTION RULES:
1. Markers: Agent-specific opt-outs (file-level only)
   - Markers: # --no-consistency-check at file top skips entire file
   - Other agents use: # --no-alt-text, # --no-seo, etc.
   - One marker = one file skipped; no section-level exclusions (MVP)

2. Globbing: sources use recursive glob syntax with negations
   - Positive patterns: "docs/**/*.md"
   - Negative patterns: "!docs/generated/**/*.md"
   - Two-pass logic: collect positive matches, then filter negations
   - Explicit file paths override glob rules

3. Default behavior: OPT-IN (explicit config required)
   - Only files listed in agents.yaml are checked
   - Unlisted files never checked (cost control, intent clarity)
   - Markers only respected for files already in sources

4. Config consolidation: agents.yaml is single source of truth
   - discovery rules (sources, markers)
   - agent assignment (which agents run)
   - agent config (glossary_path, thresholds, etc.)
   - Reference data (glossary.yaml, etc.) in separate files

5. API outputs: Groq structured outputs (JSON mode)
   - Agent returns Pydantic-validated JSON
   - Step 4 receives clean, typed data
   - No parsing needed; no hallucination in output shape

6. Artifact formats:
   - JSON: Machine-readable, GitHub artifact upload
   - Markdown: Human-readable summary for review
   - Future: GitHub PR annotations (inline comments)

PHASE ROADMAP:
   Phase 1 (COMPLETE): scan_docs() - glob patterns + marker filtering ✓
   Phase 2 (COMPLETE): find_term_candidates() - Python regex pre-scan ✓
   Phase 3 (COMPLETE): verify_with_groq() - LLM semantic validation ✓
   Phase 4 (COMPLETE): format_output() - build ConsistencyReport ✓
   Step 5 (COMPLETE): agents.output.format_report() - render JSON + Markdown ✓
"""

import os
import sys
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv
load_dotenv()  # Load .env file

# Add parent directory to path so we can import agents module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import config loaders, document scanning, candidate finding, Groq verification, and data models
from agents.config import load_config, load_glossary
from agents.scan import scan_docs
from agents.candidate_finder import find_term_candidates
from agents.groq_verifier import verify_with_groq
from agents.output import format_report
from agents.documents import DocumentInput, ConsistencyReport, ConsistencyIssue, Candidate



# ============================================================================
# Format Output
# ============================================================================


def format_output(
    issues: List[ConsistencyIssue],
    glossary_size: int,
    files_count: int,
) -> ConsistencyReport:
    """
    Format consistency check results into structured report.

    Args:
        issues: List of consistency issues found
        glossary_size: Count of canonical terms
        files_count: Count of files scanned

    Returns:
        ConsistencyReport with status, summary, and detailed findings
    """
    status = "pass" if not issues else "fail"
    summary = (
        f"✓ Consistency check passed ({glossary_size} terms, {files_count} files)"
        if status == "pass"
        else f"✗ Consistency check failed: {len(issues)} issue(s) found"
    )

    return ConsistencyReport(
        status=status,
        issues_found=len(issues),
        issues=issues,
        glossary_terms_checked=glossary_size,
        files_scanned=files_count,
        summary=summary,
    )


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """
    Orchestrate the consistency checker workflow.

    Workflow:
    1. Load agents.yaml (discover config and glossary path)
    2. Load glossary.yaml (canonical terminology)
    3. Scan documentation files (Phase 1: scan_docs)
    4. Find term candidates (Phase 2: find_term_candidates) - MOCK
    5. Verify with Groq (Phase 3: verify_with_groq) - MOCK
    6. Format and return report

    Exit behavior:
    - 0 if consistency check passes
    - 1 if issues found or error occurs
    """
    # Determine config paths (relative to repo root)
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "agents.yaml"
    docs_root = repo_root / "docs"

    print(f"[consistency-checker] Starting consistency check")
    print(f"[consistency-checker] Repo root: {repo_root}")
    print()

    # ========================================================================
    # Step 1: Load configuration (agents.yaml)
    # ========================================================================
    print("[config] Loading agents.yaml...")
    try:
        config = load_config(str(config_path))
        print(f"[config] ✓ Loaded agents.yaml")
    except FileNotFoundError as e:
        print(f"[config] ✗ {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[config] ✗ Validation error: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract configuration for consistency checker
    cc_config = config["agents"]["consistency_checker"]
    glossary_path_rel = cc_config["config"]["glossary_path"]
    sources = cc_config.get("sources", [])
    exclude_markers = cc_config["config"].get("exclude_markers", [])

    glossary_path = repo_root / glossary_path_rel

    # ========================================================================
    # Step 2: Load glossary (reference/glossary.yaml)
    # ========================================================================
    print(f"[config] Loading glossary from {glossary_path_rel}...")
    try:
        glossary = load_glossary(str(glossary_path))
        print(f"[config] ✓ Loaded {len(glossary)} canonical terms")
    except FileNotFoundError as e:
        print(f"[config] ✗ {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[config] ✗ Validation error: {e}", file=sys.stderr)
        sys.exit(1)

    print()

    # ========================================================================
    # Step 3: Scan documentation (Phase 1 - COMPLETE)
    # ========================================================================
    print("[phase-1] Scanning documentation with glob patterns and markers...")
    try:
        documents = scan_docs(
            str(docs_root),
            sources=sources,
            exclude_markers=exclude_markers,
        )
        print(f"[phase-1] ✓ Scanned {len(documents)} file(s)")
    except FileNotFoundError as e:
        print(f"[phase-1] ✗ {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"[phase-1] ✗ {e}", file=sys.stderr)
        sys.exit(1)

    print()

    # ========================================================================
    # Step 4: Find term candidates (Phase 2 - COMPLETE)
    # ========================================================================
    print("[phase-2] Finding terminology candidates with Python regex...")
    candidates_by_file = find_term_candidates(documents, glossary)
    total_candidates = sum(len(v) for v in candidates_by_file.values())
    print(f"[phase-2] ✓ Found {total_candidates} candidate issue(s)")

    # Debug: Print candidates for inspection
    if total_candidates > 0:
        print("\n[phase-2-debug] Candidate details:")
        for filepath, candidates in candidates_by_file.items():
            if candidates:
                print(f"  {filepath}:")
                for c in candidates:
                    print(f"    Line {c.line_number}: '{c.canonical_term}' → '{c.found_variant}' ({c.match_type})")
                    print(f"      Context: {c.context_snippet}")

    print()

    # ========================================================================
    # Step 5: Verify with Groq (Phase 3 - COMPLETE)
    # ========================================================================
    # Flatten candidates from dictionary into single list
    all_candidates: List[Candidate] = []
    for filepath, candidates in candidates_by_file.items():
        all_candidates.extend(candidates)

    # Call Groq for severity classification
    issues = verify_with_groq(all_candidates, glossary)
    print(f"[phase-3] ✓ Validation complete ({len(issues)} issue(s))")

    print()

    # ========================================================================
    # Step 6: Format report
    # ========================================================================
    report = format_output(issues, len(glossary), len(documents))

    # ========================================================================
    # Step 5: Format output (JSON + Markdown)
    # ========================================================================
    output_config = config.get("output", {})
    severity_threshold = output_config.get("severity_threshold", "info")
    artifact_name = output_config.get("artifact_name", "agent-qa-report")
    rendered = format_report(report, severity_threshold=severity_threshold)

    print("[report]")
    print(f"Status: {report.status.upper()}")
    print(f"Summary: {report.summary}")

    print()
    print("[markdown]")
    print(rendered["markdown"])

    print()
    print("[json]")
    print(rendered["json"])

    # Write artifacts to disk (CI uploads/reads these by the artifact_name
    # configured in agents.yaml's output.artifact_name)
    Path(f"{artifact_name}.md").write_text(rendered["markdown"] + "\n", encoding="utf-8")
    Path(f"{artifact_name}.json").write_text(rendered["json"] + "\n", encoding="utf-8")
    print(f"\n[output] Wrote {artifact_name}.md and {artifact_name}.json")

    # Return appropriate exit code
    sys.exit(0 if report.status == "pass" else 1)


if __name__ == "__main__":
    main()
