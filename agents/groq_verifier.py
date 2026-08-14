"""
Phase 3: Groq API integration for LLM-based candidate verification.

This module implements semantic validation of term candidates:
1. Send candidates to Groq (llama-3.3-70b-versatile)
2. Classify severity (error, warning, info) based on context
3. Provide reasoning for each classification
4. Handle API failures gracefully (Option A: report as warnings)

Design principles:
- Structured JSON output (Pydantic validation)
- Semantic judgment (LLM determines if violation matters)
- Graceful degradation (API failure doesn't break pipeline)
- Clear reasoning (why is this an error vs warning)
"""

import json
import os
import sys
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from agents.documents import Candidate, ConsistencyIssue


# ============================================================================
# Severity Rules & Constants
# ============================================================================

SEVERITY_RULES = """
Severity rules for terminology consistency violations:

ERROR: Critical inconsistencies that should always be fixed
  - Misspelled or wrong term (e.g., "kuber-netes" vs "Kubernetes")
  - Incorrect technical concept (wrong term used for wrong idea)
  - Critical inconsistency within same document (term used two different ways)

WARNING: Important style issues in prose (not code)
  - Case mismatch in prose (e.g., "github" vs "GitHub")
  - Abbreviation violation (e.g., "JS" vs "JavaScript" when full form is canonical)
  - Format inconsistency (e.g., "REST-API" vs "REST API")

INFO: Acceptable stylistic variations or intentional choices
  - Title case in headings (e.g., "Docs-as-Code" in ## heading when canonical is "docs-as-code")
  - Acceptable variant of hyphenation (e.g., "front-end" vs "frontend")
  - Legacy terminology that's still correct but outdated
  - Inside code examples where variants are intentional
"""

SYSTEM_PROMPT = f"""You are a technical documentation consistency auditor.

Your job: Evaluate flagged terminology issues and classify their severity.

{SEVERITY_RULES}

Context: The user will provide:
1. A glossary of canonical terms
2. Specific candidates (flagged inconsistencies with line numbers and context)

For each candidate, you will:
1. Evaluate the context
2. Classify as: error, warning, or info
3. Explain your reasoning briefly

Output ONLY valid JSON. No preamble, no markdown, no code blocks.
"""


# ============================================================================
# Groq Response Models
# ============================================================================

class GroqVerification(BaseModel):
    """Single verification result from Groq."""

    file_path: str = Field(..., description="File path from candidate")
    line_number: int = Field(..., description="Line number from candidate")
    canonical_term: str = Field(..., description="Canonical term from glossary")
    found_variant: str = Field(..., description="Variant found in document")
    severity: str = Field(
        ...,
        description="Classification: 'error', 'warning', or 'info'"
    )
    reasoning: str = Field(
        ...,
        description="Why this severity was assigned"
    )

    class Config:
        strict = True


class GroqVerificationResponse(BaseModel):
    """Response from Groq containing multiple verifications."""

    verifications: List[GroqVerification] = Field(
        ...,
        description="List of verified candidates"
    )

    class Config:
        strict = True


# ============================================================================
# Groq API Integration
# ============================================================================


def get_groq_client():
    """
    Get Groq client with API key from environment.

    Returns:
        Groq client instance

    Raises:
        ValueError: If GROQ_API_KEY environment variable is not set
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set. "
            "Please set it before running the consistency checker."
        )

    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except ImportError:
        raise ImportError(
            "groq library not installed. Run: pip install groq"
        )


def build_groq_payload(
    candidates: List[Candidate],
    glossary: Dict[str, str]
) -> str:
    """
    Build the user prompt for Groq.

    Args:
        candidates: List of Candidate objects to verify
        glossary: Canonical glossary dictionary

    Returns:
        Formatted user prompt string
    """
    # Format glossary
    glossary_str = "Canonical Glossary:\n"
    for term, definition in sorted(glossary.items()):
        glossary_str += f"  - {term}: {definition}\n"

    # Format candidates
    candidates_str = "Candidates to Verify:\n"
    for i, candidate in enumerate(candidates, 1):
        candidates_str += f"""
{i}. File: {candidate.file_path}, Line {candidate.line_number}
   Canonical: "{candidate.canonical_term}"
   Found: "{candidate.found_variant}"
   Context: {candidate.context_snippet}
   Match Type: {candidate.match_type}
"""

    prompt = f"""{glossary_str}

{candidates_str}

