"""
Test suite for agents.config module.

This test file verifies production-ready behavior:
- Happy path: valid config and glossary loading
- Error cases: missing files, invalid YAML, structure violations, insufficient terms
- Type validation: all keys/values are strings in glossary

Run with: python test_config.py
"""

import os
import sys
import tempfile
from pathlib import Path

# Add agents/ to path so we can import config module
sys.path.insert(0, str(Path(__file__).parent))

from agents.config import load_config, load_glossary


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
                    f"✗ {name}: {type(e).__name__}: {str(e)[:80]}"
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
# Test Cases: load_config()
# ============================================================================


def test_load_config():
    """Test load_config() with valid and invalid inputs."""
    print("\n[test_config] Testing load_config()")
    print("-" * 70)

    results = TestResult()

    # Test 1: Valid config file
    def test_valid_config():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents:
  consistency_checker:
    config:
      glossary_path: reference/glossary.yaml
"""
            )
            config = load_config(str(config_file))
            assert isinstance(config, dict)
            assert "agents" in config
            assert config["agents"]["consistency_checker"]["config"]["glossary_path"] == "reference/glossary.yaml"
            return config

    results.test("Valid config loads successfully", test_valid_config)

    # Test 2: Missing file
    def test_missing_file():
        load_config("/nonexistent/agents.yaml")

    results.test("Missing file raises FileNotFoundError", test_missing_file, FileNotFoundError)

    # Test 3: Invalid YAML
    def test_invalid_yaml():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents:
  - this is a list, not a dict
"""
            )
            load_config(str(config_file))

    results.test("Invalid YAML raises ValueError", test_invalid_yaml, ValueError)

    # Test 4: Missing 'agents' key
    def test_missing_agents_key():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text("something_else: value")
            load_config(str(config_file))

    results.test("Missing 'agents' key raises ValueError", test_missing_agents_key, ValueError)

    # Test 5: Missing consistency_checker
    def test_missing_consistency_checker():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents:
  other_agent:
    config: {}
"""
            )
            load_config(str(config_file))

    results.test("Missing consistency_checker raises ValueError", test_missing_consistency_checker, ValueError)

    # Test 6: Missing glossary_path in config
    def test_missing_glossary_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents:
  consistency_checker:
    config:
      other_setting: value
"""
            )
            load_config(str(config_file))

    results.test("Missing glossary_path raises ValueError", test_missing_glossary_path, ValueError)

    # Test 7: Empty glossary_path
    def test_empty_glossary_path():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents:
  consistency_checker:
    config:
      glossary_path: ""
"""
            )
            load_config(str(config_file))

    results.test("Empty glossary_path raises ValueError", test_empty_glossary_path, ValueError)

    # Test 8: agents is not a dict
    def test_agents_not_dict():
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "agents.yaml"
            config_file.write_text(
                """
agents: "string instead of dict"
"""
            )
            load_config(str(config_file))

    results.test("agents not dict raises ValueError", test_agents_not_dict, ValueError)

    return results.summary()


# ============================================================================
# Test Cases: load_glossary()
# ============================================================================


def test_load_glossary():
    """Test load_glossary() with valid and invalid inputs."""
    print("[test_config] Testing load_glossary()")
    print("-" * 70)

    results = TestResult()

    # Test 1: Valid glossary
    def test_valid_glossary():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
documentation: Organized written information about a system
consistency: Uniform terminology and style throughout content
quality: Degree to which content meets defined standards
"""
            )
            glossary = load_glossary(str(glossary_file))
            assert isinstance(glossary, dict)
            assert len(glossary) == 3
            assert glossary["documentation"] == "Organized written information about a system"
            return glossary

    results.test("Valid glossary loads successfully", test_valid_glossary)

    # Test 2: Missing file
    def test_missing_file():
        load_glossary("/nonexistent/glossary.yaml")

    results.test("Missing file raises FileNotFoundError", test_missing_file, FileNotFoundError)

    # Test 3: Invalid YAML
    def test_invalid_yaml():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text("term: [unclosed list")
            load_glossary(str(glossary_file))

    results.test("Invalid YAML raises ValueError", test_invalid_yaml, ValueError)

    # Test 4: Empty glossary
    def test_empty_glossary():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text("{}")
            load_glossary(str(glossary_file))

    results.test("Empty glossary raises ValueError", test_empty_glossary, ValueError)

    # Test 5: Too few terms (only 1)
    def test_insufficient_terms_one():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text("term: definition")
            load_glossary(str(glossary_file))

    results.test("Glossary with 1 term raises ValueError", test_insufficient_terms_one, ValueError)

    # Test 6: Too few terms (only 2)
    def test_insufficient_terms_two():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
term1: definition 1
term2: definition 2
"""
            )
            load_glossary(str(glossary_file))

    results.test("Glossary with 2 terms raises ValueError", test_insufficient_terms_two, ValueError)

    # Test 7: Non-dict glossary (list)
    def test_non_dict_glossary():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
- term1
- term2
- term3
"""
            )
            load_glossary(str(glossary_file))

    results.test("Non-dict glossary raises ValueError", test_non_dict_glossary, ValueError)

    # Test 8: Non-string key
    def test_non_string_key():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
123: numeric key
term2: definition 2
term3: definition 3
"""
            )
            load_glossary(str(glossary_file))

    results.test("Non-string key raises ValueError", test_non_string_key, ValueError)

    # Test 9: Non-string value
    def test_non_string_value():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
term1: definition 1
term2: 123
term3: definition 3
"""
            )
            load_glossary(str(glossary_file))

    results.test("Non-string value raises ValueError", test_non_string_value, ValueError)

    # Test 10: Exactly 3 terms (boundary)
    def test_exactly_three_terms():
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "glossary.yaml"
            glossary_file.write_text(
                """
term1: definition 1
term2: definition 2
term3: definition 3
"""
            )
            glossary = load_glossary(str(glossary_file))
            assert len(glossary) == 3
            return glossary

    results.test("Glossary with exactly 3 terms loads successfully", test_exactly_three_terms)

    return results.summary()


# ============================================================================
# Integration Test: Full Workflow
# ============================================================================


def test_integration():
    """Test full workflow: load config, extract glossary path, load glossary."""
    print("[test_config] Integration: Config → Glossary")
    print("-" * 70)

    results = TestResult()

    def test_full_workflow():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create config file
            config_file = tmpdir / "agents.yaml"
            config_file.write_text(
                """
agents:
  consistency_checker:
    config:
      glossary_path: reference/glossary.yaml
"""
            )

            # Create glossary file
            glossary_file = tmpdir / "reference" / "glossary.yaml"
            glossary_file.parent.mkdir()
            glossary_file.write_text(
                """
documentation: Organized information
consistency: Uniform terminology
quality: High standards
"""
            )

            # Load config
            config = load_config(str(config_file))
            glossary_path_rel = config["agents"]["consistency_checker"]["config"]["glossary_path"]

            # Resolve glossary path relative to config directory
            glossary_path = tmpdir / glossary_path_rel

            # Load glossary
            glossary = load_glossary(str(glossary_path))

            assert len(glossary) == 3
            assert "consistency" in glossary
            return True

    results.test("Full workflow: config → glossary", test_full_workflow)

    return results.summary()


# ============================================================================
# Main
# ============================================================================


def main():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("agents.config Test Suite")
    print("=" * 70)

    all_passed = True
    all_passed &= test_load_config()
    all_passed &= test_load_glossary()
    all_passed &= test_integration()

    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()