# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Engineer the docs" is a docs-as-code portfolio site with two independent parts:

1. **The Zensical site** (`docs/`) — Markdown content built into a static site with [Zensical](https://github.com/facelessuser/zensical) (a Material-for-MkDocs-style generator), configured via `zensical.toml`.
2. **The agentic QA pipeline** (`agents/`) — a standalone Python package that post-processes the docs. Three agents are implemented: a terminology consistency checker, a heading/SEO optimizer, and an alt text generator (see Phase roadmap below).

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
pip install -r requirements-agents.txt   # groq, pydantic, pyyaml, python-dotenv
```

Requires a `GROQ_API_KEY` in `.env` (loaded via `python-dotenv`) for Groq verification to run for real; without it, all three agents fall back — consistency checker and SEO optimizer report every candidate/violation as a `warning`; the alt text generator falls back from vision to context-only generation, then to a non-LLM heuristic if even that fails.

Run the agents end-to-end:

```bash
python agents/run_consistency_checker.py   # terminology consistency
python agents/run_seo_optimizer.py         # heading hierarchy + clarity
python agents/run_alt_text_generator.py    # missing/placeholder alt text
```

### Tests

There is no pytest/unittest runner configured — each `test_*.py` file at the repo root is a standalone script with its own `main()` that prints pass/fail and exits non-zero on failure. Run them individually:

```bash
python test-config.py            # agents.config: load_config / load_glossary
python test_scan.py              # agents.scan: scan_docs (glob + markers)
python test_candidate_finder.py  # agents.candidate_finder: term matching, incl. an in-memory integration fixture (no real docs read)
python test_output.py            # agents.output: JSON/Markdown formatters, severity filtering
python test_seo_optimizer.py     # agents.parsing/seo_optimizer/seo_verifier + seo_json/seo_markdown formatters
python test_alt_text_generator.py # agents.alt_text_finder + alt_text_verifier (Groq calls mocked) + alt_text_json/markdown formatters
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

- **`agents.yaml`** at the repo root is the single source of truth for *what gets checked and how* — per-agent `enabled` flag, glob `sources` (two-pass: positive patterns collected first, then patterns prefixed `!` subtracted), and agent-specific `config` (e.g. `glossary_path`/`exclude_markers` for the consistency checker, `hierarchy_rules`/`clarity_threshold` for the SEO optimizer, `decorative_paths`/`context_word_cap` for the alt text generator). All three agents (`consistency_checker`, `seo_optimizer`, `alt_text_generator`) are implemented.
- **`reference/glossary.yaml`** holds the canonical terminology the consistency checker validates against — loaded and validated by `load_glossary()` (must have ≥3 string-keyed, string-valued entries).
- **File-level opt-out markers** (e.g. `# --no-consistency-check`, `# --no-seo-check`, `# --no-alt-text`) must be the literal first line of a doc file to skip it; there is no section-level exclusion.
- **`agents/documents.py`** defines the Pydantic models that flow through every phase of all three pipelines: `DocumentInput` (scanned file) → `Candidate`/`HeadingNode`/`AltTextCandidate` (Phase 2 output) → `ConsistencyIssue`/`SeoIssue`/`AltTextIssue` (Groq-classified, Phase 3 output) → `ConsistencyReport`/`SeoReport`/`AltTextReport` (final report). All models use `strict = True` and share the `file_path`/`line_number` field naming convention.
- **Phase 2 matching** (`agents/candidate_finder.py`) is case-insensitive regex over glossary terms, generating punctuation/spacing variants for multi-word terms, skipping fenced code blocks (`is_in_code_block`, tracked by counting ``` fences per line), inline code spans, and markdown link URLs. It classifies each hit as `case_mismatch`, `punctuation_variant`, `abbreviation`, or `unknown` — but does not assign severity.
- **Phase 3** (`agents/groq_verifier.py`) sends all candidates plus the glossary to Groq (`openai/gpt-oss-120b`, structured JSON output validated by `GroqVerificationResponse`) to classify each as `error`/`warning`/`info` with reasoning. Any failure mode (missing API key, malformed/invalid JSON, API error) degrades gracefully to `_fallback_to_warnings()` rather than failing the pipeline — this is a deliberate design choice, not a bug.
- Test files mirror the consistency-checker modules 1:1 (`test-config.py` ↔ `agents/config.py`, `test_scan.py` ↔ `agents/scan.py`, `test_candidate_finder.py` ↔ `agents/candidate_finder.py`, `test_output.py` ↔ `agents/output.py`; `test_seo_optimizer.py` covers `agents/parsing.py` + `agents/seo_optimizer.py` + `agents/seo_verifier.py` together; `test_alt_text_generator.py` covers `agents/alt_text_finder.py` + `agents/alt_text_verifier.py` together) and use synthetic in-memory fixtures (`DocumentInput`/`ConsistencyReport`/`HeadingNode` objects built inline) rather than reading real files from `docs/` — file paths like `docs/guides/setup.md` appearing in test output are fixture labels, not real project files. `test_alt_text_generator.py`'s Phase 3 tests are this project's one deliberate exception to the "no mocking" convention (`unittest.mock.patch` on `get_groq_client`) — needed to deterministically exercise the vision → context-only → heuristic degradation chain.
- **`agents/output.py`** renders a built report (`ConsistencyReport`, `SeoReport`, or `AltTextReport`) into output strings. It is a pure formatting layer — no file I/O, no config loading — via a `FORMATTERS` registry (`{"json", "markdown", "seo_json", "seo_markdown", "alt_text_json", "alt_text_markdown"}`) dispatched through `format_report(report, formats, severity_threshold="info")`. `formats` is a required argument (no "run everything" default): the registry holds formatters for three different report shapes, so a caller must always state which pair matches its report type, or e.g. a `ConsistencyReport` handed to a `format_seo_*` formatter would blow up on a missing field. Adding a new output format means writing one `fn(report, severity_threshold) -> str` function and adding it to the registry — no call-site changes beyond the new `formats` entry. `severity_threshold` filters which issues each formatter *displays* for `ConsistencyReport`/`SeoReport`; `AltTextIssue` has no severity concept (a suggestion isn't a graded violation), so the alt-text formatters accept the parameter for registry signature compatibility only and ignore it.

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

### Alt text generator pipeline

Design decisions are recorded in `agents/ALT_TEXT_ARCHITECTURE.md` — read it before changing this agent's behavior. Wired in `agents/run_alt_text_generator.py:main()`, reusing `agents/scan.py`, `agents/parsing.py`, and the `agents/output.py` registry:

```text
load_config (agents/config.py)
  → scan_docs                    (agents/scan.py)              Phase 1 — shared with the other agents
  → parse_headings_from_markdown (agents/parsing.py)            Phase 2a — for breadcrumbs + section bounds
  → find_alt_text_candidates     (agents/alt_text_finder.py)    Phase 2b — classify + extract context
  → generate_alt_text            (agents/alt_text_verifier.py)  Phase 3 — ONE Groq vision call per image
  → format_output                (in run_alt_text_generator.py) builds the AltTextReport
  → format_report                (agents/output.py)             renders alt_text_json/alt_text_markdown
```

- **Generator only, not an auditor**: this agent writes alt text where it's missing; it never touches existing (non-placeholder) alt text. The "please generate this" signal is a deliberate authoring convention — write the alt text as the image's exact filename, extension included (e.g. `![docs-engineering-overview.png](...)`) — since Markdown's `![](path)` can't otherwise distinguish "not written yet" from "intentionally decorative."
- **`agents/alt_text_finder.py`**'s `classify_alt_text()` implements the architecture doc's 3-step order: (1) alt present and not the filename placeholder → `has_alt`, skip; (2) alt empty **and** path matches a configured `decorative_paths` glob → `decorative`, skip; (3) everything else → `generate`. The filename match is exact (extension included, case-sensitive) — never fuzzy. `decorative_paths` globs are resolved via real `glob.glob(..., recursive=True)` against the filesystem (same mechanism `agents/scan.py` uses for `sources`), not a hand-rolled matcher, so `**` behaves identically everywhere in this project. Broken references (image file doesn't exist) and external images (`http(s)://`) are checked before classification — broken refs become a finalized `AltTextIssue` with `source="broken_reference"` and no LLM call; external images are skipped with a console warning only, never fetched.
- **Section-bounded context, not a fixed line window**: `extract_section_context()` finds the nearest enclosing heading (via `parse_headings_from_markdown`, using the new `HeadingNode.ancestors` field for a multi-level breadcrumb like `"Database Architecture > Performance Tuning"` — `ancestors` was added specifically for this, since the pre-existing `parent_heading` field only carries one level), bounds the section at the next heading of the same or higher level, strips code fences/image refs/raw HTML, and — only if the section exceeds `context_word_cap` — trims from the section's outer edges inward, keeping the lines nearest the image.
- **Phase 3** (`agents/alt_text_verifier.py`)'s `generate_alt_text()` sends image bytes + breadcrumb + context to Groq's vision model (`qwen/qwen3.6-27b`, Groq's only vision-capable model) with `reasoning_format="hidden"` — it's a reasoning model that emits a `<think>` trace before answering even when told not to, and `max_tokens` must budget for that hidden reasoning too (1500) or `content` comes back empty. On any vision failure (including unsupported formats like `.svg`), falls back to `_generate_context_fallback()` — same prompt inputs minus the image, via a *different* model (`openai/gpt-oss-120b`, already proven in the other two agents) rather than retrying the vision model without an image. If that also fails, degrades further to a deterministic, non-LLM heuristic string (humanized filename + breadcrumb topic), with `confidence` hardcoded to `"low"` and `reasoning` explaining no LLM was reachable — still tagged `source="context_fallback"` since it's the same fallback path internally exhausting its options, not a third source type.
- **Structured Outputs, not prompt-only JSON**: both Groq calls pass `response_format=RESPONSE_SCHEMA` (a `json_schema` response format), which constrains `confidence` to a real enum (`"high"`/`"low"`) at generation time rather than hoping the model follows a free-text example — verified against both models directly; `qwen/qwen3.6-27b` needs the same `max_tokens=1500` headroom as above or the schema-validated request comes back empty. `source` (`vision`/`context_fallback`/`broken_reference`) is deliberately *not* part of this schema — it's fully determined by which code path executes, never by asking the model to self-report it, since that would create a second, potentially-contradicting source of truth for something the caller already knows with certainty.
- **Artifact naming**: writes `agent-alt-text-report.md`/`.json`, distinct from the other two agents' artifacts, same rationale as the SEO optimizer's naming above.
- **Cost scaling caveat**: `dorny/paths-filter` in CI (see below) only gates *whether the job runs at all* — it skips cleanly when nothing under `docs/**`/`reference/**`/`agents/**` changed. It does not make the scan itself incremental: once the job runs, `scan_docs()` globs `docs/**/*.md` unconditionally (no git-diff awareness anywhere in the pipeline), so every run re-scans and re-vision-calls every image in the entire `docs/` tree, not just images in the file that changed. The other two agents have the same full-corpus-per-run behavior; it's more expensive here because vision calls cost more than text classification calls. Making this incremental would mean changing `run_alt_text_generator.py`'s scanning logic, not the CI config.

## CI/CD (`.github/workflows/ci-cd.yml`)

Six jobs on push/PR to `main`: `lint-and-validate` (markdownlint + Vale) → `build` (`zensical build --strict`) → `agents`, `seo_optimizer`, `alt_text_generator`, and `deploy` all run in parallel, each only depending on `build`, so a flagged issue in any agent never blocks a Pages deployment.

- **`agents`** (consistency checker), **`seo_optimizer`**, and **`alt_text_generator`** each run their respective `agents/run_*.py` script with `continue-on-error: true` (the script exits non-zero when issues are found — that's expected, not a workflow failure). All three are gated by `dorny/paths-filter` (only run if `docs/**`, `reference/**`, or `agents/**` changed, to conserve Groq API calls) and skip gracefully on fork PRs (`GROQ_API_KEY` is withheld by GitHub for those). On a same-repo run with the secret missing, each fails fast with a clear error instead of silently no-op'ing. Each posts its rendered Markdown to `$GITHUB_STEP_SUMMARY` and uploads its JSON report as a build artifact — `agents` reads `agent-qa-report.md`/`.json` (named via `agents.yaml`'s `output.artifact_name`); `seo_optimizer` reads the hardcoded `agent-seo-report.md`/`.json`; `alt_text_generator` reads the hardcoded `agent-alt-text-report.md`/`.json`. Rename `artifact_name` in `agents.yaml` and update the workflow's hardcoded filenames to match if you change it. All three are report-only (post a summary + artifact for manual review) — none auto-fixes or auto-commits anything.
- The alt text generator (`agents/run_alt_text_generator.py`) runs in the `alt_text_generator` job, added mirroring the other two agent jobs.
