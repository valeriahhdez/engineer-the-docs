"""
Test suite for agents.output module.

This test file verifies production-ready behavior:
- JSON formatter: valid JSON, correct metadata, severity filtering
- Markdown formatter: table rendering, empty-issues case, cell escaping
- format_report: default formatter set, explicit subset, unknown formatter error

Run with: python test_output.py
"""

import json
import sys
from pathlib import Path

# Add agents/ to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.output import (
    format_json,
    format_markdown,
    format_report,
    filter_by_severity,
)
from agents.documents import ConsistencyIssue, ConsistencyReport


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


def make_issue(severity="warning", **overrides):
    fields = dict(
        file_path="docs/test.md",
        line_number=3,
        canonical_term="GitHub",
        found_variant="github",
        context_snippet="...we use github here...",
        severity=severity,
        reasoning="Case mismatch in prose",
        match_type="case_mismatch",
    )
    fields.update(overrides)
    return ConsistencyIssue(**fields)


def make_report(issues=None, status=None):
    issues = issues or []
    return ConsistencyReport(
        status=status or ("fail" if issues else "pass"),
        issues_found=len(issues),
        issues=issues,
        glossary_terms_checked=8,
        files_scanned=2,
        summary="Consistency check summary",
    )


# ============================================================================
# Test Cases: Severity Filtering
# ============================================================================


def test_severity_filtering():
    print("\n[test_output] Testing severity filtering")
    print("-" * 70)

    results = TestResult()

    def test_filter_keeps_at_or_above():
        issues = [make_issue("info"), make_issue("warning"), make_issue("error")]
        filtered = filter_by_severity(issues, "warning")
        assert len(filtered) == 2
        assert all(i.severity in ("warning", "error") for i in filtered)
        return filtered

    results.test("Filter keeps issues at or above threshold", test_filter_keeps_at_or_above)

    def test_filter_info_keeps_all():
        issues = [make_issue("info"), make_issue("warning"), make_issue("error")]
        filtered = filter_by_severity(issues, "info")
        assert len(filtered) == 3
        return filtered

    results.test("'info' threshold keeps everything", test_filter_info_keeps_all)

    def test_filter_error_keeps_only_error():
        issues = [make_issue("info"), make_issue("warning"), make_issue("error")]
        filtered = filter_by_severity(issues, "error")
        assert len(filtered) == 1
        assert filtered[0].severity == "error"
        return filtered

    results.test("'error' threshold keeps only errors", test_filter_error_keeps_only_error)

    return results.summary()


# ============================================================================
# Test Cases: JSON Formatter
# ============================================================================


def test_json_formatter():
    print("[test_output] Testing JSON formatter")
    print("-" * 70)

    results = TestResult()

    def test_valid_json():
        report = make_report([make_issue("warning")])
        rendered = format_json(report)
        parsed = json.loads(rendered)
        assert parsed["status"] == "fail"
        assert parsed["issues_found"] == 1
        assert parsed["issues_shown"] == 1
        return parsed

    results.test("Produces valid, well-formed JSON", test_valid_json)

    def test_json_severity_filter():
        report = make_report([make_issue("info"), make_issue("error")])
        rendered = format_json(report, severity_threshold="error")
        parsed = json.loads(rendered)
        # issues_found reflects the full report; issues_shown reflects the filter
        assert parsed["issues_found"] == 2
        assert parsed["issues_shown"] == 1
        assert len(parsed["issues"]) == 1
        return parsed

    results.test("issues_found stays unfiltered; issues/issues_shown respect threshold", test_json_severity_filter)

    def test_json_empty_report():
        report = make_report([])
        rendered = format_json(report)
        parsed = json.loads(rendered)
        assert parsed["status"] == "pass"
        assert parsed["issues"] == []
        return parsed

    results.test("Empty report renders cleanly", test_json_empty_report)

    return results.summary()


# ============================================================================
# Test Cases: Markdown Formatter
# ============================================================================


def test_markdown_formatter():
    print("[test_output] Testing Markdown formatter")
    print("-" * 70)

    results = TestResult()

    def test_markdown_table_renders():
        report = make_report([make_issue("warning")])
        rendered = format_markdown(report)
        assert "| File | Line |" in rendered
        assert "docs/test.md" in rendered
        assert "github" in rendered
        return rendered

    results.test("Issues table renders with issue data", test_markdown_table_renders)

    def test_markdown_empty_report():
        report = make_report([])
        rendered = format_markdown(report)
        assert "No issues" in rendered
        assert "|" not in rendered  # No table when there's nothing to show
        return rendered

    results.test("Empty report skips the table", test_markdown_empty_report)

    def test_markdown_escapes_pipes():
        issue = make_issue(reasoning="Found `a | b` in a code sample")
        report = make_report([issue])
        rendered = format_markdown(report)
        assert "\\|" in rendered
        return rendered

    results.test("Pipe characters in cell text are escaped", test_markdown_escapes_pipes)

    def test_markdown_respects_threshold():
        report = make_report([make_issue("info")])
        rendered = format_markdown(report, severity_threshold="error")
        assert "No issues" in rendered
        return rendered

    results.test("Markdown table omits issues below threshold", test_markdown_respects_threshold)

    return results.summary()


# ============================================================================
# Test Cases: format_report dispatch
# ============================================================================


def test_format_report_dispatch():
    print("[test_output] Testing format_report dispatch")
    print("-" * 70)

    results = TestResult()

    def test_explicit_formats_list():
        report = make_report([make_issue("warning")])
        rendered = format_report(report, formats=["json", "markdown"])
        assert set(rendered.keys()) == {"json", "markdown"}
        return rendered

    results.test(
        "Renders exactly the requested formats (formats is required, no implicit 'all')",
        test_explicit_formats_list,
    )

    def test_formats_required():
        report = make_report([])
        format_report(report)

    results.test(
        "Omitting formats raises (registry is shared across report types; no safe default)",
        test_formats_required,
        expect_exception=TypeError,
    )

    def test_explicit_subset():
        report = make_report([make_issue("warning")])
        rendered = format_report(report, formats=["markdown"])
        assert set(rendered.keys()) == {"markdown"}
        return rendered

    results.test("Explicit formats subset is respected", test_explicit_subset)

    def test_unknown_formatter():
        report = make_report([])
        format_report(report, formats=["xml"])

    results.test("Unknown formatter raises ValueError", test_unknown_formatter, expect_exception=ValueError)

    return results.summary()


# ============================================================================
# Main
# ============================================================================


def main():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("agents.output Test Suite")
    print("=" * 70)

    all_passed = True
    all_passed &= test_severity_filtering()
    all_passed &= test_json_formatter()
    all_passed &= test_markdown_formatter()
    all_passed &= test_format_report_dispatch()

    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
