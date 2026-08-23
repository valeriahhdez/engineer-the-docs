"""
Phase 2 (SEO): Detect heading hierarchy violations using Python + config rules.

This module implements the deterministic pre-scan for the SEO heading
optimizer: given a document's headings (from agents.parsing) and the
hierarchy_rules from agents.yaml, flag structural violations. It does not
judge clarity or assign severity — that's Groq's job (agents/seo_verifier.py).

Design principles (mirrors agents/candidate_finder.py):
- Deterministic: exact line numbers, no LLM guessing
- Transparent: classify violation type for understanding
- Pragmatic: let Groq decide severity (we just flag)
"""

from typing import Dict, List

from agents.documents import HeadingNode, SeoHierarchyIssue


def detect_hierarchy_violations(
    headings: List[HeadingNode],
    hierarchy_rules: Dict,
) -> List[SeoHierarchyIssue]:
    """
    Detect heading hierarchy violations for a single document.

    Args:
        headings: Headings for one document, in document order (from
            agents.parsing.parse_headings_from_markdown)
        hierarchy_rules: From agents.yaml's
            agents.seo_optimizer.config.hierarchy_rules, e.g.:
            {
                "require_h1": True,
                "allow_h1_skip": False,
                "allow_h2_skip": False,
                "max_nesting_depth": 4,
            }
            A level's skip is permitted via "allow_h{level}_skip"; any
            level not listed defaults to disallowed — opt-in, like every
            other discovery rule in this project.

    Returns:
        List of SeoHierarchyIssue, in document order. Severity is not
        assigned here.
    """
    violations: List[SeoHierarchyIssue] = []

    require_h1 = hierarchy_rules.get("require_h1", True)
    max_nesting_depth = hierarchy_rules.get("max_nesting_depth", 6)

    if require_h1 and not any(h.level == 1 for h in headings):
        violations.append(
            SeoHierarchyIssue(
                issue_type="missing_h1",
                heading_level=1,
                expected_level=1,
                heading_text="(missing)",
                line_number=headings[0].line_number if headings else 1,
                reasoning=(
                    "Document has no H1 heading, but hierarchy_rules.require_h1 "
                    "is enabled."
                ),
            )
        )

    previous_level = 0
    for heading in headings:
        if heading.level > max_nesting_depth:
            violations.append(
                SeoHierarchyIssue(
                    issue_type="max_depth_exceeded",
                    heading_level=heading.level,
                    expected_level=max_nesting_depth,
                    heading_text=heading.text,
                    line_number=heading.line_number,
                    reasoning=(
                        f"H{heading.level} exceeds the configured "
                        f"max_nesting_depth of {max_nesting_depth}."
                    ),
                )
            )

        if previous_level and heading.level > previous_level + 1:
            allow_key = f"allow_h{previous_level}_skip"
            if not hierarchy_rules.get(allow_key, False):
                violations.append(
                    SeoHierarchyIssue(
                        issue_type=f"h{previous_level}_skip",
                        heading_level=heading.level,
                        expected_level=previous_level + 1,
                        heading_text=heading.text,
                        line_number=heading.line_number,
                        reasoning=(
                            f"H{previous_level} is followed by H{heading.level}; "
                            f"expected H{previous_level + 1}."
                        ),
                    )
                )

        previous_level = heading.level

    return violations
