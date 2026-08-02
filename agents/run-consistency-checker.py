"""
Consistency Checker Agent - Entry Point Skeleton

ARCHITECTURE:
  Load config → Scan docs → Run agent → Format output → Return results

DISCOVERY & EXECUTION RULES:

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

from dataclasses import dataclass
from typing import List
from pathlib import Path
import glob
import yaml


# ============================================================================
# DATA STRUCTURES - Typed data flowing between steps
# ============================================================================

@dataclass
class DocumentInput:
    """A single markdown file ready for checking."""
    filepath: str      # relative path: "docs/get-started/setup.md"
    content: str       # full markdown text
    file_id: str       # unique ID for linking in output


@dataclass
class ConsistencyIssue:
    """A single consistency violation found by the agent."""
    filepath: str
    line_num: int
    term: str          # the term that was inconsistent
    expected: str      # what the glossary says it should be
    found: str         # what was actually in the doc
    context: str       # surrounding text (for verification)
    severity: str      # "error" | "warning" | "info"


@dataclass
class ConsistencyReport:
    """Full results from consistency checker."""
    issues: List[ConsistencyIssue]
    file_count: int
    issue_count: int
    by_severity: dict  # {"error": 5, "warning": 12, "info": 3}


# ============================================================================
# STEP 1: LOAD CONFIG & GLOSSARY
# ============================================================================

def load_config(config_path: str = "agents.yaml") -> dict:
    """
    Load agents.yaml and validate structure.
    
    Raises FileNotFoundError or ValueError if:
      - File doesn't exist
      - File has invalid YAML
      - Missing consistency_checker section
    
    Returns:
      {
        "consistency_checker": {
          "enabled": True,
          "sources": ["docs/**/*.md", "!docs/generated/**/*.md"],
          "config": {
            "glossary_path": "reference/glossary.yaml",
            "exclude_markers": ["# --no-consistency-check"]
          }
        }
      }
    """
    # Validate file exists
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    
    # Load YAML
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}")
    
    # Validate structure
    if not config or "agents" not in config:
        raise ValueError(f"Config missing 'agents' section")
    
    if "consistency_checker" not in config["agents"]:
        raise ValueError(f"Config missing 'agents.consistency_checker' section")
    
    print(f"✓ Config loaded from {config_path}")
    return config


def load_glossary(glossary_path: str) -> dict:
    """
    Load reference/glossary.yaml.
    
    Raises FileNotFoundError or ValueError if:
      - File doesn't exist
      - File is empty or invalid YAML
      - File has fewer than 3 terms (sanity check)
    
    Returns:
      {
        "API": "API (Application Programming Interface)",
        "GitHub": "GitHub",
        "Zensical": "Zensical",
        ...
      }
    """
    # Validate file exists
    if not Path(glossary_path).exists():
        raise FileNotFoundError(f"Glossary not found: {glossary_path}")
    
    # Load YAML
    try:
        with open(glossary_path, 'r') as f:
            glossary = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {glossary_path}: {e}")
    
    # Validate content
    if not glossary or len(glossary) < 3:
        raise ValueError(f"Glossary has {len(glossary or {})} terms; need at least 3")
    
    print(f"✓ Glossary loaded: {len(glossary)} terms from {glossary_path}")
    return glossary


# ============================================================================
# STEP 2: INPUT ADAPTER - Scan docs with opt-in & negation logic
# ============================================================================

def scan_docs(sources: List[str], exclude_markers: List[str]) -> List[DocumentInput]:
    """
    Scan docs/ folder for markdown files using two-pass glob logic.
    
    Two-pass glob:
      Pass 1: Collect all files matching positive patterns
      Pass 2: Remove files matching negative patterns (! prefix)
    
    Respects markers:
      - Files with '# --no-consistency-check' at top are skipped
      - Marker must be first line (file-level exclusion only)
    
    Args:
      sources: ["docs/**/*.md", "!docs/generated/**/*.md"]
      exclude_markers: ["# --no-consistency-check"]
    
    Returns:
      [DocumentInput(...), DocumentInput(...), ...]
    
    TODO: Replace mock with real file globbing + marker checking.
    """
    
    # Separate positive and negative patterns
    positive_sources = [s for s in sources if not s.startswith("!")]
    negative_sources = [s[1:] for s in sources if s.startswith("!")]
    
    # Pass 1: Collect files matching positive patterns
    files = set()
    for pattern in positive_sources:
        # TODO: Use glob.glob(pattern, recursive=True)
        # files.update(glob.glob(pattern, recursive=True))
        pass
    
    # Pass 2: Remove files matching negative patterns
    for pattern in negative_sources:
        # TODO: Use glob.glob(pattern, recursive=True)
        # files -= set(glob.glob(pattern, recursive=True))
        pass
    
    # Mock files for demo
    mock_files = [
        DocumentInput(
            filepath="docs/introduction/docs-engineering-overview.md",
            content="# Docs-as-Code Overview\n\nGithub Actions powers our CI/CD...",
            file_id="intro-overview"
        ),
        DocumentInput(
            filepath="docs/get-started/setup-project.md",
            content="# Set Up Your Project\n\nUse the github CLI...",
            file_id="gs-setup"
        ),
    ]
    
    print(f"✓ Scanned docs/: found {len(mock_files)} files")
    print(f"  Positive patterns: {positive_sources}")
    print(f"  Negative patterns: {negative_sources}")
    print(f"  Skipped (markers): 0")
    
    return mock_files


# ============================================================================
# STEP 3: AGENT LOGIC - Consistency checker with Groq
# ============================================================================

def consistency_checker_agent(
    documents: List[DocumentInput],
    glossary: dict,
    groq_api_key: str = None
) -> List[ConsistencyIssue]:
    """
    Check each document against glossary using Groq API with JSON mode.
    
    Flow:
      1. For each document, build prompt with glossary + text
      2. Call Groq API with response_format=json_schema (structured output)
      3. Parse response: extract issues (term, line_num, severity)
         - Groq returns validated Pydantic JSON, no parsing errors
      4. Accumulate issues
    
    Args:
      documents: List of DocumentInput from Step 2
      glossary: Dict from Step 1
      groq_api_key: API key (from env or config)
    
    Returns:
      [ConsistencyIssue(...), ...]
    
    TODO: 
      - Implement actual Groq API call with response_format
      - Design prompt that returns structured JSON
      - Handle API errors gracefully
    """
    
    issues = []
    
    for doc in documents:
        # TODO: Build prompt with glossary + document content
        # prompt = f"""
        # You are a documentation consistency checker.
        # 
        # Glossary:
        # {json.dumps(glossary, indent=2)}
        # 
        # Document:
        # {doc.content}
        # 
        # Find all terms in the document that don't match the glossary.
        # Return ONLY valid JSON matching this schema:
        # {ConsistencyIssueResponse.model_json_schema()}
        # """
        
        # TODO: Call Groq API
        # response = groq.Completion.create(
        #     model="mixtral-8x7b-32768",  # or similar
        #     messages=[{"role": "user", "content": prompt}],
        #     response_format={
        #         "type": "json_schema",
        #         "json_schema": {
        #             "name": "consistency_check",
        #             "schema": ConsistencyAgentResponse.model_json_schema()
        #         }
        #     }
        # )
        
        # Mock issue for demo (shows expected shape)
        issues.append(
            ConsistencyIssue(
                filepath=doc.filepath,
                line_num=5,
                term="github",
                expected="GitHub",
                found="github",
                context="Use the github CLI to clone...",
                severity="warning"
            )
        )
    
    print(f"✓ Agent processed {len(documents)} documents")
    print(f"  Found {len(issues)} issues")
    return issues


