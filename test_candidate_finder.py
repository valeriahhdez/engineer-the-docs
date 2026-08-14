"""
Test suite for agents.candidate_finder module.

This test file verifies production-ready behavior:
- Case-insensitive term matching
- Match type classification (case, punctuation, abbreviation)
- Code block detection and skipping
- Context extraction
- Real document scanning
- Integration with real glossary

Run with: python test_candidate_finder.py
"""

import sys
from pathlib import Path

# Add agents/ to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.candidate_finder import (
    find_term_candidates,
    find_term_in_line,
    classify_match_type,
    is_in_code_block,
    extract_context,
    summarize_candidates,
)
from agents.documents import DocumentInput, Candidate


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


# ============================================================================
# Test Cases: Match Type Classification
# ============================================================================


def test_match_type_classification():
    """Test classification of different mismatch types."""
    print("\n[test_candidate] Testing match type classification")
    print("-" * 70)

    results = TestResult()

    # Test 1: Case mismatch
    def test_case_mismatch():
        result = classify_match_type("GitHub", "github")
        assert result == "case_mismatch", f"Expected case_mismatch, got {result}"
        return result

    results.test("Case mismatch detection (GitHub vs github)", test_case_mismatch)

    # Test 2: Punctuation variant
    def test_punctuation_variant():
        result = classify_match_type("REST API", "REST-API")
        assert result == "punctuation_variant", f"Expected punctuation_variant, got {result}"
        return result

    results.test("Punctuation variant detection (REST API vs REST-API)", test_punctuation_variant)

    # Test 3: Abbreviation
    def test_abbreviation():
        result = classify_match_type("pull request", "pr")
        assert result == "abbreviation", f"Expected abbreviation, got {result}"
        return result

    results.test("Abbreviation detection (pull request vs pr)", test_abbreviation)

    # Test 4: Multiple case and punctuation
    def test_complex_variant():
        result = classify_match_type("CI/CD", "cicd")
        assert result in ["punctuation_variant", "unknown"], f"Got {result}"
        return result

    results.test("Complex variant (CI/CD vs cicd)", test_complex_variant)

    return results.summary()


# ============================================================================
# Test Cases: Context Extraction
# ============================================================================


def test_context_extraction():
    """Test context snippet generation."""
    print("[test_candidate] Testing context extraction")
    print("-" * 70)

    results = TestResult()

    # Test 1: Context with surrounding text
    def test_context_middle():
        text = "This is a GitHub repository example"
        context = extract_context(text, 10, 16, window=10)  # "GitHub"
        assert "GitHub" in context
        assert "..." not in context  # No truncation needed
        return context

    results.test("Context extracted for term in middle", test_context_middle)

    # Test 2: Context at start
    def test_context_start():
        text = "GitHub is great"
        context = extract_context(text, 0, 6, window=10)
        assert "GitHub" in context
        assert context.startswith("GitHub") or context.startswith("...")
        return context

    results.test("Context extracted for term at start", test_context_start)

    # Test 3: Context with ellipsis
    def test_context_ellipsis():
        text = "a" * 100 + "GitHub" + "b" * 100
        context = extract_context(text, 100, 106, window=20)
        assert "..." in context  # Should have ellipsis
        assert "GitHub" in context
        return context

    results.test("Ellipsis added for truncated context", test_context_ellipsis)

    return results.summary()


# ============================================================================
# Test Cases: Code Block Detection
# ============================================================================


def test_code_block_detection():
    """Test detection of lines inside code blocks."""
    print("[test_candidate] Testing code block detection")
    print("-" * 70)

    results = TestResult()

    # Test 1: Outside code block
    def test_outside_block():
        lines = ["# Title", "Some text", "More text"]
        result = is_in_code_block(lines, 2)  # Line 2
        assert result is False
        return result

    results.test("Line outside code block returns False", test_outside_block)

    # Test 2: Inside code block
    def test_inside_block():
        lines = [
            "Some text",
            "```python",
            "def function():",
            "    pass",
            "```",
            "More text",
        ]
        result = is_in_code_block(lines, 3)  # Line 3 (inside block)
        assert result is True
        return result

    results.test("Line inside code block returns True", test_inside_block)

    # Test 3: Line after block
    def test_after_block():
        lines = [
            "Text",
            "```",
            "code",
            "```",
            "After block",
        ]
        result = is_in_code_block(lines, 5)  # Line 5 (after closing ```)
        assert result is False
        return result

    results.test("Line after code block returns False", test_after_block)

    # Test 4: Multiple blocks
    def test_multiple_blocks():
        lines = [
            "Text",
            "```",
            "block1",
            "```",
            "Between",
            "```",
            "block2",
            "```",
            "After",
        ]
        assert is_in_code_block(lines, 3) is True   # In first block
        assert is_in_code_block(lines, 4) is False  # After first block
        assert is_in_code_block(lines, 7) is True   # In second block
        return True

    results.test("Multiple code blocks detected correctly", test_multiple_blocks)

    return results.summary()


