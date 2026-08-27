"""
Entry point for the alt text generator agent.

ARCHITECTURE (agents/ALT_TEXT_ARCHITECTURE.md):
  Load config → Scan docs → Detect/classify images → Verify with Groq
    vision (one call per "generate" image) → Format output

Mirrors agents/run_seo_optimizer.py's structure and phase numbering so
all three entry points stay easy to compare.

Note on artifacts: agents.yaml's `output` block (artifact_name,
severity_threshold, ...) is shared across agents rather than per-agent.
This entry point reuses `output.severity_threshold`... except AltTextIssue
has no severity concept, so it's accepted by the formatters for registry
signature compatibility only (see agents/output.py) and has no filtering
effect here. Writes its own files under a distinct "agent-alt-text-report"
name (hardcoded here) so it doesn't collide with the other two agents'
artifacts.

PHASE ROADMAP:
   Phase 1: scan_docs() - reused from agents/scan.py ✓
   Phase 2: find_alt_text_candidates() - classify + section-bounded context ✓
   Phase 3: generate_alt_text() - Groq vision, one call per image ✓
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
from agents.alt_text_finder import find_alt_text_candidates, resolve_decorative_paths
from agents.alt_text_verifier import generate_alt_text
from agents.output import format_report
from agents.documents import AltTextIssue, AltTextReport


# ============================================================================
# Format Output
# ============================================================================


def format_output(
    issues: List[AltTextIssue],
    images_scanned: int,
    files_count: int,
) -> AltTextReport:
    """
    Format alt text check results into structured report.

    Args:
        issues: List of alt-text issues found (generated suggestions +
            broken references)
        images_scanned: Count of images discovered across all files
        files_count: Count of files scanned

    Returns:
        AltTextReport with status, summary, and detailed findings
    """
    status = "pass" if not issues else "fail"
    summary = (
        f"✓ Alt text check passed ({images_scanned} images, {files_count} files)"
        if status == "pass"
        else f"✗ Alt text check found {len(issues)} issue(s) needing review"
    )

    return AltTextReport(
        status=status,
        issues_found=len(issues),
        issues=issues,
        images_scanned=images_scanned,
        files_scanned=files_count,
        summary=summary,
    )


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """
    Orchestrate the alt text generator workflow.

    Workflow:
    1. Load agents.yaml (discover config: decorative_paths, context_word_cap)
    2. Scan documentation files (reuses agents/scan.py)
    3. Per document: parse headings, classify every image reference
    4. Verify "generate"-classified images with Groq vision, ONE call per image
    5. Format and write report

    Exit behavior:
    - 0 if no issues are found
    - 1 if issues are found (suggestions to review, or broken references)
      or an error occurs
    """
    repo_root = Path(__file__).parent.parent
    config_path = repo_root / "agents.yaml"
    docs_root = repo_root / "docs"

    print(f"[alt-text-generator] Starting alt text check")
    print(f"[alt-text-generator] Repo root: {repo_root}")
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

    alt_text_config = config["agents"]["alt_text_generator"]
    sources = alt_text_config.get("sources", [])
    inner_config = alt_text_config.get("config", {})
    exclude_markers = inner_config.get("exclude_markers", [])
    decorative_patterns = inner_config.get("decorative_paths", [])
    context_word_cap = inner_config.get("context_word_cap", 200)

    decorative_paths = resolve_decorative_paths(decorative_patterns, docs_root)
    print(f"[config] ✓ Resolved {len(decorative_paths)} decorative image path(s)")

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
    # Step 3 & 4: Classify images, verify "generate" candidates with Groq
    # vision (Phase 2 + Phase 3, one Groq call per image)
    # ========================================================================
    print("[phase-2] Classifying image references...")
    all_issues: List[AltTextIssue] = []
    images_scanned = 0

    for doc in documents:
        headings = parse_headings_from_markdown(doc.content)

        candidates, broken_issues, doc_image_count = find_alt_text_candidates(
            doc, headings, docs_root, decorative_paths, context_word_cap
        )
        images_scanned += doc_image_count
        all_issues.extend(broken_issues)

        for candidate in candidates:
            all_issues.append(generate_alt_text(candidate))

    print(f"[phase-2] ✓ Scanned {images_scanned} image(s) across {len(documents)} file(s); "
          f"{len(all_issues)} issue(s) found")
    print()

    # ========================================================================
    # Step 5: Format report
    # ========================================================================
    report = format_output(all_issues, images_scanned, len(documents))

    output_config = config.get("output", {})
    severity_threshold = output_config.get("severity_threshold", "info")
    artifact_name = "agent-alt-text-report"
    rendered = format_report(
        report,
        formats=["alt_text_json", "alt_text_markdown"],
        severity_threshold=severity_threshold,
    )

    print("[report]")
    print(f"Status: {report.status.upper()}")
    print(f"Summary: {report.summary}")

    print()
    print("[markdown]")
    print(rendered["alt_text_markdown"])

    print()
    print("[json]")
    print(rendered["alt_text_json"])

    Path(f"{artifact_name}.md").write_text(rendered["alt_text_markdown"] + "\n", encoding="utf-8")
    Path(f"{artifact_name}.json").write_text(rendered["alt_text_json"] + "\n", encoding="utf-8")
    print(f"\n[output] Wrote {artifact_name}.md and {artifact_name}.json")

    # Return appropriate exit code
    sys.exit(0 if report.status == "pass" else 1)


if __name__ == "__main__":
    main()
