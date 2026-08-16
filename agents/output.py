"""
Step 5: Format a ConsistencyReport into output formats (JSON, Markdown).

This module is a pure formatting layer: it takes an already-built
ConsistencyReport and renders it as strings. It does not read config,
scan files, or write to disk — callers own I/O and config lookup.

Formatters are registered in FORMATTERS so new output formats (e.g. a
future GitHub PR annotation format) can be added without changing call
sites: implement `fn(report, severity_threshold) -> str` and add it to
the registry.

severity_threshold filters which issues are *displayed* by a formatter.
It does not affect the report's own status/issues_found, which always
reflect the full, unfiltered set of issues Phase 3 found.
"""

import json
from typing import Callable, Dict, List, Optional

from agents.documents import ConsistencyIssue, ConsistencyReport

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


def filter_by_severity(
    issues: List[ConsistencyIssue], severity_threshold: str
) -> List[ConsistencyIssue]:
    """
    Keep only issues at or above severity_threshold.

    Args:
        issues: Issues to filter
        severity_threshold: Minimum severity to keep ('info', 'warning', 'error')

    Returns:
        Issues with severity >= severity_threshold. Unrecognized severities
        are treated as 'info' (lowest), matching the existing 'unknown
        match_type' fallback pattern used elsewhere in this package.
    """
    threshold_level = SEVERITY_ORDER.get(severity_threshold, 0)
    return [
        issue
        for issue in issues
        if SEVERITY_ORDER.get(issue.severity, 0) >= threshold_level
    ]


def _escape_markdown_cell(text: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def format_json(report: ConsistencyReport, severity_threshold: str = "info") -> str:
    """
    Render a ConsistencyReport as JSON, for machine consumption
    (e.g. GitHub Actions artifact upload).

    Args:
        report: Report to render
        severity_threshold: Minimum severity to include in the 'issues' array

    Returns:
        JSON string. Top-level fields mirror ConsistencyReport; 'issues'
        is filtered by severity_threshold, and 'issues_shown' records how
        many of the report's 'issues_found' survived the filter.
    """
    shown = filter_by_severity(report.issues, severity_threshold)
    payload = report.model_dump()
    payload["issues"] = [issue.model_dump() for issue in shown]
    payload["issues_shown"] = len(shown)
    return json.dumps(payload, indent=2)


def format_markdown(report: ConsistencyReport, severity_threshold: str = "info") -> str:
    """
    Render a ConsistencyReport as a human-readable Markdown summary,
    for PR review / manual inspection.

    Args:
        report: Report to render
        severity_threshold: Minimum severity to include in the issues table

    Returns:
        Markdown string with a metadata summary and an issues table
        (omitted if no issues meet the threshold).
    """
    shown = filter_by_severity(report.issues, severity_threshold)

    lines = [
        f"# Consistency check: {report.status.upper()}",
        "",
        report.summary,
        "",
        f"- Glossary terms checked: {report.glossary_terms_checked}",
        f"- Files scanned: {report.files_scanned}",
        f"- Issues found: {report.issues_found} "
        f"(showing {len(shown)} at or above '{severity_threshold}')",
        "",
    ]

    if not shown:
        lines.append("No issues at or above the configured severity threshold.")
        return "\n".join(lines)

    lines.append("| File | Line | Canonical term | Found variant | Severity | Reasoning |")
    lines.append("|---|---|---|---|---|---|")
    for issue in shown:
        lines.append(
            "| {file} | {line} | {term} | {variant} | {severity} | {reasoning} |".format(
                file=_escape_markdown_cell(issue.file_path),
                line=issue.line_number,
                term=_escape_markdown_cell(issue.canonical_term),
                variant=_escape_markdown_cell(issue.found_variant),
                severity=issue.severity,
                reasoning=_escape_markdown_cell(issue.reasoning),
            )
        )

    return "\n".join(lines)


FORMATTERS: Dict[str, Callable[[ConsistencyReport, str], str]] = {
    "json": format_json,
    "markdown": format_markdown,
}


def format_report(
    report: ConsistencyReport,
    formats: Optional[List[str]] = None,
    severity_threshold: str = "info",
) -> Dict[str, str]:
    """
    Render a ConsistencyReport with one or more registered formatters.

    Args:
        report: Report to render
        formats: Formatter names to run (defaults to every registered formatter)
        severity_threshold: Minimum severity to include ('info', 'warning', 'error')

    Returns:
        Dict mapping formatter name to its rendered string.

    Raises:
        ValueError: If a requested formatter name isn't registered.
    """
    if formats is None:
        formats = list(FORMATTERS.keys())

    unknown = [name for name in formats if name not in FORMATTERS]
    if unknown:
        raise ValueError(
            f"Unknown formatter(s): {unknown}. Available: {list(FORMATTERS.keys())}"
        )

    return {
        name: FORMATTERS[name](report, severity_threshold) for name in formats
    }
