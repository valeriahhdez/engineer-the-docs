"""
Data models for document processing, consistency checking, and SEO heading
analysis.

This module defines Pydantic models for:
- DocumentInput: Represents a scanned markdown file
- Candidate: Represents a flagged terminology variant found by Python regex
- ConsistencyIssue: Represents a validated issue (after Groq verification)
- HeadingNode: Represents a parsed markdown heading with hierarchy context
- SeoHierarchyIssue: Represents a flagged heading violation found by Python
- SeoIssue: Represents a validated SEO issue (after Groq verification)

All models enforce strict validation and type safety for portfolio quality.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentInput(BaseModel):
    """Represents a scanned markdown document."""

    file_path: str = Field(
        ...,
        description="Relative path to the markdown file (e.g., 'docs/intro.md')"
    )
    content: str = Field(
        ...,
        description="Full markdown file content"
    )
    lines: List[str] = Field(
        default_factory=list,
        description="Lines of the document (split by newline)"
    )

    class Config:
        strict = True


class Candidate(BaseModel):
    """Represents a flagged terminology variant found by Python regex."""

    file_path: str = Field(..., description="Relative path to file")
    line_number: int = Field(..., description="1-indexed line number (exact)")
    canonical_term: str = Field(..., description="Term from glossary")
    found_variant: str = Field(..., description="Variant found in document")
    context_snippet: str = Field(
        ...,
        description="Surrounding text (e.g., 10 chars before/after)"
    )
    raw_text: str = Field(..., description="Full line text where variant was found")
    match_type: str = Field(
        default="unknown",
        description="Type of mismatch: case_mismatch, abbreviation, spelling, etc."
    )

    class Config:
        strict = True


class ConsistencyIssue(BaseModel):
    """Represents a validated consistency issue (after Groq verification)."""

    file_path: str = Field(..., description="Relative path to checked file")
    line_number: int = Field(..., description="Line where issue occurred (exact)")
    canonical_term: str = Field(..., description="Canonical term from glossary")
    found_variant: str = Field(..., description="Variant found in document")
    context_snippet: str = Field(..., description="Surrounding text for context")
    severity: str = Field(
        ...,
        description="Issue severity: 'error', 'warning', or 'info'"
    )
    reasoning: str = Field(
        default="",
        description="Why Groq classified this issue with this severity"
    )
    match_type: str = Field(
        default="unknown",
        description="Type of mismatch: case_mismatch, abbreviation, spelling, etc."
    )

    class Config:
        strict = True


class ConsistencyReport(BaseModel):
    """Structured output from consistency checker agent."""

    status: str = Field(
        ...,
        description="'pass' or 'fail'"
    )
    issues_found: int = Field(
        ...,
        description="Count of consistency violations"
    )
    issues: List[ConsistencyIssue] = Field(
        default_factory=list,
        description="List of specific issues"
    )
    glossary_terms_checked: int = Field(
        ...,
        description="Count of canonical terms evaluated"
    )
    files_scanned: int = Field(
        ...,
        description="Count of documentation files"
    )
    summary: str = Field(
        ...,
        description="Human-readable summary"
    )

    class Config:
        strict = True


class HeadingNode(BaseModel):
    """Represents a parsed markdown heading, with hierarchy context."""

    level: int = Field(..., description="Heading level, 1-6 (H1-H6)")
    text: str = Field(..., description="Heading text, e.g. 'Setting Up Kubernetes'")
    line_number: int = Field(..., description="1-indexed line number (exact)")
    parent_heading: Optional[str] = Field(
        default=None,
        description="Text of the nearest preceding heading with a lower level, if any"
    )

    class Config:
        strict = True


class SeoHierarchyIssue(BaseModel):
    """Represents a flagged heading hierarchy violation found by Python (no severity yet)."""

    issue_type: str = Field(
        ...,
        description="e.g. 'missing_h1', 'h1_skip', 'h2_skip', 'max_depth_exceeded'"
    )
    heading_level: int = Field(..., description="Level of the heading that triggered the violation")
    expected_level: int = Field(..., description="Level the hierarchy rules expected instead")
    heading_text: str = Field(..., description="Text of the offending heading")
    line_number: int = Field(..., description="1-indexed line number of the offending heading")
    reasoning: str = Field(
        ...,
        description="Why this is a violation, e.g. 'H1 must be followed by H2, not H3'"
    )

    class Config:
        strict = True


class SeoIssue(BaseModel):
    """Represents a validated SEO issue (after Groq verification)."""

    file_path: str = Field(..., description="Relative path to checked file")
    line_number: int = Field(..., description="1-indexed line number of the heading")
    heading_level: int = Field(..., description="Heading level, 1-6 (H1-H6)")
    heading_text: str = Field(..., description="Heading text")
    parent_heading: Optional[str] = Field(
        default=None,
        description="Text of the enclosing heading, if any"
    )
    issue_type: str = Field(..., description="'hierarchy_violation' or 'low_clarity'")
    severity: str = Field(..., description="Issue severity: 'error', 'warning', or 'info'")
    reasoning: str = Field(default="", description="Why Groq classified this issue with this severity")
    suggested_fix: str = Field(default="", description="Actionable rewrite or fix suggestion")

    class Config:
        strict = True


class SeoReport(BaseModel):
    """Structured output from the SEO heading optimizer agent."""

    status: str = Field(..., description="'pass' or 'fail'")
    issues_found: int = Field(..., description="Count of SEO issues")
    issues: List[SeoIssue] = Field(default_factory=list, description="List of specific issues")
    headings_analyzed: int = Field(..., description="Count of headings evaluated")
    files_scanned: int = Field(..., description="Count of documentation files")
    summary: str = Field(..., description="Human-readable summary")

    class Config:
        strict = True
