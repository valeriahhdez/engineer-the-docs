"""
Phase 3 (SEO): Groq batched verification for heading clarity + violation severity.

This module sends ALL headings and hierarchy violations for a single
document in one Groq payload — batched per document, not per heading —
so a large doc costs one API call instead of dozens. Failure modes
degrade gracefully, mirroring agents/groq_verifier.py: any error (missing
API key, malformed JSON, API error) falls back to reporting hierarchy
violations as 'warning'-severity issues with no clarity scoring, rather
than failing the pipeline.

get_groq_client() is imported from agents.groq_verifier rather than
reimplemented here — it's a plain API-key/client bootstrap with no
consistency-checker-specific behavior.
"""

import json
import sys
from typing import Dict, List

from pydantic import BaseModel, Field, ValidationError

from agents.documents import HeadingNode, SeoHierarchyIssue, SeoIssue
from agents.groq_verifier import get_groq_client


# ============================================================================
# Severity Rules & Prompt
# ============================================================================

SEVERITY_RULES = """
Severity rules for SEO heading issues:

ERROR: Structural problems that break navigation or hurt SEO significantly
  - Missing H1
  - Multi-level heading skips (e.g. H1 straight to H3)
  - Heading text so vague it gives no information about the section

WARNING: Issues worth fixing but not broken
  - Single-level, isolated hierarchy skips deep in a section
  - Heading clarity clearly below the configured threshold

INFO: Minor or stylistic
  - Borderline clarity scores near the threshold
  - Non-critical depth violations in reference/appendix-style sections
"""

SYSTEM_PROMPT = f"""You are a technical documentation SEO auditor.

Your job: For ONE document, score every heading's clarity and classify
the severity of every flagged hierarchy violation.

{SEVERITY_RULES}

Context: The user will provide, for a single document:
1. Every heading in the document (level, text, line number, parent heading)
2. Hierarchy violations already detected by Python (no severity yet)
3. The clarity_threshold below which a heading should be flagged

For each hierarchy violation, assign a severity and a suggested_fix.
For each heading scoring below clarity_threshold, emit a new issue with
issue_type "low_clarity" and a suggested_fix (a concrete, more specific
rewrite of the heading text). Don't emit an issue for headings that are
already clear and have no violation.

Output ONLY valid JSON. No preamble, no markdown, no code blocks.
"""


# ============================================================================
# Groq Response Models
# ============================================================================


class GroqHeadingIssue(BaseModel):
    """Single SEO issue from Groq (violation severity or clarity flag)."""

    heading_text: str = Field(..., description="Heading text this issue is about")
    line_number: int = Field(..., description="Line number, echoed back from the input")
    issue_type: str = Field(..., description="'hierarchy_violation' or 'low_clarity'")
    severity: str = Field(..., description="Classification: 'error', 'warning', or 'info'")
    reasoning: str = Field(..., description="Why this severity/flag was assigned")
    suggested_fix: str = Field(default="", description="Actionable rewrite or fix")

    class Config:
        strict = True


class GroqSeoVerificationResponse(BaseModel):
    """Response from Groq containing all issues for one document."""

    issues: List[GroqHeadingIssue] = Field(..., description="Issues for this document")

    class Config:
        strict = True


# ============================================================================
# Groq API Integration
# ============================================================================


def build_seo_payload(
    headings: List[HeadingNode],
    hierarchy_issues: List[SeoHierarchyIssue],
    clarity_threshold: int,
) -> str:
    """
    Build the batched user prompt for one document's Groq call.

    Args:
        headings: Every heading in the document
        hierarchy_issues: Violations already detected by Python
        clarity_threshold: Score (0-100) below which a heading is flagged

    Returns:
        Formatted user prompt string
    """
    payload = {
        "clarity_threshold": clarity_threshold,
        "headings": [
            {
                "level": h.level,
                "text": h.text,
                "line_number": h.line_number,
                "parent_heading": h.parent_heading,
            }
            for h in headings
        ],
        "hierarchy_violations": [
            {
                "issue_type": v.issue_type,
                "heading_level": v.heading_level,
                "expected_level": v.expected_level,
                "heading_text": v.heading_text,
                "line_number": v.line_number,
                "reasoning": v.reasoning,
            }
            for v in hierarchy_issues
        ],
    }

    return f"""Document headings and violations:
{json.dumps(payload, indent=2)}

Please verify each hierarchy violation and score every heading's clarity.
Respond with ONLY a JSON object matching this structure:
{{
  "issues": [
    {{
      "heading_text": "Setup",
      "line_number": 12,
      "issue_type": "hierarchy_violation" | "low_clarity",
      "severity": "error" | "warning" | "info",
      "reasoning": "Why this classification",
      "suggested_fix": "Concrete rewrite or fix"
    }}
  ]
}}
"""