# ============================================================================
# Test Cases: Find Term in Line
# ============================================================================


def test_find_term_in_line():
    """Test finding term variants in a single line."""
    print("[test_candidate] Testing term finding in line")
    print("-" * 70)

    results = TestResult()

    # Test 1: Case-insensitive matching
    def test_case_insensitive():
        candidates = find_term_in_line(
            "We use github for version control",
            "GitHub",
            line_number=1,
            file_path="docs/test.md"
        )
        assert len(candidates) == 1
        assert candidates[0].found_variant == "github"
        assert candidates[0].match_type == "case_mismatch"
        return candidates

    results.test("Case-insensitive term matching", test_case_insensitive)

    # Test 2: No match
    def test_no_match():
        candidates = find_term_in_line(
            "We use version control",
            "GitHub",
            line_number=1,
            file_path="docs/test.md"
        )
        assert len(candidates) == 0
        return candidates

    results.test("No match returns empty list", test_no_match)

    # Test 3: Multiple matches in line
    def test_multiple_matches():
        candidates = find_term_in_line(
            "github and GITHUB and GitHub",
            "GitHub",
            line_number=1,
            file_path="docs/test.md"
        )
        # Should find 2 (lowercase and uppercase, but not exact match)
        assert len(candidates) == 2
        return candidates

    results.test("Multiple matches found in same line", test_multiple_matches)

    # Test 4: Exact match skipped
    def test_exact_match_skipped():
        candidates = find_term_in_line(
            "GitHub is our version control",
            "GitHub",
            line_number=1,
            file_path="docs/test.md"
        )
        # Exact match should be skipped
        assert len(candidates) == 0
        return candidates

    results.test("Exact matches are skipped", test_exact_match_skipped)

    # Test 5: Multi-word term
    def test_multi_word_term():
        candidates = find_term_in_line(
            "We use REST API for endpoints",
            "REST API",
            line_number=1,
            file_path="docs/test.md"
        )
        # Exact match, should be skipped
        assert len(candidates) == 0
        return candidates

    results.test("Multi-word terms handled correctly", test_multi_word_term)

    # Test 6: Variant of multi-word term
    def test_multi_word_variant():
        candidates = find_term_in_line(
            "We use REST-API for endpoints",
            "REST API",
            line_number=1,
            file_path="docs/test.md"
        )
        assert len(candidates) == 1
        assert candidates[0].match_type == "punctuation_variant"
        return candidates

    results.test("Multi-word term variants detected", test_multi_word_variant)

    return results.summary()


# ============================================================================
# Test Cases: Full Document Scanning
# ============================================================================


def test_full_document_scanning():
    """Test scanning complete documents for term candidates."""
    print("[test_candidate] Testing full document scanning")
    print("-" * 70)

    results = TestResult()

    # Test 1: Simple document
    def test_simple_document():
        doc = DocumentInput(
            file_path="docs/test.md",
            content="# Title\n\nWe use github and GitHub Actions here.",
            lines=["# Title", "", "We use github and GitHub Actions here."]
        )
        glossary = {
            "GitHub": "GitHub",
            "GitHub Actions": "GitHub Actions",
        }
        candidates_by_file = find_term_candidates([doc], glossary)

        assert "docs/test.md" in candidates_by_file
        candidates = candidates_by_file["docs/test.md"]
        # Should find: "github" (case mismatch)
        # Should NOT find: "GitHub" (exact), "GitHub Actions" (exact)
        assert len(candidates) == 1
        assert candidates[0].found_variant == "github"
        return candidates_by_file

    results.test("Simple document scanning", test_simple_document)

    # Test 2: Document with code block
    def test_document_with_code_block():
        doc = DocumentInput(
            file_path="docs/test.md",
            content="# Title\n\nUse github in code:\n```\ngithub_token = \"xyz\"\n```\n\nBut github is uppercase.",
            lines=[
                "# Title",
                "",
                "Use github in code:",
                "```",
                "github_token = \"xyz\"",
                "```",
                "",
                "But github is uppercase."
            ]
        )
        glossary = {"GitHub": "GitHub"}
        candidates_by_file = find_term_candidates([doc], glossary)

        candidates = candidates_by_file["docs/test.md"]
        # Should find: "github" on line 3, "github" on line 8
        # Should NOT find: "github" in code block (line 5)
        assert len(candidates) == 2
        assert all(c.line_number in [3, 8] for c in candidates)
        return candidates_by_file

    results.test("Code block lines are skipped", test_document_with_code_block)

    # Test 3: Multiple documents
    def test_multiple_documents():
        doc1 = DocumentInput(
            file_path="docs/file1.md",
            content="Use github here",
            lines=["Use github here"]
        )
        doc2 = DocumentInput(
            file_path="docs/file2.md",
            content="Use github there",
            lines=["Use github there"]
        )
        glossary = {"GitHub": "GitHub"}
        candidates_by_file = find_term_candidates([doc1, doc2], glossary)

        assert len(candidates_by_file) == 2
        assert len(candidates_by_file["docs/file1.md"]) == 1
        assert len(candidates_by_file["docs/file2.md"]) == 1
        return candidates_by_file

    results.test("Multiple documents scanned", test_multiple_documents)

    return results.summary()


