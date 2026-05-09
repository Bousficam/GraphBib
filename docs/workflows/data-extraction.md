# Data Extraction (systematic review tables)

`tools/extract_data.py` populates a SR data-extraction table (Excel
`.xlsx` or CSV) from `wiki/sources/`. Three filling layers applied per
cell, in order:

1. **Frontmatter** (always on) — known column headers map to YAML
   fields (title, authors, year, doi, study_design, …).
2. **Body regex** (always on) — built-in patterns for clinical fields
   (n per arm, age mean, baseline FM, ΔFM, p-value, Cohen's d, CI,
   trial-registration ID, …).
3. **LLM** (`--llm`) — for cells still empty AND with a per-column
   rule provided in an `INSTRUCTIONS` row, calls Claude via litellm.
   Cached in `tools/.cache/extract_llm.json`.

Cells already populated by the user are never overwritten.

## Spec rows (INSTRUCTIONS / TYPE / SCALE)

Three rows above the data describe each column. The slug cell of each
spec row contains the marker (`INSTRUCTIONS`, `TYPE`, `SCALE`):

```
slug          | year         | risk_of_bias                     | design
INSTRUCTIONS  | Pub year     | Cochrane RoB 2 overall           | Study design
TYPE          | quantitative | ordinal                          | nominal
SCALE         | (YYYY)       | 0=low, 1=some concerns, 2=high   | RCT, cohort, cross-sectional
cervera-2020  |              |                                  |
```

- **INSTRUCTIONS** — natural-language extraction rule per column.
- **TYPE** — `quantitative` | `ordinal` | `nominal` | `text`.
- **SCALE** — quantitative: unit hint `(years)`; ordinal/nominal coded
  `0=low, 1=high` (LLM returns the code); enum `RCT, cohort` (LLM
  returns one verbatim); text: leave empty.

The tool validates extracted values against TYPE/SCALE; mismatches are
flagged in stderr and counted as `invalid` in the run summary.

`--from-source` inserts the three rows pre-filled with sensible
defaults for the SR column set; edit them in Excel before running
`--llm`. Skip with `--no-spec`.

## Modes

```bash
# Pre-fill a NEW template from a SR's cites: (writes an INSTRUCTIONS row by default)
python tools/extract_data.py --from-source cervera-2020 -o cervera-ext.xlsx

# Fill an existing template (frontmatter + regex)
python tools/extract_data.py cervera-ext.xlsx

# Same + LLM fallback for unfilled cells (default Haiku, ANTHROPIC_API_KEY)
python tools/extract_data.py cervera-ext.xlsx --llm

# Force Sonnet for trickier extraction:
LLM_MODEL=claude-sonnet-4-6 python tools/extract_data.py cervera-ext.xlsx --llm
```

**Model tiers**: `LLM_MODEL_FAST` (Haiku) vs `LLM_MODEL` (Sonnet).

Default SR column set and recognized header aliases live at the top of
`tools/extract_data.py` (`DEFAULT_SR_COLUMNS`, `FM_MAP`,
`BODY_PATTERNS`). Extend the ontology there for domain-specific fields.

The agent should run this tool on user request, summarize the per-cell
method counts (frontmatter / regex / llm / manual / empty) and the
per-row status (complete / partial / empty / not_found), and surface
which columns remained empty so the user knows what to fill manually.

For batch-filling rows of an extraction Excel/CSV with stricter quality
than `--llm`, delegate to the `extractor` sub-agent (one cell at a
time, type/scale validated).
