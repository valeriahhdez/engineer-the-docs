"""
Entry point for the SEO heading optimizer agent.

ARCHITECTURE:
  Load config → Scan docs → Parse headings → Detect hierarchy violations
    → Verify with Groq (batched per document) → Format output

Mirrors agents/run_consistency_checker.py's structure and phase numbering
so the two entry points stay easy to compare.

Note on artifacts: agents.yaml's `output` block (artifact_name,
severity_threshold, ...) is shared across agents rather than per-agent.
This entry point reuses `output.severity_threshold` but writes its own
files under a distinct "agent-seo-report" name (hardcoded here) so it
doesn't collide with the consistency checker's "agent-qa-report" files.

PHASE ROADMAP:
   Phase 1: scan_docs() - reused from agents/scan.py ✓
   Phase 2: parse_headings_from_markdown() + detect_hierarchy_violations() ✓
   Phase 3: verify_seo_with_groq() - batched, one call per document ✓
   Phase 4: format_report() - reused from agents/output.py's registry ✓
"""

import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()  # Load .env file

# Add parent directory to path so we can import agents module
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.config import load_config
from agents.scan import scan_docs
from agents.parsing import parse_headings_from_markdown
from agents.seo_optimizer import detect_hierarchy_violations
from agents.seo_verifier import verify_seo_with_groq
from agents.output import format_report
from agents.documents import SeoIssue, SeoReport


# ============================================================================
# Format Output
# ============================================================================


def format_output(
    issues: List[SeoIssue],
    headings_analyzed: int,
    files_count: int,
) -> SeoReport:
    """
    Format SEO check results into structured report.

    Args:
        issues: List of SEO issues found
        headings_analyzed: Count of headings evaluated across all files
        files_count: Count of files scanned

    Returns:
        SeoReport with status, summary, and detailed findings
    """
    status = "pass" if not issues else "fail"
    summary = (
        f"✓ SEO check passed ({headings_analyzed} headings, {files_count} files)"
        if status == "pass"
        else f"✗ SEO check failed: {len(issues)} issue(s) found"
    )

    return SeoReport(
        status=status,
        issues_found=len(issues),
        issues=issues,
        headings_analyzed=headings_analyzed,
        files_scanned=files_count,
        summary=summary,
    )


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """
    Orchestrate the SEO heading optimizer workflow.

    Workflow:
    1. Load agents.yaml (discover config and hierarchy rules)
    2. Scan documentation files (reuses agents/scan.py)
    3. Parse headings and detect hierarchy violations, per document
    4. Verify with Groq, ONE batched call per document
    5. Format and write report

    Exit behavior:
    - 0 if the SEO check passes
    - 1 if issues are found or an error occurs
    """
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "agents.yaml"
    docs_root = repo_root / "docs"

    print(f"[seo-optimizer] Starting SEO heading check")
    print(f"[seo-optimizer] Repo root: {repo_root}")
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

    seo_config = config["agents"]["seo_optimizer"]
    sources = seo_config.get("sources", [])
    inner_config = seo_config.get("config", {})
    exclude_markers = inner_config.get("exclude_markers", [])
    hierarchy_rules = inner_config.get("hierarchy_rules", {})
    clarity_threshold = inner_config.get("clarity_threshold", 40)

    print()

    # ========================================================================
    # Step 2: Scan documentation (Phase 1, reused from agents/scan.py)
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
    # Step 3 & 4: Parse headings, detect violations, verify with Groq
    # (Phase 2 + batched Phase 3, one Groq call per document)
    # ========================================================================
    print("[phase-2] Parsing headings and detecting hierarchy violations...")
    all_issues: List[SeoIssue] = []
    headings_analyzed = 0

    for doc in documents:
        headings = parse_headings_from_markdown(doc.content)
        headings_analyzed += len(headings)

        violations = detect_hierarchy_violations(headings, hierarchy_rules)
        print(
            f"[phase-2]   {doc.file_path}: {len(headings)} heading(s), "
            f"{len(violations)} violation(s)"
        )

        doc_issues = verify_seo_with_groq(
            doc.file_path, headings, violations, clarity_threshold
        )
        all_issues.extend(doc_issues)

    print(f"[phase-2] ✓ Analyzed {headings_analyzed} heading(s) across {len(documents)} file(s)")
    print()

    # ========================================================================
    # Step 5: Format report
    # ========================================================================
    report = format_output(all_issues, headings_analyzed, len(documents))

    output_config = config.get("output", {})
    severity_threshold = output_config.get("severity_threshold", "info")
    artifact_name = "agent-seo-report"
    rendered = format_report(
        report, formats=["seo_json", "seo_markdown"], severity_threshold=severity_threshold
    )

    print("[report]")
    print(f"Status: {report.status.upper()}")
    print(f"Summary: {report.summary}")

    print()
    print("[markdown]")
    print(rendered["seo_markdown"])

    print()
    print("[json]")
    print(rendered["seo_json"])

    Path(f"{artifact_name}.md").write_text(rendered["seo_markdown"] + "\n", encoding="utf-8")
    Path(f"{artifact_name}.json").write_text(rendered["seo_json"] + "\n", encoding="utf-8")
    print(f"\n[output] Wrote {artifact_name}.md and {artifact_name}.json")

    # Return appropriate exit code
    sys.exit(0 if report.status == "pass" else 1)


if __name__ == "__main__":
    main()
