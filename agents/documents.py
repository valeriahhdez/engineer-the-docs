"""
Data models for document processing and consistency checking.

This module defines Pydantic models for:
- DocumentInput: Represents a scanned markdown file
- Candidate: Represents a flagged terminology variant found by Python regex
- ConsistencyIssue: Represents a validated issue (after Groq verification)

All models enforce strict validation and type safety for portfolio quality.
"""

from typing import List
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