# ============================================================================
# Integration Test: Real Glossary and Documents
# ============================================================================


def test_real_glossary_and_docs():
    """Test with real project glossary and sample documents."""
    print("[test_candidate] Integration: Real glossary + documents")
    print("-" * 70)

    results = TestResult()

    def test_integration():
        # Sample glossary (subset of real one)
        glossary = {
            "API": "API (Application Programming Interface)",
            "GitHub": "GitHub",
            "Groq": "Groq",
            "Markdown": "Markdown",
            "CI/CD": "CI/CD",
            "GitHub Actions": "GitHub Actions",
            "docs-as-code": "docs-as-code",
            "REST API": "REST API",
        }

        # Create sample documents matching your real docs
        index_doc = DocumentInput(
            file_path="docs/index.md",
            content="""# Welcome to Engineer the Docs

This is our documentation site built with Zensical and docs-as-code principles.

## What We Do

We use GitHub Actions for CI/CD and markdownlint for quality gates.

## Key Tools

- **API**: Our REST API documentation
- **GitHub**: Version control and automation
- **GitHub Actions**: CI/CD pipeline orchestration
- **Groq**: AI-powered documentation QA
""",
            lines=[
                "# Welcome to Engineer the Docs",
                "",
                "This is our documentation site built with Zensical and docs-as-code principles.",
                "",
                "## What We Do",
                "",
                "We use GitHub Actions for CI/CD and markdownlint for quality gates.",
                "",
                "## Key Tools",
                "",
                "- **API**: Our REST API documentation",
                "- **GitHub**: Version control and automation",
                "- **GitHub Actions**: CI/CD pipeline orchestration",
                "- **Groq**: AI-powered documentation QA",
            ]
        )

        setup_doc = DocumentInput(
            file_path="docs/guides/setup.md",
            content="""# Setup Guide

To get started, you'll need:

1. A github account (for version control)
2. Understanding of markdown and YAML
3. Knowledge of CI/CD pipelines

Edit your agents.yaml:

```yaml
agents:
  consistency_checker:
    enabled: true
```

Our REST API provides endpoints.

This demonstrates documentation engineering.
""",
            lines=[
                "# Setup Guide",
                "",
                "To get started, you'll need:",
                "",
                "1. A github account (for version control)",
                "2. Understanding of markdown and YAML",
                "3. Knowledge of CI/CD pipelines",
                "",
                "Edit your agents.yaml:",
                "",
                "```yaml",
                "agents:",
                "  consistency_checker:",
                "    enabled: true",
                "```",
                "",
                "Our REST API provides endpoints.",
                "",
                "This demonstrates documentation engineering.",
            ]
        )

        candidates_by_file = find_term_candidates(
            [index_doc, setup_doc],
            glossary
        )

        print("\n[test_integration] Found candidates:")
        for filepath, candidates in candidates_by_file.items():
            print(f"  {filepath}: {len(candidates)} candidates")
            for c in candidates:
                print(f"    Line {c.line_number}: '{c.canonical_term}' → '{c.found_variant}' ({c.match_type})")

        # Verify expected candidates
        index_candidates = candidates_by_file["docs/index.md"]
        setup_candidates = candidates_by_file["docs/guides/setup.md"]

        # Index doc should find lowercase "github", "rest api" variant
        # Setup doc should find lowercase "github", and term in code block should be skipped
        
        assert len(index_candidates) >= 1  # At least "github" lowercase
        assert len(setup_candidates) >= 1  # At least "github" lowercase

        return candidates_by_file

    results.test("Real glossary + documents integration", test_integration)

    return results.summary()


# ============================================================================
# Main
# ============================================================================


def main():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("agents.candidate_finder Test Suite")
    print("=" * 70)

    all_passed = True
    all_passed &= test_match_type_classification()
    all_passed &= test_context_extraction()
    all_passed &= test_code_block_detection()
    all_passed &= test_find_term_in_line()
    all_passed &= test_full_document_scanning()
    all_passed &= test_real_glossary_and_docs()

    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
