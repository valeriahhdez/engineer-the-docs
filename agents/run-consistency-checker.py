"""
Entry point for the consistency checker agent.

ARCHITECTURE:
  Load config → Scan docs → Run agent → Format output → Return results

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
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List
 
import yaml
from pydantic import BaseModel, Field
 
# Add parent directory to path so we can import agents module
sys.path.insert(0, str(Path(__file__).parent.parent))
 
# Import production-ready config loaders
from agents.config import load_config, load_glossary
 
 
# ============================================================================
# Type Definitions
# ============================================================================
 
class ConsistencyIssue(BaseModel):
    """Single consistency check finding."""
 
    file_path: str = Field(..., description="Relative path to checked file")
    line_number: int = Field(..., description="Line where issue occurred")
    term: str = Field(..., description="Canonical term from glossary")
    found: str = Field(..., description="Variant found in document")
    message: str = Field(..., description="Human-readable issue description")
 
 
class ConsistencyReport(BaseModel):
    """Structured output from consistency checker agent."""
 
    status: str = Field(..., description="'pass' or 'fail'")
    issues_found: int = Field(..., description="Count of consistency violations")
    issues: List[ConsistencyIssue] = Field(
        default_factory=list, description="List of specific issues"
    )
    glossary_terms_checked: int = Field(
        ..., description="Count of canonical terms evaluated"
    )
    files_scanned: int = Field(..., description="Count of documentation files")
    summary: str = Field(..., description="Human-readable summary")
 
 
# ============================================================================
# Mock Functions (Entry Point Skeleton)
# ============================================================================
 
 
def scan_docs(docs_root: str, marker_filter: str = "") -> List[str]:
    """
    Mock: Scan documentation files matching opt-in markers.
 
    This is a skeleton function. In production, it will:
    1. Walk docs_root recursively
    2. Filter files by marker (e.g., skip files marked `# --no-consistency-check`)
    3. Return list of markdown file paths
 
    Args:
        docs_root: Root directory for documentation
        marker_filter: Optional agent-specific marker to exclude files
 
    Returns:
        List of file paths (currently mocked)
    """
    # MOCK: Return hardcoded file paths
    return [
        "docs/index.md",
        "docs/guides/setup.md",
        "docs/guides/architecture.md",
        "docs/reference/cli.md",
    ]
 
 
def consistency_checker_agent(
    file_paths: List[str], glossary: Dict[str, str]
) -> List[ConsistencyIssue]:
    """
    Mock: Run consistency check against canonical terminology.
 
    This is a skeleton function. In production, it will:
    1. Load each file
    2. Search for glossary terms and variants
    3. Return issues for terminology mismatches
 
    Args:
        file_paths: List of markdown files to check
        glossary: Canonical terminology dictionary
 
    Returns:
        List of consistency issues (currently mocked)
    """
    # MOCK: Return empty list (no issues found)
    return []
 
 
def format_output(
    issues: List[ConsistencyIssue], glossary_size: int, files_count: int
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
    3. Scan documentation files
    4. Run consistency check agent
    5. Format and return report
 
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
 
    # Extract glossary path from config
    glossary_path_rel = config["agents"]["consistency_checker"]["config"]["glossary_path"]
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
    # Step 3: Scan documentation
    # ========================================================================
    print("[scan] Scanning documentation files...")
    file_paths = scan_docs(str(docs_root))
    print(f"[scan] ✓ Found {len(file_paths)} files")
 
    # ========================================================================
    # Step 4: Run consistency check agent
    # ========================================================================
    print("[agent] Running consistency check...")
    issues = consistency_checker_agent(file_paths, glossary)
    print(f"[agent] ✓ Check complete ({len(issues)} issues)")
 
    # ========================================================================
    # Step 5: Format report
    # ========================================================================
    print()
    report = format_output(issues, len(glossary), len(file_paths))
 
    # ========================================================================
    # Output
    # ========================================================================
    print("[report]")
    print(f"Status: {report.status.upper()}")
    print(f"Summary: {report.summary}")
    print(f"Glossary terms checked: {report.glossary_terms_checked}")
    print(f"Files scanned: {report.files_scanned}")
    print(f"Issues found: {report.issues_found}")
 
    if report.issues:
        print("\n[issues]")
        for issue in report.issues:
            print(f"  {issue.file_path}:{issue.line_number} - {issue.message}")
 
    print()
    print("[result]")
    print(report.model_dump_json(indent=2))
 
    # Return appropriate exit code
    sys.exit(0 if report.status == "pass" else 1)
 
 
if __name__ == "__main__":
    main()
 