Please verify each candidate. Respond with ONLY a JSON object matching this structure:
{{
  "verifications": [
    {{
      "file_path": "path/to/file.md",
      "line_number": 42,
      "canonical_term": "term",
      "found_variant": "variant",
      "severity": "error|warning|info",
      "reasoning": "Why this classification"
    }}
  ]
}}
"""
    return prompt


def verify_with_groq(
    candidates: List[Candidate],
    glossary: Dict[str, str],
) -> List[ConsistencyIssue]:
    """
    Send candidates to Groq for semantic verification and severity classification.

    This function:
    1. Builds a prompt with candidates + glossary
    2. Calls llama-3.3-70b-versatile for structured JSON output
    3. Parses response into ConsistencyIssue objects
    4. Handles API failures gracefully (reports as warnings)

    Args:
        candidates: List of Candidate objects from Phase 2
        glossary: Canonical terminology dictionary

    Returns:
        List of ConsistencyIssue objects with severity assigned

    Error Handling:
        If Groq API fails (timeout, rate limit, auth, etc.):
        - Reports all candidates as "warning" severity
        - Adds note about Groq verification unavailable
        - Pipeline continues (doesn't fail CI)
    """
    if not candidates:
        print("[phase-3] No candidates to verify")
        return []

    print(f"[phase-3] Verifying {len(candidates)} candidate(s) with Groq...")

    try:
        # Get Groq client
        client = get_groq_client()

        # Build payload
        user_prompt = build_groq_payload(candidates, glossary)

        # Call Groq API
        print(f"[phase-3]   Calling llama-3.3-70b-versatile...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0,  # Deterministic output
            max_tokens=2048,
        )

        # Extract response text
        response_text = response.choices[0].message.content.strip()
        print(f"[phase-3]   ✓ Response received")

        # Parse JSON response
        try:
            response_json = json.loads(response_text)
            groq_response = GroqVerificationResponse(**response_json)
        except json.JSONDecodeError as e:
            print(
                f"[phase-3] ✗ Failed to parse Groq JSON response: {e}",
                file=sys.stderr,
            )
            # Fallback: report all candidates as warnings
            return _fallback_to_warnings(candidates, "Groq response malformed")

        except ValidationError as e:
            print(
                f"[phase-3] ✗ Groq response validation failed: {e}",
                file=sys.stderr,
            )
            # Fallback: report all candidates as warnings
            return _fallback_to_warnings(candidates, "Groq response invalid")

        # Convert Groq verifications to ConsistencyIssue objects
        issues = []
        for verification in groq_response.verifications:
            issue = ConsistencyIssue(
                file_path=verification.file_path,
                line_number=verification.line_number,
                canonical_term=verification.canonical_term,
                found_variant=verification.found_variant,
                context_snippet=next(
                    (c.context_snippet for c in candidates
                     if c.file_path == verification.file_path
                     and c.line_number == verification.line_number),
                    ""
                ),
                severity=verification.severity,
                reasoning=verification.reasoning,
                match_type=next(
                    (c.match_type for c in candidates
                     if c.file_path == verification.file_path
                     and c.line_number == verification.line_number),
                    "unknown"
                ),
            )
            issues.append(issue)

        print(f"[phase-3] ✓ Verified {len(issues)} issue(s)")
        return issues

    except ValueError as e:
        # Missing API key
        print(f"[phase-3] ✗ {e}", file=sys.stderr)
        print(
            "[phase-3] Falling back to reporting all candidates as warnings",
            file=sys.stderr,
        )
        return _fallback_to_warnings(candidates, str(e))

    except ImportError as e:
        # groq library not installed
        print(f"[phase-3] ✗ {e}", file=sys.stderr)
        return _fallback_to_warnings(candidates, str(e))

    except Exception as e:
        # Other API errors (timeout, rate limit, etc.)
        print(f"[phase-3] ✗ Groq API error: {e}", file=sys.stderr)
        print(
            "[phase-3] Falling back to reporting all candidates as warnings",
            file=sys.stderr,
        )
        return _fallback_to_warnings(
            candidates, f"Groq API error: {type(e).__name__}"
        )


def _fallback_to_warnings(
    candidates: List[Candidate], reason: str
) -> List[ConsistencyIssue]:
    """
    Fallback: Convert all candidates to warning-level issues.

    Used when Groq verification fails (API unavailable, malformed response, etc.).

    Args:
        candidates: Candidates to convert
        reason: Reason for fallback

    Returns:
        List of ConsistencyIssue objects with severity="warning"
    """
    print(f"[phase-3] Converting {len(candidates)} candidates to warnings")
    issues = []
    for candidate in candidates:
        issue = ConsistencyIssue(
            file_path=candidate.file_path,
            line_number=candidate.line_number,
            canonical_term=candidate.canonical_term,
            found_variant=candidate.found_variant,
            context_snippet=candidate.context_snippet,
            severity="warning",
            reasoning=f"Python detected variant (Groq verification unavailable: {reason})",
            match_type=candidate.match_type,
        )
        issues.append(issue)

    return issues
