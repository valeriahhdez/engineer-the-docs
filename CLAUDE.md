# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Engineer the docs" is a docs-as-code portfolio site with two independent parts:

1. **The Zensical site** (`docs/`) — Markdown content built into a static site with [Zensical](https://github.com/facelessuser/zensical) (a Material-for-MkDocs-style generator), configured via `zensical.toml`.
2. **The agentic QA pipeline** (`agents/`) — a standalone Python package that post-processes the docs for terminology consistency, currently in active development (see Phase roadmap below).

These two parts share the `docs/` directory as input but are otherwise decoupled — the site build does not depend on the agents package.

## Commands

### Site (Zensical)

```bash
pip install -r requirements.txt   # site build deps
zensical build --strict           # build to site/
```

There is no local `zensical serve`/dev-server command recorded in this repo yet — check the Zensical CLI (`zensical --help`) if one is needed.

### Agents package

```bash
pip install -r requirements-agents.txt   # groq, pydantic, pyyaml
pip install python-dotenv                # required by agents/run_consistency_checker.py but missing from requirements-agents.txt
```

Requires a `GROQ_API_KEY` in `.env` (loaded via `python-dotenv`) for Phase 3 (Groq verification) to run for real; without it, the pipeline falls back to reporting every candidate as a `warning`.

Run the full consistency checker end-to-end:

```bash
python agents/run_consistency_checker.py
```

### Tests

There is no pytest/unittest runner configured — each `test_*.py` file at the repo root is a standalone script with its own `main()` that prints pass/fail and exits non-zero on failure. Run them individually:

```bash
python test-config.py            # agents.config: load_config / load_glossary
python test_scan.py              # agents.scan: scan_docs (glob + markers)
python test_candidate_finder.py  # agents.candidate_finder: term matching, incl. an in-memory integration fixture (no real docs read)
python test_output.py            # agents.output: JSON/Markdown formatters, severity filtering
```

Each file inserts the repo root onto `sys.path` itself, so run them from the repo root without extra setup.

### Linting (docs content, runs in CI)

```bash
# Markdown lint (config in .markdownlint-cli2.yaml — MD013/MD033/MD046 disabled)
markdownlint-cli2 "**/*.md"

# Vale prose linter (config in .vale.ini; styles in .github/styles/, Google base + custom vocab)
vale docs
```

## Architecture: agents package

The consistency-checker pipeline is a strict 4-phase sequence, all wired together in `agents/run_consistency_checker.py:main()`:

```
load_config/load_glossary (agents/config.py)
  → scan_docs           (agents/scan.py)        Phase 1
  → find_term_candidates (agents/candidate_finder.py)  Phase 2
  → verify_with_groq     (agents/groq_verifier.py)     Phase 3
  → format_output         (in run_consistency_checker.py)  Phase 4 — builds the ConsistencyReport
  → format_report          (agents/output.py)     Step 5 — renders the report as JSON/Markdown
```

- **`agents.yaml`** at the repo root is the single source of truth for *what gets checked and how* — per-agent `enabled` flag, glob `sources` (two-pass: positive patterns collected first, then patterns prefixed `!` subtracted), and agent-specific `config` (e.g. `glossary_path`, `exclude_markers`). Only the `consistency_checker` agent is implemented; `alt_text_generator` and `seo_optimizer` are declared in the config but have no corresponding code yet.
- **`reference/glossary.yaml`** holds the canonical terminology the checker validates against — loaded and validated by `load_glossary()` (must have ≥3 string-keyed, string-valued entries).
- **File-level opt-out markers** (e.g. `# --no-consistency-check`) must be the literal first line of a doc file to skip it; there is no section-level exclusion.
- **`agents/documents.py`** defines the Pydantic models that flow through every phase: `DocumentInput` (scanned file) → `Candidate` (regex-flagged variant, Phase 2 output) → `ConsistencyIssue` (Groq-classified severity, Phase 3 output) → `ConsistencyReport` (final Phase 4 output). All models use `strict = True`.
- **Phase 2 matching** (`agents/candidate_finder.py`) is case-insensitive regex over glossary terms, generating punctuation/spacing variants for multi-word terms, skipping fenced code blocks (`is_in_code_block`, tracked by counting ``` fences per line), inline code spans, and markdown link URLs. It classifies each hit as `case_mismatch`, `punctuation_variant`, `abbreviation`, or `unknown` — but does not assign severity.
- **Phase 3** (`agents/groq_verifier.py`) sends all candidates plus the glossary to Groq (`llama-3.3-70b-versatile`, structured JSON output validated by `GroqVerificationResponse`) to classify each as `error`/`warning`/`info` with reasoning. Any failure mode (missing API key, malformed/invalid JSON, API error) degrades gracefully to `_fallback_to_warnings()` rather than failing the pipeline — this is a deliberate design choice, not a bug.
- Test files mirror this structure 1:1 (`test-config.py` ↔ `agents/config.py`, `test_scan.py` ↔ `agents/scan.py`, `test_candidate_finder.py` ↔ `agents/candidate_finder.py`, `test_output.py` ↔ `agents/output.py`) and use synthetic in-memory fixtures (`DocumentInput`/`ConsistencyReport` objects built inline) rather than reading real files from `docs/` — file paths like `docs/guides/setup.md` appearing in test output are fixture labels, not real project files.
- **`agents/output.py`** (Step 5) renders a built `ConsistencyReport` into output strings. It is a pure formatting layer — no file I/O, no config loading — via a `FORMATTERS` registry (`{"json": format_json, "markdown": format_markdown}`) dispatched through `format_report(report, formats=None, severity_threshold="info")`. Adding a new output format (the roadmap's planned GitHub PR annotations) means writing one `fn(report, severity_threshold) -> str` function and adding it to the registry — no call-site changes. `severity_threshold` (read from `agents.yaml`'s `output.severity_threshold`) filters which issues each formatter *displays*; it does not change `report.status`/`issues_found`, which always reflect the full, unfiltered issue set from Phase 3 — the report is the single source of truth, filtering is presentation-only. `run_consistency_checker.py:main()` calls `format_report()` in its Output section and prints both renderings.

## CI/CD (`.github/workflows/ci-cd.yml`)

Three-job pipeline on push/PR to `main`: `lint-and-validate` (markdownlint + Vale) → `build` (`zensical build --strict`, only on the site, not the agents pipeline) → `deploy` (GitHub Pages, main-branch pushes only). The agents package is not currently wired into CI.