# ============================================================================
# STEP 4: OUTPUT FORMATTER - Structure results for manual review
# ============================================================================

def format_output(issues: List[ConsistencyIssue], file_count: int) -> ConsistencyReport:
    """
    Structure issues into a report (typed data).
    
    Output layers (will be implemented in output.py):
      1. JSON artifact: Machine-readable, GitHub artifact upload
      2. Markdown summary: Human-readable for review
      3. GitHub PR annotations: Inline comments (future)
    
    Args:
      issues: List of ConsistencyIssue from Step 3
      file_count: Number of files checked
    
    Returns:
      ConsistencyReport with:
        - issues: full list (typed)
        - file_count: docs checked
        - issue_count: total issues found
        - by_severity: breakdown of error/warning/info
    """
    
    by_severity = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        by_severity[issue.severity] += 1
    
    report = ConsistencyReport(
        issues=issues,
        file_count=file_count,
        issue_count=len(issues),
        by_severity=by_severity
    )
    
    print(f"✓ Report formatted:")
    print(f"  {report.issue_count} issues across {report.file_count} files")
    print(f"  Errors: {by_severity['error']}, Warnings: {by_severity['warning']}, Info: {by_severity['info']}")
    
    return report


# ============================================================================
# STEP 5: MAIN ENTRY POINT - Wires all steps together
# ============================================================================

