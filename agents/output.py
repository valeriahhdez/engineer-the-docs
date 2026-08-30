"""
Step 5: Format a report (ConsistencyReport or SeoReport) into output
formats (JSON, Markdown).

This module is a pure formatting layer: it takes an already-built report
and renders it as strings. It does not read config, scan files, or write
to disk — callers own I/O and config lookup.

Formatters are registered in FORMATTERS so new output formats (e.g. a
future GitHub PR annotation format, or a new agent's report type) can be
added without changing existing call sites: implement
`fn(report, severity_threshold) -> str` and add it to the registry.

The registry is shared across report types (ConsistencyReport's "json"/
"markdown", SeoReport's "seo_json"/"seo_markdown"), so format_report()
requires an explicit `formats` list — there is no "run every registered
formatter" default, since a ConsistencyReport handed to a SEO formatter
(or vice versa) would fail on the first Seo/Consistency-specific field
access. Callers always pass the formats that match their report type.

severity_threshold filters which issues are *displayed* by a formatter.
It does not affect the report's own status/issues_found, which always
reflect the full, unfiltered set of issues Phase 3 found.
"""

import json
from typing import Any, Callable, Dict, List, Union

from agents.documents import (
    AltTextReport,
    ConsistencyIssue,
    ConsistencyReport,
    SeoIssue,
    SeoReport,
)

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


