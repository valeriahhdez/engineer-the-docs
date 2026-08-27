"""
Test suite for the alt text generator agent:
agents.alt_text_finder (Phase 2: classify + section-bounded context) and
agents.alt_text_verifier (Phase 3: Groq vision + fallback degradation).

This test file verifies production-ready behavior:
- 3-step classifier: has_alt / decorative / generate, including the
  filename-exact-match placeholder edge case
- decorative_paths glob matching (via the real filesystem)
- Broken image references (no LLM call)
- Fenced code block exclusion
- Section-bounded context extraction, including the oversized-section
  trim-outward case
- Vision-failure -> context-only -> heuristic degradation chain

Note on mocking: every other test file in this project deliberately
avoids mocking (see agents/config.py's docstring: "No mocking: pure file
I/O, testable in isolation"). Phase 3 here is the one exception, per
explicit instruction — there's no deterministic way to test the
vision -> context_fallback -> heuristic degradation chain against a real,
non-deterministic API without controlling exactly when/how it fails.
Phase 2 (classification, context extraction) still uses real files and
no mocking, consistent with the rest of the project.

Run with: python test_alt_text_generator.py
"""

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Add agents/ to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.documents import AltTextCandidate, DocumentInput, HeadingNode
from agents.parsing import parse_headings_from_markdown
from agents.alt_text_finder import (
    classify_alt_text,
    extract_section_context,
    find_alt_text_candidates,
    find_image_references,
    is_external_image,
    resolve_decorative_paths,
    resolve_image_path,
    _trim_outward,
)
from agents.alt_text_verifier import (
    _heuristic_alt_text,
    generate_alt_text,
)


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
                    f"✗ {name}: {type(e).__name__}: {str(e)[:150]}"
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


def make_candidate(**overrides):
    fields = dict(
        file_path="guide.md",
        image_path="assets/images/diagram.png",
        image_abs_path="/tmp/does-not-matter.png",
        line_number=9,
        alt_text_raw="diagram.png",
        heading_breadcrumb="Database Architecture > Performance Tuning",
        context_text="Some prose describing the diagram.",
    )
    fields.update(overrides)
    return AltTextCandidate(**fields)