def main(config_path: str = "agents.yaml", groq_api_key: str = None):
    """
    Run the consistency checker end-to-end.
    
    Args:
      config_path: Path to agents.yaml
      groq_api_key: Groq API key (or read from env)
    
    Returns:
      ConsistencyReport (typed, ready for output formatting)
    
    Exit codes:
      0: Success (issues found or no issues)
      1: Hard failure (missing config, invalid glossary, API error)
    """
    
    print("\n" + "="*70)
    print("CONSISTENCY CHECKER AGENT - SKELETON RUN")
    print("="*70 + "\n")
    
    try:
        # Step 1: Load config and glossary
        config = load_config(config_path)
        cc_config = config["agents"]["consistency_checker"]["config"]
        glossary = load_glossary(cc_config["glossary_path"])
        
        # Step 2: Scan docs (two-pass glob + marker logic)
        documents = scan_docs(
            sources=config["agents"]["consistency_checker"]["sources"],
            exclude_markers=cc_config.get("exclude_markers", [])
        )
        
        # Step 3: Run agent (Groq API with structured output)
        issues = consistency_checker_agent(documents, glossary, groq_api_key)
        
        # Step 4: Format output (typed report)
        report = format_output(issues, file_count=len(documents))
        
        # Print summary
        print("\n" + "="*70)
        print("REPORT SUMMARY")
        print("="*70)
        print(f"Files checked:    {report.file_count}")
        print(f"Total issues:     {report.issue_count}")
        print(f"  Errors:         {report.by_severity['error']}")
        print(f"  Warnings:       {report.by_severity['warning']}")
        print(f"  Info:           {report.by_severity['info']}")
        
        if report.issues:
            print("\nFirst issue (example):")
            issue = report.issues[0]
            print(f"  File:    {issue.filepath}:{issue.line_num}")
            print(f"  Term:    '{issue.found}' → should be '{issue.expected}'")
            print(f"  Context: {issue.context}")
        
        print("\n" + "="*70)
        print("Output formats (to implement in output.py):")
        print("="*70)
        print("1. JSON artifact → GitHub Actions artifact store")
        print("2. Markdown summary → artifact + manual review")
        print("3. GitHub PR annotations → inline comments (future)")
        
        return report, 0
        
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("  Make sure agents.yaml and glossary file exist.")
        return None, 1
    except ValueError as e:
        print(f"\n✗ Error: {e}")
        print("  Glossary validation failed.")
        return None, 1


if __name__ == "__main__":
    report, exit_code = main()
    
    print("\n" + "="*70)
    print("NEXT STEPS (Implementation roadmap)")
    print("="*70)
    print("""
1. Create agents/config.py
   - load_config(): Read YAML, validate structure
   - load_glossary(): Read YAML, validate (≥3 terms, all strings)
   
2. Create agents/input_adapter.py (or inline in consistency_checker.py)
   - scan_docs(): Implement glob + negation logic
   - marker detection: Check file first line for # --no-consistency-check
   
3. Create agents/consistency_checker.py
   - consistency_checker_agent(): Call Groq API with JSON schema
   - Design prompt: Glossary terms → check document → return issues
   
4. Create agents/output.py
   - to_json_artifact(): Serialize report to JSON
   - to_markdown_summary(): Serialize report to Markdown table
   - to_github_annotations(): Serialize to ::warning/::error format
    """)
    print("="*70 + "\n")
    
    exit(exit_code)