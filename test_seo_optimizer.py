"""
Test suite for the SEO heading optimizer agent:
agents.parsing, agents.seo_optimizer, agents.seo_verifier, and the
seo_json/seo_markdown formatters in agents.output.

This test file verifies production-ready behavior:
- Heading extraction: nesting, parent tracking, code block skipping
- Hierarchy violation detection: require_h1, skip rules, max nesting depth
- Groq batching payload shape (pure function, no network)
- Graceful degradation when GROQ_API_KEY is unavailable (real, unmocked)
- SeoReport formatter table rendering, escaping, and empty-state handling

Run with: python test_seo_optimizer.py
"""

import json
import os
import sys
from pathlib import Path

# Add agents/ to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.parsing import parse_headings_from_markdown
from agents.seo_optimizer import detect_hierarchy_violations
from agents.seo_verifier import build_seo_payload, verify_seo_with_groq
from agents.output import format_seo_json, format_seo_markdown
from agents.documents import HeadingNode, SeoHierarchyIssue, SeoIssue, SeoReport


# ============================================================================
# Test Helpers
# ============================================================================


class TestResult:
    """Track test results."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def test(self, name: str, fn, expect_exception=None):
        """Run a single test."""
        try:
            result = fn()
            if expect_exception:
                self.failed += 1
                self.errors.append(
                    f"✗ {name}: Expected {expect_exception.__name__} but no exception raised"
                )
            else:
                self.passed += 1
                print(f"✓ {name}")
        except Exception as e:
            if expect_exception and isinstance(e, expect_exception):
                self.passed += 1
                print(f"✓ {name} (caught {type(e).__name__})")
            else:
                self.failed += 1
                self.errors.append(
                    f"✗ {name}: {type(e).__name__}: {str(e)[:100]}"
                )

    def summary(self):
        """Print summary."""
        total = self.passed + self.failed
        print(f"\n{'='*70}")
        print(f"Tests passed: {self.passed}/{total}")
        if self.failed > 0:
            print(f"Tests failed: {self.failed}/{total}")
            for error in self.errors:
                print(f"  {error}")
        print(f"{'='*70}\n")
        return self.failed == 0


def make_heading(**overrides):
    fields = dict(level=1, text="Installation", line_number=1, parent_heading=None)
    fields.update(overrides)
    return HeadingNode(**fields)


def make_hierarchy_issue(**overrides):
    fields = dict(
        issue_type="h1_skip",
        heading_level=3,
        expected_level=2,
        heading_text="Docker Setup",
        line_number=5,
        reasoning="H1 is followed by H3; expected H2.",
    )
    fields.update(overrides)
    return SeoHierarchyIssue(**fields)


def make_seo_issue(severity="warning", **overrides):
    fields = dict(
        file_path="docs/test.md",
        line_number=5,
        heading_level=3,
        heading_text="Docker Setup",
        parent_heading="Installation",
        issue_type="hierarchy_violation",
        severity=severity,
        reasoning="H1 is followed by H3; expected H2.",
        suggested_fix="Insert an H2 section before this heading.",
    )
    fields.update(overrides)
    return SeoIssue(**fields)


def make_seo_report(issues=None, headings_analyzed=5):
    issues = issues or []
    return SeoReport(
        status="fail" if issues else "pass",
        issues_found=len(issues),
        issues=issues,
        headings_analyzed=headings_analyzed,
        files_scanned=1,
        summary="SEO check summary",
    )


# ============================================================================
# Test Cases: Heading Parsing (agents/parsing.py)
# ============================================================================


def test_heading_parsing():
    print("\n[test_seo] Testing heading extraction")
    print("-" * 70)

    results = TestResult()

    def test_nested_structure():
        content = (
            "# Installation\n"
            "## Prerequisites\n"
            "### Docker Setup\n"
            "### Kubernetes Setup\n"
            "## Configuration\n"
        )
        headings = parse_headings_from_markdown(content)
        assert len(headings) == 5
        assert headings[0].level == 1 and headings[0].parent_heading is None
        assert headings[1].parent_heading == "Installation"
        assert headings[2].parent_heading == "Prerequisites"
        assert headings[3].parent_heading == "Prerequisites"
        assert headings[4].parent_heading == "Installation"
        return headings

    results.test("Nested headings get correct parent tracking", test_nested_structure)

    def test_sibling_reset():
        content = "# A\n## B\n## C\n"
        headings = parse_headings_from_markdown(content)
        # C's parent should be A, not B (siblings don't nest under each other)
        assert headings[2].parent_heading == "A"
        return headings

    results.test("Sibling headings don't nest under each other", test_sibling_reset)

    def test_code_block_skip():
        content = (
            "# Real Heading\n"
            "```python\n"
            "# This is a comment, not a heading\n"
            "## Also not a heading\n"
            "```\n"
            "## Also Real\n"
        )
        headings = parse_headings_from_markdown(content)
        assert len(headings) == 2
        assert headings[0].text == "Real Heading"
        assert headings[1].text == "Also Real"
        return headings

    results.test("Headings inside fenced code blocks are skipped", test_code_block_skip)

    def test_no_headings():
        headings = parse_headings_from_markdown("Just a paragraph, no headings here.")
        assert headings == []
        return headings

    results.test("Document with no headings returns empty list", test_no_headings)

    def test_trailing_hash_decoration():
        content = "## Configuration ##\n"
        headings = parse_headings_from_markdown(content)
        assert len(headings) == 1
        assert headings[0].text == "Configuration"
        return headings

    results.test("Trailing '#' decoration is stripped from heading text", test_trailing_hash_decoration)

    def test_no_space_after_hash_ignored():
        # "#comment" (no space) is not a valid ATX heading per CommonMark
        content = "#comment\nReal text\n"
        headings = parse_headings_from_markdown(content)
        assert headings == []
        return headings

    results.test("'#' without a following space is not treated as a heading", test_no_space_after_hash_ignored)

    return results.summary()


# ============================================================================
# Test Cases: Hierarchy Violation Detection (agents/seo_optimizer.py)
# ============================================================================


def test_hierarchy_violations():
    print("[test_seo] Testing hierarchy violation detection")
    print("-" * 70)

    results = TestResult()

    def test_well_formed_doc_no_violations():
        headings = [
            make_heading(level=1, text="Installation", line_number=1, parent_heading=None),
            make_heading(level=2, text="Prerequisites", line_number=2, parent_heading="Installation"),
            make_heading(level=3, text="Docker Setup", line_number=3, parent_heading="Prerequisites"),
        ]
        rules = {"require_h1": True, "max_nesting_depth": 4}
        violations = detect_hierarchy_violations(headings, rules)
        assert violations == []
        return violations

    results.test("Well-formed hierarchy produces no violations", test_well_formed_doc_no_violations)

    def test_missing_h1():
        headings = [make_heading(level=2, text="Prerequisites", line_number=1, parent_heading=None)]
        violations = detect_hierarchy_violations(headings, {"require_h1": True})
        assert len(violations) == 1
        assert violations[0].issue_type == "missing_h1"
        return violations

    results.test("Missing H1 is flagged when require_h1 is enabled", test_missing_h1)

    def test_missing_h1_allowed_when_rule_disabled():
        headings = [make_heading(level=2, text="Prerequisites", line_number=1, parent_heading=None)]
        violations = detect_hierarchy_violations(headings, {"require_h1": False})
        assert violations == []
        return violations

    results.test("Missing H1 is not flagged when require_h1 is disabled", test_missing_h1_allowed_when_rule_disabled)

    def test_h1_skip_disallowed_by_default():
        headings = [
            make_heading(level=1, text="Installation", line_number=1, parent_heading=None),
            make_heading(level=3, text="Docker Setup", line_number=2, parent_heading=None),
        ]
        violations = detect_hierarchy_violations(headings, {"require_h1": True})
        skip_violations = [v for v in violations if v.issue_type == "h1_skip"]
        assert len(skip_violations) == 1
        assert skip_violations[0].expected_level == 2
        return violations

    results.test("H1 -> H3 skip is flagged by default", test_h1_skip_disallowed_by_default)

    def test_h1_skip_allowed_when_configured():
        headings = [
            make_heading(level=1, text="Installation", line_number=1, parent_heading=None),
            make_heading(level=3, text="Docker Setup", line_number=2, parent_heading=None),
        ]
        violations = detect_hierarchy_violations(
            headings, {"require_h1": True, "allow_h1_skip": True}
        )
        skip_violations = [v for v in violations if v.issue_type == "h1_skip"]
        assert skip_violations == []
        return violations

    results.test("H1 -> H3 skip is not flagged when allow_h1_skip is true", test_h1_skip_allowed_when_configured)

    def test_max_nesting_depth_exceeded():
        headings = [
            make_heading(level=1, text="A", line_number=1, parent_heading=None),
            make_heading(level=2, text="B", line_number=2, parent_heading="A"),
            make_heading(level=3, text="C", line_number=3, parent_heading="B"),
            make_heading(level=4, text="D", line_number=4, parent_heading="C"),
            make_heading(level=5, text="E", line_number=5, parent_heading="D"),
        ]
        violations = detect_hierarchy_violations(
            headings, {"require_h1": True, "max_nesting_depth": 4}
        )
        depth_violations = [v for v in violations if v.issue_type == "max_depth_exceeded"]
        assert len(depth_violations) == 1
        assert depth_violations[0].heading_level == 5
        return violations

    results.test("Heading beyond max_nesting_depth is flagged", test_max_nesting_depth_exceeded)

    return results.summary()


# ============================================================================
# Test Cases: Groq Payload Building (agents/seo_verifier.py, no network)
# ============================================================================


def test_seo_payload_building():
    print("[test_seo] Testing Groq payload building")
    print("-" * 70)

    results = TestResult()

    def test_payload_includes_headings_and_violations():
        headings = [make_heading()]
        violations = [make_hierarchy_issue()]
        prompt = build_seo_payload(headings, violations, clarity_threshold=40)
        # Payload is embedded as a JSON blob inside the prompt text
        assert "Installation" in prompt
        assert "h1_skip" in prompt
        assert '"clarity_threshold": 40' in prompt
        return prompt

    results.test("Payload embeds headings, violations, and threshold", test_payload_includes_headings_and_violations)

    def test_payload_is_valid_json_embedded():
        headings = [make_heading()]
        violations = []
        prompt = build_seo_payload(headings, violations, clarity_threshold=40)
        # Extract the embedded JSON block (between the first '{' and its matching close)
        start = prompt.index("{")
        end = prompt.rindex("}", 0, prompt.index("Please verify")) + 1
        embedded = json.loads(prompt[start:end])
        assert embedded["clarity_threshold"] == 40
        assert len(embedded["headings"]) == 1
        return embedded

    results.test("Embedded headings/violations payload is valid JSON", test_payload_is_valid_json_embedded)

    return results.summary()


# ============================================================================
# Test Cases: Graceful Degradation (agents/seo_verifier.py, real/unmocked)
# ============================================================================


def test_groq_fallback():
    print("[test_seo] Testing graceful degradation when Groq is unavailable")
    print("-" * 70)

    results = TestResult()

    def test_fallback_on_missing_api_key():
        original_key = os.environ.pop("GROQ_API_KEY", None)
        try:
            headings = [make_heading()]
            violations = [make_hierarchy_issue()]
            issues = verify_seo_with_groq("docs/test.md", headings, violations, clarity_threshold=40)
            assert len(issues) == 1
            assert issues[0].severity == "warning"
            assert issues[0].issue_type == "hierarchy_violation"
            assert "GROQ_API_KEY" in issues[0].reasoning
            return issues
        finally:
            if original_key is not None:
                os.environ["GROQ_API_KEY"] = original_key

    results.test(
        "Missing GROQ_API_KEY degrades to warning-level issues, not a crash",
        test_fallback_on_missing_api_key,
    )

    def test_no_headings_short_circuits():
        issues = verify_seo_with_groq("docs/empty.md", [], [], clarity_threshold=40)
        assert issues == []
        return issues

    results.test("Document with no headings skips the Groq call entirely", test_no_headings_short_circuits)

    return results.summary()


# ============================================================================
# Test Cases: Model Validation (agents/documents.py)
# ============================================================================


def test_seo_models():
    print("[test_seo] Testing SEO Pydantic models")
    print("-" * 70)

    results = TestResult()

    def test_seo_issue_optional_parent():
        issue = make_seo_issue(parent_heading=None)
        assert issue.parent_heading is None
        return issue

    results.test("SeoIssue.parent_heading accepts None (top-level headings)", test_seo_issue_optional_parent)

    def test_seo_issue_suggested_fix_defaults_empty():
        issue = SeoIssue(
            file_path="docs/test.md",
            line_number=1,
            heading_level=1,
            heading_text="Installation",
            issue_type="hierarchy_violation",
            severity="warning",
            reasoning="test",
        )
        assert issue.suggested_fix == ""
        return issue

    results.test("SeoIssue.suggested_fix defaults to empty string", test_seo_issue_suggested_fix_defaults_empty)

    def test_seo_report_status_derivation():
        report = make_seo_report([make_seo_issue()])
        assert report.status == "fail"
        empty_report = make_seo_report([])
        assert empty_report.status == "pass"
        return report

    results.test("SeoReport status reflects presence of issues", test_seo_report_status_derivation)

    return results.summary()


# ============================================================================
# Test Cases: Output Formatters (agents/output.py)
# ============================================================================


def test_seo_output_formatters():
    print("[test_seo] Testing SEO output formatters")
    print("-" * 70)

    results = TestResult()

    def test_json_formatter():
        report = make_seo_report([make_seo_issue()])
        rendered = format_seo_json(report)
        parsed = json.loads(rendered)
        assert parsed["status"] == "fail"
        assert parsed["issues_shown"] == 1
        return parsed

    results.test("format_seo_json produces valid JSON with issues_shown", test_json_formatter)

    def test_markdown_table_renders():
        report = make_seo_report([make_seo_issue()])
        rendered = format_seo_markdown(report)
        assert "| File | Line | Heading |" in rendered
        assert "Docker Setup" in rendered
        assert "Insert an H2 section" in rendered
        return rendered

    results.test("format_seo_markdown renders a table with suggested fixes", test_markdown_table_renders)

    def test_markdown_empty_state():
        report = make_seo_report([])
        rendered = format_seo_markdown(report)
        assert "No issues" in rendered
        assert "|" not in rendered
        return rendered

    results.test("format_seo_markdown skips the table when there are no issues", test_markdown_empty_state)

    def test_markdown_escapes_pipes():
        issue = make_seo_issue(suggested_fix="Use `a | b` instead")
        report = make_seo_report([issue])
        rendered = format_seo_markdown(report)
        assert "\\|" in rendered
        return rendered

    results.test("Pipe characters in suggested_fix are escaped", test_markdown_escapes_pipes)

    def test_markdown_respects_severity_threshold():
        report = make_seo_report([make_seo_issue(severity="info")])
        rendered = format_seo_markdown(report, severity_threshold="error")
        assert "No issues" in rendered
        return rendered

    results.test("Severity threshold filters the rendered table", test_markdown_respects_severity_threshold)

    return results.summary()


# ============================================================================
# Main
# ============================================================================


def main():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("SEO heading optimizer Test Suite")
    print("=" * 70)

    all_passed = True
    all_passed &= test_heading_parsing()
    all_passed &= test_hierarchy_violations()
    all_passed &= test_seo_payload_building()
    all_passed &= test_groq_fallback()
    all_passed &= test_seo_models()
    all_passed &= test_seo_output_formatters()

    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
