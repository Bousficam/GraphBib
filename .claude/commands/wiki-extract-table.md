---
description: Build a SR data-extraction Excel from a review's cites — pre-fill template, run frontmatter+regex extraction, optionally loop the extractor sub-agent for cells the regex missed.
argument-hint: "<SR-slug> [output.xlsx]"
---

Generate and populate a systematic-review data-extraction table.

Arguments: $ARGUMENTS

- The first argument is `<SR-slug>` — the slug of a review/meta-analysis
  source page in the wiki whose `cites:` frontmatter lists the papers
  to extract from (e.g. `cervera-2020`).
- The second argument, if provided, is the output filename. Default:
  `<SR-slug>-extraction.xlsx`.

# Procedure

## Phase 1 — Pre-fill template from the SR's cites

```bash
python tools/extract_data.py --from-source <SR-slug> -o <output>
```

This walks the SR's `cites:`, writes one row per cited paper that
exists in the wiki, with the default 27-column SR set. Inserts three
spec rows (INSTRUCTIONS / TYPE / SCALE) with sensible defaults.

Surface to the user:
*"Pre-filled `<output>` with N rows. Open it in Excel, edit the
INSTRUCTIONS / TYPE / SCALE rows to match your SR question, then
return here for Phase 2."*

Wait for user confirmation before proceeding.

## Phase 2 — Frontmatter + body regex pass (free)

```bash
python tools/extract_data.py <output>
```

Fills cells from frontmatter (deterministic, ~25 % of cells) and
body regex (~30 % more). Cells already populated by the user are
preserved. Reports per-cell method counts.

## Phase 3 — LLM pass for unfilled cells (opt-in)

If significant cells remain empty AND the INSTRUCTIONS rows are
filled, ask:

```
N cells are still empty. Run --llm to fill them via Claude (Haiku
default, ~$0.05–0.20 per paper for 25 columns)? [Y/n]
```

If yes:

```bash
python tools/extract_data.py <output> --llm
```

The tool sends the body (cached per paper) + per-column instruction
to the LLM, validates against TYPE/SCALE, writes the result.

## Phase 4 — Reports

Surface:

```
=== /wiki-extract-table — <date> ===

Output: <output>
N papers, M columns

Per-cell method:
  frontmatter: <a>
  regex: <b>
  llm: <c>
  manual (preserved): <d>
  empty: <e>
  invalid (validation failed): <f>

Per-row status:
  complete: <P>
  partial: <Q>
  empty: <R>
  not_found in wiki: <S>

Cells flagged invalid (manual review needed):
  - <slug> / <column>: <reason>
  - …

Open <output> in Excel for manual review of empty / invalid cells.
```

# Notes

- For a one-off extraction of a specific cell, delegate to the
  `extractor` sub-agent directly (no need to set up a full table).
- The default SR column set covers most clinical RCT extractions
  (design, N per arm, demographics, intervention, outcomes, effect
  sizes, RoB). For domain-specific fields, edit
  `DEFAULT_SR_COLUMNS` / `DEFAULT_SR_TYPES` / `DEFAULT_SR_SCALES`
  at the top of `tools/extract_data.py`.
- For papers not in your wiki: ingest them first via
  `/wiki-batch-ingest` (or `/wiki-discover` to fetch first).