class FakeGroqResponse:
    """Mimics groq's ChatCompletion response shape (choices[0].message.content)."""

    def __init__(self, content: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


class FakeGroqClient:
    """
    Mimics the groq.Groq client's call surface used by alt_text_verifier:
    client.chat.completions.create(...). Consumes queued responses in
    order; a queued Exception instance is raised instead of returned.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeGroqResponse(item)


# ============================================================================
# Test Cases: Image Reference Detection (agents/alt_text_finder.py)
# ============================================================================


def test_image_reference_detection():
    print("\n[test_alt_text] Testing image reference detection")
    print("-" * 70)

    results = TestResult()

    def test_basic_detection():
        lines = ["Some text", "![alt text](assets/img.png)", "More text"]
        refs = find_image_references(lines)
        assert refs == [(2, "alt text", "assets/img.png")]
        return refs

    results.test("Basic image reference detected with correct line number", test_basic_detection)

    def test_empty_alt():
        lines = ["![](assets/icon.svg)"]
        refs = find_image_references(lines)
        assert refs == [(1, "", "assets/icon.svg")]
        return refs

    results.test("Empty alt text captured as empty string", test_empty_alt)

    def test_code_fence_exclusion():
        lines = [
            "Real image below:",
            "![real](assets/real.png)",
            "```markdown",
            "![fake](assets/fake.png)",
            "```",
            "After the block",
        ]
        refs = find_image_references(lines)
        assert len(refs) == 1
        assert refs[0][2] == "assets/real.png"
        return refs

    results.test("Image references inside fenced code blocks are excluded", test_code_fence_exclusion)

    def test_title_syntax_stripped():
        lines = ['![alt](assets/img.png "A title")']
        refs = find_image_references(lines)
        assert refs[0][2] == "assets/img.png"
        return refs

    results.test("Trailing quoted title syntax is stripped from the path", test_title_syntax_stripped)

    def test_external_detection():
        assert is_external_image("https://example.com/img.png") is True
        assert is_external_image("http://example.com/img.png") is True
        assert is_external_image("assets/img.png") is False
        assert is_external_image("../assets/img.png") is False
        return True

    results.test("External http(s) sources are correctly identified", test_external_detection)

    return results.summary()


# ============================================================================
# Test Cases: 3-Step Classifier (agents/alt_text_finder.py)
# ============================================================================


def test_classifier():
    print("[test_alt_text] Testing 3-step classifier")
    print("-" * 70)

    results = TestResult()

    def test_has_alt():
        result = classify_alt_text("A clear description", "diagram.png", is_decorative_path=False)
        assert result == "has_alt"
        return result

    results.test("Real alt text -> has_alt", test_has_alt)

    def test_filename_placeholder_exact_match():
        # The core edge case: alt text IS the filename, exactly (with extension)
        result = classify_alt_text("diagram.png", "diagram.png", is_decorative_path=False)
        assert result == "generate"
        return result

    results.test("Filename-as-alt placeholder (exact match) -> generate", test_filename_placeholder_exact_match)

    def test_filename_match_must_be_exact_no_fuzzy():
        # A genuinely good, humanized alt text (no extension) must NOT be
        # mistaken for the placeholder, even if derived from the filename
        result = classify_alt_text("Diagram", "diagram.png", is_decorative_path=False)
        assert result == "has_alt"
        return result

    results.test(
        "Fuzzy filename-like alt text (no extension) is NOT treated as placeholder",
        test_filename_match_must_be_exact_no_fuzzy,
    )

    def test_filename_match_case_sensitive():
        # Doc: "exact match" — different case should not count as the placeholder
        result = classify_alt_text("Diagram.PNG", "diagram.png", is_decorative_path=False)
        assert result == "has_alt"
        return result

    results.test("Filename placeholder match is case-sensitive (exact only)", test_filename_match_case_sensitive)

    def test_decorative():
        result = classify_alt_text("", "icon.svg", is_decorative_path=True)
        assert result == "decorative"
        return result

    results.test("Empty alt + decorative path -> decorative", test_decorative)

    def test_empty_not_decorative_generates():
        # Safety net: accidental ![]() outside a decorative path still flagged
        result = classify_alt_text("", "screenshot.png", is_decorative_path=False)
        assert result == "generate"
        return result

    results.test("Empty alt + NOT a decorative path -> generate (safety net)", test_empty_not_decorative_generates)

    def test_decorative_path_with_real_alt_is_respected():
        # Doc: "If a decorative-path image somehow has real alt text, that
        # text is respected and left alone"
        result = classify_alt_text("A hand-drawn rocket icon", "rocket.svg", is_decorative_path=True)
        assert result == "has_alt"
        return result

    results.test("Decorative-path image WITH real alt text is respected as has_alt", test_decorative_path_with_real_alt_is_respected)

    return results.summary()


# ============================================================================
# Test Cases: Decorative Path Resolution (real filesystem, no mocking)
# ============================================================================


def test_decorative_path_resolution():
    print("[test_alt_text] Testing decorative_paths glob resolution")
    print("-" * 70)

    results = TestResult()

    def test_glob_matches_real_files():
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            icons_dir = docs_root / "assets" / "icons"
            icons_dir.mkdir(parents=True)
            (icons_dir / "play.svg").write_text("<svg></svg>")
            (icons_dir / "sub").mkdir()
            (icons_dir / "sub" / "nested.svg").write_text("<svg></svg>")
            other_dir = docs_root / "assets" / "images"
            other_dir.mkdir(parents=True)
            (other_dir / "diagram.png").write_bytes(b"fake-png-bytes")

            resolved = resolve_decorative_paths(["assets/icons/**"], docs_root)

            assert "assets/icons/play.svg" in resolved
            assert "assets/icons/sub/nested.svg" in resolved
            assert "assets/images/diagram.png" not in resolved
            return resolved

    results.test("decorative_paths glob matches nested files via ** (real filesystem)", test_glob_matches_real_files)

    return results.summary()


# ============================================================================
# Test Cases: Broken References + Full Document Classification
# ============================================================================


def test_broken_references_and_full_scan():
    print("[test_alt_text] Testing broken references and full document scan")
    print("-" * 70)

    results = TestResult()

    def test_broken_reference_flagged_no_llm():
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            docs_root.mkdir(exist_ok=True)
            content = "# Guide\n\n![missing.png](assets/missing.png)\n"
            lines = content.split("\n")
            doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
            headings = parse_headings_from_markdown(content)

            candidates, broken_issues, total = find_alt_text_candidates(
                doc, headings, docs_root, decorative_paths=set(), context_word_cap=200
            )

            assert candidates == []
            assert total == 1
            assert len(broken_issues) == 1
            assert broken_issues[0].source == "broken_reference"
            assert broken_issues[0].suggested_alt == ""
            assert broken_issues[0].line_number == 3
            return broken_issues

    results.test("Broken image reference is flagged as source='broken_reference', no candidate created", test_broken_reference_flagged_no_llm)

    def test_full_scan_classification_mix():
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_root = Path(tmpdir)
            (docs_root / "assets" / "icons").mkdir(parents=True)
            (docs_root / "assets" / "images").mkdir(parents=True)
            (docs_root / "assets" / "icons" / "star.svg").write_text("<svg></svg>")
            (docs_root / "assets" / "images" / "diagram.png").write_bytes(b"fake")

            content = (
                "# Guide\n"
                "\n"
                "![A clear diagram of the pipeline](assets/images/diagram.png)\n"
                "\n"
                "![](assets/icons/star.svg)\n"
                "\n"
                "![diagram.png](assets/images/diagram.png)\n"
                "\n"
                "![missing.png](assets/nope.png)\n"
            )
            lines = content.split("\n")
            doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
            headings = parse_headings_from_markdown(content)
            decorative = resolve_decorative_paths(["assets/icons/**"], docs_root)

            candidates, broken_issues, total = find_alt_text_candidates(
                doc, headings, docs_root, decorative, context_word_cap=200
            )

            assert total == 4
            assert len(candidates) == 1  # only the filename-placeholder one
            assert candidates[0].image_path == "assets/images/diagram.png"
            assert len(broken_issues) == 1
            return candidates, broken_issues

    results.test(
        "Full scan: has_alt/decorative skipped, placeholder generates, broken flagged",
        test_full_scan_classification_mix,
    )

    return results.summary()


# ============================================================================
# Test Cases: Section-Bounded Context Extraction
# ============================================================================


def test_context_extraction():
    print("[test_alt_text] Testing section-bounded context extraction")
    print("-" * 70)

    results = TestResult()

    def test_breadcrumb_multi_level():
        content = (
            "# Top\n"
            "## Database Architecture\n"
            "### Performance Tuning\n"
            "\n"
            "![diagram.png](assets/diagram.png)\n"
        )
        lines = content.split("\n")
        doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
        headings = parse_headings_from_markdown(content)

        breadcrumb, _ = extract_section_context(doc, headings, image_line=5, word_cap=200)
        assert breadcrumb == "Top > Database Architecture > Performance Tuning"
        return breadcrumb

    results.test("Breadcrumb includes full ancestor chain, not just immediate parent", test_breadcrumb_multi_level)

    def test_section_stops_at_next_heading():
        content = (
            "## Section A\n"
            "\n"
            "Relevant text about A.\n"
            "\n"
            "![img.png](assets/img.png)\n"
            "\n"
            "## Section B\n"
            "\n"
            "Unrelated text about B.\n"
        )
        lines = content.split("\n")
        doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
        headings = parse_headings_from_markdown(content)

        _, context = extract_section_context(doc, headings, image_line=5, word_cap=200)
        assert "Relevant text about A" in context
        assert "Unrelated text about B" not in context
        return context

    results.test("Context stops at the next same-or-higher-level heading", test_section_stops_at_next_heading)

    def test_noise_stripped_from_context():
        content = (
            "## Section\n"
            "\n"
            "Intro text.\n"
            "\n"
            "```python\n"
            "code_that_should_be_stripped()\n"
            "```\n"
            "\n"
            "![this-image.png](assets/this-image.png)\n"
            "\n"
            "![another.png](assets/another.png) sits nearby too.\n"
            "\n"
            "<div>raw html</div>\n"
        )
        lines = content.split("\n")
        doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
        headings = parse_headings_from_markdown(content)

        _, context = extract_section_context(doc, headings, image_line=9, word_cap=200)
        assert "code_that_should_be_stripped" not in context
        assert "![" not in context
        assert "<div>" not in context
        assert "Intro text" in context
        assert "sits nearby too" in context
        return context

    results.test("Code fences, image refs, and raw HTML are stripped from context", test_noise_stripped_from_context)

    def test_oversized_section_trims_outward():
        # Build a section far larger than the word cap; the image sits in
        # the middle. Lines nearest the image should survive; lines at the
        # section's true edges (farthest from the image) should be dropped.
        # Distinct prefixes for the leading/trailing padding blocks avoid
        # any ambiguity about which end of each block sits near the image.
        far_before = [f"Leading filler {i} with several words in it." for i in range(15)]
        far_after = [f"Trailing filler {i} with several words in it." for i in range(15)]
        near_image_before = "The sentence immediately before the image describes it directly."
        near_image_after = "The sentence immediately after the image also describes it."
        content_lines = (
            ["## Section", ""]
            + far_before
            + [near_image_before, "![img.png](assets/img.png)", near_image_after]
            + far_after
        )
        content = "\n".join(content_lines)
        lines = content.split("\n")
        doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
        headings = parse_headings_from_markdown(content)

        image_line = content_lines.index("![img.png](assets/img.png)") + 1
        _, context = extract_section_context(doc, headings, image_line=image_line, word_cap=40)

        assert near_image_before in context
        assert near_image_after in context
        # Truest edges: first leading line (right after the heading) and
        # last trailing line (at the very end of the document)
        assert far_before[0] not in context
        assert far_after[-1] not in context
        return context

    results.test(
        "Oversized section trims outward from the edges, keeping text nearest the image",
        test_oversized_section_trims_outward,
    )

    def test_trim_outward_unit():
        lines = [f"line{i}" for i in range(10)]
        result = _trim_outward(lines, center_idx=5, word_cap=3)
        assert "line5" in result
        assert result == sorted(result, key=lambda l: lines.index(l))  # order preserved
        return result

    results.test("_trim_outward preserves document order in the kept subset", test_trim_outward_unit)

    def test_no_heading_before_image():
        content = "Just a paragraph.\n\n![img.png](assets/img.png)\n"
        lines = content.split("\n")
        doc = DocumentInput(file_path="guide.md", content=content, lines=lines)
        headings = parse_headings_from_markdown(content)  # empty

        breadcrumb, context = extract_section_context(doc, headings, image_line=3, word_cap=200)
        assert breadcrumb == ""
        assert "Just a paragraph" in context
        return breadcrumb, context

    results.test("Image before any heading gets empty breadcrumb, not a crash", test_no_heading_before_image)

    return results.summary()


# ============================================================================
# Test Cases: Path Resolution
# ============================================================================


def test_path_resolution():
    print("[test_alt_text] Testing image path resolution")
    print("-" * 70)

    results = TestResult()

    def test_relative_to_doc_directory():
        docs_root = Path("/repo/docs")
        result = resolve_image_path("introduction/overview.md", "../assets/images/diagram.png", docs_root)
        assert result == Path("/repo/docs/assets/images/diagram.png")
        return result

    results.test("Image path resolves relative to the referencing doc's own directory", test_relative_to_doc_directory)

    return results.summary()


# ============================================================================
# Test Cases: Groq Vision + Fallback Degradation (mocked, per explicit ask)
# ============================================================================


def test_vision_and_fallback():
    print("[test_alt_text] Testing Groq vision + fallback degradation (mocked)")
    print("-" * 70)

    results = TestResult()

    def test_vision_success():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-bytes")
            image_path = f.name
        try:
            candidate = make_candidate(image_abs_path=image_path)
            fake_client = FakeGroqClient([json.dumps({"suggested_alt": "A pipeline diagram"})])
            with patch("agents.alt_text_verifier.get_groq_client", return_value=fake_client):
                issue = generate_alt_text(candidate)
            assert issue.source == "vision"
            assert issue.suggested_alt == "A pipeline diagram"
            assert len(fake_client.calls) == 1
            assert fake_client.calls[0]["model"] == "qwen/qwen3.6-27b"
            return issue
        finally:
            Path(image_path).unlink()

    results.test("Vision call succeeds -> source='vision'", test_vision_success)

    def test_vision_fails_falls_back_to_context():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-bytes")
            image_path = f.name
        try:
            candidate = make_candidate(image_abs_path=image_path)
            fake_client = FakeGroqClient([
                RuntimeError("model unavailable"),  # vision call fails
                json.dumps({"suggested_alt": "Likely a pipeline diagram"}),  # fallback succeeds
            ])
            with patch("agents.alt_text_verifier.get_groq_client", return_value=fake_client):
                issue = generate_alt_text(candidate)
            assert issue.source == "context_fallback"
            assert issue.suggested_alt == "Likely a pipeline diagram"
            assert len(fake_client.calls) == 2
            assert fake_client.calls[1]["model"] == "openai/gpt-oss-120b"
            return issue
        finally:
            Path(image_path).unlink()

    results.test("Vision failure falls back to context-only generation -> source='context_fallback'", test_vision_fails_falls_back_to_context)

    def test_both_fail_degrades_to_heuristic():
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake-png-bytes")
            image_path = f.name
        try:
            candidate = make_candidate(
                image_abs_path=image_path,
                image_path="assets/images/docs-engineering-overview.png",
                heading_breadcrumb="Overview > Architecture",
            )
            fake_client = FakeGroqClient([
                RuntimeError("model unavailable"),
                RuntimeError("fallback also unavailable"),
            ])
            with patch("agents.alt_text_verifier.get_groq_client", return_value=fake_client):
                issue = generate_alt_text(candidate)
            assert issue.source == "context_fallback"  # still the 2-value enum, not a 3rd type
            assert issue.suggested_alt == _heuristic_alt_text(candidate)
            assert len(fake_client.calls) == 2
            return issue
        finally:
            Path(image_path).unlink()

    results.test(
        "Both vision and context-only fail -> heuristic placeholder, source stays 'context_fallback'",
        test_both_fail_degrades_to_heuristic,
    )

    def test_unsupported_format_skips_vision_entirely():
        candidate = make_candidate(image_abs_path="/nonexistent/icon.svg")
        fake_client = FakeGroqClient([json.dumps({"suggested_alt": "A star icon"})])
        with patch("agents.alt_text_verifier.get_groq_client", return_value=fake_client):
            issue = generate_alt_text(candidate)
        assert issue.source == "context_fallback"
        assert len(fake_client.calls) == 1  # only the fallback call, vision never attempted
        assert fake_client.calls[0]["model"] == "openai/gpt-oss-120b"
        return issue

    results.test("Unsupported image format (e.g. .svg) skips vision, goes straight to context-only", test_unsupported_format_skips_vision_entirely)

    def test_heuristic_alt_text_uses_breadcrumb_and_filename():
        candidate = make_candidate(
            image_path="assets/images/docs-engineering-overview.png",
            heading_breadcrumb="Overview > Architecture",
        )
        result = _heuristic_alt_text(candidate)
        assert "Architecture" in result
        assert "docs" in result.lower()
        return result

    results.test("_heuristic_alt_text humanizes filename and includes nearest breadcrumb topic", test_heuristic_alt_text_uses_breadcrumb_and_filename)

    return results.summary()


# ============================================================================
# Main
# ============================================================================


def main():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("Alt text generator Test Suite")
    print("=" * 70)

    all_passed = True
    all_passed &= test_image_reference_detection()
    all_passed &= test_classifier()
    all_passed &= test_decorative_path_resolution()
    all_passed &= test_broken_references_and_full_scan()
    all_passed &= test_context_extraction()
    all_passed &= test_path_resolution()
    all_passed &= test_vision_and_fallback()

    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