def verify_seo_with_groq(
    file_path: str,
    headings: List[HeadingNode],
    hierarchy_issues: List[SeoHierarchyIssue],
    clarity_threshold: int,
) -> List[SeoIssue]:
    """
    Send one document's headings + violations to Groq in a single batched
    call, and return the merged SeoIssue list.

    Args:
        file_path: Relative path to the document (attached to every issue)
        headings: Every heading in the document
        hierarchy_issues: Violations already detected by Python
        clarity_threshold: Score (0-100) below which a heading is flagged

    Returns:
        List of SeoIssue with severity assigned

    Error Handling:
        If Groq API fails (timeout, rate limit, auth, missing key, etc.):
        - Reports all hierarchy_issues as "warning" severity, no clarity scoring
        - Pipeline continues (doesn't fail CI)
    """
    if not headings:
        print(f"[seo-phase-3] {file_path}: no headings, skipping Groq call")
        return []

    print(
        f"[seo-phase-3] Verifying {file_path} ({len(headings)} heading(s), "
        f"{len(hierarchy_issues)} violation(s)) with Groq..."
    )

    # Match Groq's response back to a heading by line number (unique per
    # document), same approach agents/groq_verifier.py uses to re-attach
    # context after verification.
    heading_by_line: Dict[int, HeadingNode] = {h.line_number: h for h in headings}

    try:
        client = get_groq_client()
        user_prompt = build_seo_payload(headings, hierarchy_issues, clarity_threshold)

        print(f"[seo-phase-3]   Calling openai/gpt-oss-120b...")
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,  # Deterministic output
            max_tokens=4096,
        )

        response_text = response.choices[0].message.content.strip()
        print(f"[seo-phase-3]   ✓ Response received")

        try:
            response_json = json.loads(response_text)
            groq_response = GroqSeoVerificationResponse(**response_json)
        except json.JSONDecodeError as e:
            print(
                f"[seo-phase-3] ✗ Failed to parse Groq JSON response: {e}",
                file=sys.stderr,
            )
            return _fallback_to_warnings(file_path, hierarchy_issues, "Groq response malformed")
        except ValidationError as e:
            print(
                f"[seo-phase-3] ✗ Groq response validation failed: {e}",
                file=sys.stderr,
            )
            return _fallback_to_warnings(file_path, hierarchy_issues, "Groq response invalid")

        issues: List[SeoIssue] = []
        for verification in groq_response.issues:
            heading = heading_by_line.get(verification.line_number)
            issues.append(
                SeoIssue(
                    file_path=file_path,
                    line_number=verification.line_number,
                    heading_level=heading.level if heading else 0,
                    heading_text=verification.heading_text,
                    parent_heading=heading.parent_heading if heading else None,
                    issue_type=verification.issue_type,
                    severity=verification.severity,
                    reasoning=verification.reasoning,
                    suggested_fix=verification.suggested_fix,
                )
            )

        print(f"[seo-phase-3] ✓ Verified {len(issues)} issue(s) for {file_path}")
        return issues

    except ValueError as e:
        # Missing API key
        print(f"[seo-phase-3] ✗ {e}", file=sys.stderr)
        print(
            "[seo-phase-3] Falling back to reporting violations as warnings",
            file=sys.stderr,
        )
        return _fallback_to_warnings(file_path, hierarchy_issues, str(e))

    except ImportError as e:
        # groq library not installed
        print(f"[seo-phase-3] ✗ {e}", file=sys.stderr)
        return _fallback_to_warnings(file_path, hierarchy_issues, str(e))

    except Exception as e:
        # Other API errors (timeout, rate limit, etc.)
        print(f"[seo-phase-3] ✗ Groq API error: {e}", file=sys.stderr)
        print(
            "[seo-phase-3] Falling back to reporting violations as warnings",
            file=sys.stderr,
        )
        return _fallback_to_warnings(
            file_path, hierarchy_issues, f"Groq API error: {type(e).__name__}"
        )


def _fallback_to_warnings(
    file_path: str,
    hierarchy_issues: List[SeoHierarchyIssue],
    reason: str,
) -> List[SeoIssue]:
    """
    Fallback: convert hierarchy_issues to warning-level SeoIssues. Clarity
    scoring is skipped entirely since it requires the LLM.

    Used when Groq verification fails (API unavailable, malformed response, etc.).
    """
    print(f"[seo-phase-3] Converting {len(hierarchy_issues)} violation(s) to warnings")
    return [
        SeoIssue(
            file_path=file_path,
            line_number=v.line_number,
            heading_level=v.heading_level,
            heading_text=v.heading_text,
            parent_heading=None,
            issue_type="hierarchy_violation",
            severity="warning",
            reasoning=f"{v.reasoning} (Groq verification unavailable: {reason})",
            suggested_fix="",
        )
        for v in hierarchy_issues
    ]