def filter_by_severity(
    issues: List[Union[ConsistencyIssue, SeoIssue]], severity_threshold: str
) -> List[Union[ConsistencyIssue, SeoIssue]]:
    """
    Keep only issues at or above severity_threshold.

    Args:
        issues: Issues to filter (ConsistencyIssue or SeoIssue — both
            expose a `.severity` field)
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


def format_seo_json(report: SeoReport, severity_threshold: str = "info") -> str:
    """
    Render a SeoReport as JSON, for machine consumption
    (e.g. GitHub Actions artifact upload).

    Args:
        report: Report to render
        severity_threshold: Minimum severity to include in the 'issues' array

    Returns:
        JSON string. Top-level fields mirror SeoReport; 'issues' is
        filtered by severity_threshold, and 'issues_shown' records how
        many of the report's 'issues_found' survived the filter.
    """
    shown = filter_by_severity(report.issues, severity_threshold)
    payload = report.model_dump()
    payload["issues"] = [issue.model_dump() for issue in shown]
    payload["issues_shown"] = len(shown)
    return json.dumps(payload, indent=2)


def format_seo_markdown(report: SeoReport, severity_threshold: str = "info") -> str:
    """
    Render a SeoReport as a human-readable Markdown summary, for PR
    review / manual inspection.

    Args:
        report: Report to render
        severity_threshold: Minimum severity to include in the issues table

    Returns:
        Markdown string with a metadata summary and an issues table
        (omitted if no issues meet the threshold).
    """
    shown = filter_by_severity(report.issues, severity_threshold)

    lines = [
        f"# SEO heading check: {report.status.upper()}",
        "",
        report.summary,
        "",
        f"- Headings analyzed: {report.headings_analyzed}",
        f"- Files scanned: {report.files_scanned}",
        f"- Issues found: {report.issues_found} "
        f"(showing {len(shown)} at or above '{severity_threshold}')",
        "",
    ]

    if not shown:
        lines.append("No issues at or above the configured severity threshold.")
        return "\n".join(lines)

    lines.append("| File | Line | Heading | Parent | Type | Severity | Reasoning | Suggested fix |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for issue in shown:
        lines.append(
            "| {file} | {line} | {heading} | {parent} | {issue_type} | {severity} | {reasoning} | {fix} |".format(
                file=_escape_markdown_cell(issue.file_path),
                line=issue.line_number,
                heading=_escape_markdown_cell(f"H{issue.heading_level} {issue.heading_text}"),
                parent=_escape_markdown_cell(issue.parent_heading or "—"),
                issue_type=issue.issue_type,
                severity=issue.severity,
                reasoning=_escape_markdown_cell(issue.reasoning),
                fix=_escape_markdown_cell(issue.suggested_fix),
            )
        )

    return "\n".join(lines)


def format_alt_text_json(report: AltTextReport, severity_threshold: str = "info") -> str:
    """
    Render an AltTextReport as JSON, for machine consumption
    (e.g. GitHub Actions artifact upload).

    Args:
        report: Report to render
        severity_threshold: Accepted for FORMATTERS registry signature
            compatibility only — AltTextIssue has no severity concept
            (it's a generated suggestion or a broken-reference flag, not
            a graded violation), so this has no filtering effect here.

    Returns:
        JSON string. Top-level fields mirror AltTextReport; 'issues' is
        the full, unfiltered list.
    """
    payload = report.model_dump()
    payload["issues_shown"] = len(report.issues)
    return json.dumps(payload, indent=2)


def format_alt_text_markdown(report: AltTextReport, severity_threshold: str = "info") -> str:
    """
    Render an AltTextReport as a human-readable Markdown summary, for PR
    review / manual acceptance of suggested alt text.

    Args:
        report: Report to render
        severity_threshold: Accepted for FORMATTERS registry signature
            compatibility only — see format_alt_text_json.

    Returns:
        Markdown string with a metadata summary and an issues table
        (omitted if there are no issues).
    """
    lines = [
        f"# Alt text check: {report.status.upper()}",
        "",
        report.summary,
        "",
        f"- Images scanned: {report.images_scanned}",
        f"- Files scanned: {report.files_scanned}",
        f"- Issues found: {report.issues_found}",
        "",
    ]

    if not report.issues:
        lines.append("No missing or broken alt text found.")
        return "\n".join(lines)

    lines.append("| File | Line | Image | Heading | Source | Confidence | Suggested alt | Reasoning |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for issue in report.issues:
        suggested = issue.suggested_alt if issue.source != "broken_reference" else "**BROKEN REFERENCE**"
        lines.append(
            "| {file} | {line} | {image} | {heading} | {source} | {confidence} | {suggested} | {reasoning} |".format(
                file=_escape_markdown_cell(issue.file_path),
                line=issue.line_number,
                image=_escape_markdown_cell(issue.image_path),
                heading=_escape_markdown_cell(issue.heading_breadcrumb or "—"),
                source=issue.source,
                confidence=issue.confidence or "—",
                suggested=_escape_markdown_cell(suggested),
                reasoning=_escape_markdown_cell(issue.reasoning or "—"),
            )
        )

    return "\n".join(lines)


FORMATTERS: Dict[str, Callable[[Any, str], str]] = {
    "json": format_json,
    "markdown": format_markdown,
    "seo_json": format_seo_json,
    "seo_markdown": format_seo_markdown,
    "alt_text_json": format_alt_text_json,
    "alt_text_markdown": format_alt_text_markdown,
}


def format_report(
    report: Union[ConsistencyReport, SeoReport, AltTextReport],
    formats: List[str],
    severity_threshold: str = "info",
) -> Dict[str, str]:
    """
    Render a report with one or more registered formatters.

    Args:
        report: Report to render (ConsistencyReport, SeoReport, or AltTextReport)
        formats: Formatter names to run — must match the report type
            (e.g. ["json", "markdown"] for a ConsistencyReport,
            ["seo_json", "seo_markdown"] for a SeoReport,
            ["alt_text_json", "alt_text_markdown"] for an AltTextReport).
            Required: the registry holds formatters for multiple report
            types, so there's no safe "run everything" default.
        severity_threshold: Minimum severity to include ('info', 'warning', 'error')

    Returns:
        Dict mapping formatter name to its rendered string.

    Raises:
        ValueError: If a requested formatter name isn't registered.
    """
    unknown = [name for name in formats if name not in FORMATTERS]
    if unknown:
        raise ValueError(
            f"Unknown formatter(s): {unknown}. Available: {list(FORMATTERS.keys())}"
        )

    return {
        name: FORMATTERS[name](report, severity_threshold) for name in formats
    }
