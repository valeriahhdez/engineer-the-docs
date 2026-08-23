# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Engineer the docs" is a docs-as-code portfolio site with two independent parts:

1. **The Zensical site** (`docs/`) — Markdown content built into a static site with [Zensical](https://github.com/facelessuser/zensical) (a Material-for-MkDocs-style generator), configured via `zensical.toml`.
2. **The agentic QA pipeline** (`agents/`) — a standalone Python package that post-processes the docs. Two agents are implemented: a terminology consistency checker and a heading/SEO optimizer (see Phase roadmap below).

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

Requires a `GROQ_API_KEY` in `.env` (loaded via `python-dotenv`) for Groq verification to run for real; without it, both agents fall back to reporting every candidate/violation as a `warning`.

Run the agents end-to-end:

```bash
python agents/run_consistency_checker.py   # terminology consistency
python agents/run_seo_optimizer.py         # heading hierarchy + clarity
```

### Tests

There is no pytest/unittest runner configured — each `test_*.py` file at the repo root is a standalone script with its own `main()` that prints pass/fail and exits non-zero on failure. Run them individually:

```bash
python test-config.py            # agents.config: load_config / load_glossary
python test_scan.py              # agents.scan: scan_docs (glob + markers)
python test_candidate_finder.py  # agents.candidate_finder: term matching, incl. an in-memory integration fixture (no real docs read)
python test_output.py            # agents.output: JSON/Markdown formatters, severity filtering
python test_seo_optimizer.py     # agents.parsing/seo_optimizer/seo_verifier + seo_json/seo_markdown formatters
```

Note: `test_candidate_finder.py`'s integration test currently fails independent of anything in this file — pre-existing, unrelated to the SEO agent.

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

```text
load_config/load_glossary (agents/config.py)
  → scan_docs           (agents/scan.py)        Phase 1
  → find_term_candidates (agents/candidate_finder.py)  Phase 2
  → verify_with_groq     (agents/groq_verifier.py)     Phase 3
  → format_output         (in run_consistency_checker.py)  Phase 4 — builds the ConsistencyReport
  → format_report          (agents/output.py)     Step 5 — renders the report as JSON/Markdown
```

- **`agents.yaml`** at the repo root is the single source of truth for *what gets checked and how* — per-agent `enabled` flag, glob `sources` (two-pass: positive patterns collected first, then patterns prefixed `!` subtracted), and agent-specific `config` (e.g. `glossary_path`/`exclude_markers` for the consistency checker, `hierarchy_rules`/`clarity_threshold` for the SEO optimizer). `consistency_checker` and `seo_optimizer` are both implemented; `alt_text_generator` is declared in the config but has no corresponding code yet.
- **`reference/glossary.yaml`** holds the canonical terminology the consistency checker validates against — loaded and validated by `load_glossary()` (must have ≥3 string-keyed, string-valued entries).
- **File-level opt-out markers** (e.g. `# --no-consistency-check`, `# --no-seo-check`) must be the literal first line of a doc file to skip it; there is no section-level exclusion.
- **`agents/documents.py`** defines the Pydantic models that flow through every phase of both pipelines: `DocumentInput` (scanned file) → `Candidate`/`HeadingNode` (Phase 2 output) → `ConsistencyIssue`/`SeoIssue` (Groq-classified severity, Phase 3 output) → `ConsistencyReport`/`SeoReport` (final report). All models use `strict = True`.
- **Phase 2 matching** (`agents/candidate_finder.py`) is case-insensitive regex over glossary terms, generating punctuation/spacing variants for multi-word terms, skipping fenced code blocks (`is_in_code_block`, tracked by counting ``` fences per line), inline code spans, and markdown link URLs. It classifies each hit as `case_mismatch`, `punctuation_variant`, `abbreviation`, or `unknown` — but does not assign severity.
- **Phase 3** (`agents/groq_verifier.py`) sends all candidates plus the glossary to Groq (`openai/gpt-oss-120b`, structured JSON output validated by `GroqVerificationResponse`) to classify each as `error`/`warning`/`info` with reasoning. Any failure mode (missing API key, malformed/invalid JSON, API error) degrades gracefully to `_fallback_to_warnings()` rather than failing the pipeline — this is a deliberate design choice, not a bug.
- Test files mirror the consistency-checker modules 1:1 (`test-config.py` ↔ `agents/config.py`, `test_scan.py` ↔ `agents/scan.py`, `test_candidate_finder.py` ↔ `agents/candidate_finder.py`, `test_output.py` ↔ `agents/output.py`; `test_seo_optimizer.py` covers `agents/parsing.py` + `agents/seo_optimizer.py` + `agents/seo_verifier.py` together) and use synthetic in-memory fixtures (`DocumentInput`/`ConsistencyReport`/`HeadingNode` objects built inline) rather than reading real files from `docs/` — file paths like `docs/guides/setup.md` appearing in test output are fixture labels, not real project files.
- **`agents/output.py`** renders a built report (`ConsistencyReport` or `SeoReport`) into output strings. It is a pure formatting layer — no file I/O, no config loading — via a `FORMATTERS` registry (`{"json": format_json, "markdown": format_markdown, "seo_json": format_seo_json, "seo_markdown": format_seo_markdown}`) dispatched through `format_report(report, formats, severity_threshold="info")`. `formats` is a required argument (no "run everything" default): the registry holds formatters for two different report shapes, so a caller must always state which pair matches its report type, or a `ConsistencyReport` handed to a `format_seo_*` formatter (or vice versa) would blow up on a missing field. Adding a new output format (e.g. the roadmap's planned GitHub PR annotations) means writing one `fn(report, severity_threshold) -> str` function and adding it to the registry — no call-site changes beyond the new `formats` entry. `severity_threshold` (read from `agents.yaml`'s `output.severity_threshold`) filters which issues each formatter *displays*; it does not change `report.status`/`issues_found`, which always reflect the full, unfiltered issue set — the report is the single source of truth, filtering is presentation-only.

### SEO heading optimizer pipeline

Mirrors the consistency checker's phase structure, wired in `agents/run_seo_optimizer.py:main()`, reusing `agents/scan.py` and the `agents/output.py` registry:

```text
load_config (agents/config.py)
  → scan_docs                     (agents/scan.py)             Phase 1 — shared with consistency checker
  → parse_headings_from_markdown  (agents/parsing.py)           Phase 2a — extracts HeadingNode list per doc, with parent tracking
  → detect_hierarchy_violations   (agents/seo_optimizer.py)     Phase 2b — flags structural issues, no severity yet
  → verify_seo_with_groq          (agents/seo_verifier.py)      Phase 3 — ONE batched Groq call per document
  → format_output                 (in run_seo_optimizer.py)     builds the SeoReport
  → format_report                 (agents/output.py)            renders seo_json/seo_markdown
```

- **`agents/parsing.py`**'s `parse_headings_from_markdown()` extracts ATX headings (`#`–`######` only — no Setext `===`/`---` support), skipping fenced code blocks, and tracks `parent_heading` via a level-ordered stack (nearest preceding heading with a lower level).
- **`agents/seo_optimizer.py`**'s `detect_hierarchy_violations()` reads `hierarchy_rules` from `agents.yaml` (`require_h1`, `allow_h{N}_skip`, `max_nesting_depth`). Any skip level not explicitly allowed defaults to disallowed — opt-in, like every other discovery rule in this project.
- **`agents/seo_verifier.py`**'s `verify_seo_with_groq()` batches an entire document's headings + violations into a single Groq call (not one call per heading), matched back by line number. It reuses `get_groq_client()` from `agents/groq_verifier.py` rather than duplicating the API-key bootstrap, and degrades the same way: any failure converts hierarchy violations to `warning`-severity issues with clarity scoring skipped (it requires the LLM).
- **Artifact naming**: `agents.yaml`'s `output` block (`artifact_name`, `severity_threshold`) is shared, not per-agent. `run_seo_optimizer.py` reuses `output.severity_threshold` but writes its own files under a hardcoded `agent-seo-report.md`/`.json` (distinct from the consistency checker's `agent-qa-report.md`/`.json`) so the two agents don't clobber each other's artifacts. If you add per-agent artifact naming to `agents.yaml` later, update both entry points.
- Not yet wired into `.github/workflows/ci-cd.yml` — only `run_consistency_checker.py` runs in CI today.

## CI/CD (`.github/workflows/ci-cd.yml`)

Four jobs on push/PR to `main`: `lint-and-validate` (markdownlint + Vale) → `build` (`zensical build --strict`) → `agents` and `deploy` run in parallel, both only depending on `build`, so a flagged terminology issue never blocks a Pages deployment.

- **`agents`** runs `agents/run_consistency_checker.py` with `continue-on-error: true` (the script exits non-zero when issues are found — that's expected, not a workflow failure). It's gated by `dorny/paths-filter` (only runs if `docs/**`, `reference/**`, or `agents/**` changed, to conserve Groq API calls) and skips gracefully on fork PRs (`GROQ_API_KEY` is withheld by GitHub for those). On a same-repo run with the secret missing, it fails fast with a clear error instead of silently no-op'ing. It posts the rendered Markdown to `$GITHUB_STEP_SUMMARY` and uploads the JSON report as a build artifact — both read from `agent-qa-report.md`/`.json`, which `run_consistency_checker.py` writes to disk using `agents.yaml`'s `output.artifact_name`. Rename `artifact_name` in `agents.yaml` and update the workflow's hardcoded filenames to match.
