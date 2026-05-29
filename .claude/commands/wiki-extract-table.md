---
description: Drive a systematic-review data extraction from a user-prepared 2-row template. The agent analyzes the template, debriefs with the user about ambiguous columns, then runs the extraction (deterministic → LLM) into a sibling file.
argument-hint: "<template.xlsx>  OR  --from-source <SR-slug>"
---

Run the systematic-review data extraction workflow.

Arguments: $ARGUMENTS

# Template format (NEW — 2-row)

A template is an Excel (or CSV) file with **2 header rows** + one row
per source:

| Row | What | Example |
|---|---|---|
| 1 | Column headers — variable names | `slug`, `year`, `n_intervention`, `risk_of_bias`, `baseline_FM` |
| 2 | **Instructions** per column — categorical scale, natural-language rule, or empty for implicit variables | (see below) |
| 3+ | One row per source (slug in the first column) | `cervera-2020`, `khedr-2005`, … |

Row 2 cell content drives how the agent extracts each column:

| Row-2 content | Interpretation | Example |
|---|---|---|
| `value \| value \| value` | **Categorical** with these allowed values (the agent picks one verbatim) | `low \| some concerns \| high` |
| `value, value, value` (short tokens) | **Categorical** comma-separated | `RCT, cohort, cross-sectional, case-series` |
| `0=label, 1=label, 2=label` | **Coded ordinal** (the agent returns the code) | `0=low, 1=some concerns, 2=high` |
| `(unit)` or `(range)` | **Quantitative type hint** | `(years)`, `(0-100)` |
| Sentence (3+ words) | **Natural-language instruction** — the agent reads the source and applies the rule | `Fugl-Meyer UE baseline mean, intervention arm only` |
| **Empty** | **Implicit variable** — the agent will ASK what to extract during debrief | (e.g. `adherence_pct` with no instruction) |

The legacy 4-row format (INSTRUCTIONS / TYPE / SCALE markers in the
slug column) is still supported for backward compatibility — same
flow below, omit `--instructions-row` and let the script auto-detect.

# Procedure

## Phase 0 — Locate or bootstrap the template

Two paths:

**A. The user already prepared a template.** Confirm the path
(`$ARGUMENTS` should be the .xlsx / .csv). Proceed to Phase 1.

**B. The user passed `--from-source <SR-slug>`.** Pre-fill a starter
template from the SR's `cites:`:

```bash
python tools/extract_data.py --from-source <SR-slug> -o <SR-slug>-extraction.xlsx --no-spec
```

The `--no-spec` flag omits the legacy INSTRUCTIONS / TYPE / SCALE
rows so the user gets a clean 2-row template they fill in. Surface
the path, ask the user to edit row 2 in Excel, then re-invoke
`/wiki-extract-table <path>` to proceed.

## Phase 1 — Comprehension debrief (the gate)

```bash
python tools/extract_data.py <template> --analyze --instructions-row 1
```

This emits JSON describing each column:

```
columns: [
  {name, instruction, kind: categorical|nl|empty|type_hint,
   inferred_type, allowed_values}
]
```

Process the JSON and present a grouped summary to the user:

```
Template analyzed: <path>  (N columns, M data rows)

CLEAR — I'll extract these confidently:
  • <name>     (kind: categorical, values: [a, b, c])
  • <name>     (kind: nl, instruction: "<verbatim>")
  • <name>     (kind: type_hint, will return numeric with units)

NEEDS YOUR CLARIFICATION (empty or ambiguous instruction):
  • <name>     instruction is empty — what should I extract?
  • <name>     instruction "<X>" is short/vague — confirm meaning?
```

For each NEEDS-CLARIFICATION column, ask **a specific, leading
question** so the user can answer concisely:

- *"`adherence_pct` is empty. (a) % participants completing the
  protocol, (b) % sessions completed of planned, or (c) something
  else?"*
- *"`cost` is empty. Direct medical cost only or societal? In what
  currency, base year?"*
- *"`dropout_reasons` says 'list main reasons'. Maximum how many?
  Verbatim quotes or paraphrase? Include `n` per reason?"*

**WAIT** for the user to answer every clarification. Then propose
to update the template's row 2 in-place with the clarified
instructions:

```
I'll add these instructions to the template's row 2:
  adherence_pct      → "% participants who completed ≥ 80% of planned sessions"
  cost               → "Direct medical cost only, in 2020 USD"
  dropout_reasons    → "Top 3 reasons verbatim, with n per reason"
Confirm? [Y/n]
```

On confirm, edit those cells in the template file (just row 2 for
those columns) so the next phases have proper instructions. Tell
the user the template now reflects the agreed spec and is reusable
for the next extraction.

## Phase 2 — Deterministic extraction (free, 0 tokens)

```bash
python tools/extract_data.py <template> --instructions-row 1
```

Frontmatter + body-regex pass. Writes to `<template-stem>-filled.<ext>`
**next to the template** (the template stays as a reusable spec).
Reports:

```
✓ <stem>-filled.xlsx written  (template preserved at <stem>.xlsx).

Per-row status:    complete: K | partial: K | empty: K | not_found: K
Per-cell method:   frontmatter: K | regex: K | manual: K | empty: K | invalid: K
```

If `empty` is small (<10% of cells), suggest filling the rest by
hand and stop. Otherwise propose Phase 3.

## Phase 3 — LLM extraction (opt-in, costs tokens)

```bash
python tools/extract_data.py <template> --llm --instructions-row 1
```

For each remaining empty cell with a non-empty instruction, the
script delegates to the `extractor` sub-agent (haiku — ~10× cheaper
than sonnet). The sub-agent reads the source MD, applies the
instruction with TYPE / SCALE awareness (inferred from row-2 content
per Phase 1's classification), and returns one validated value or
`not reported`.

Results cached in `tools/.cache/extract_llm.json` keyed by
(slug, column, instruction-hash) so re-runs on unchanged instructions
are free.

## Phase 4 — Recap

Print final counts and the output path. Suggest:

```
Extraction written to <stem>-filled.xlsx (M of N cells filled).

K cells empty after all phases — likely "not reported" in source.
Spot-check before publishing.

Reusable spec at <stem>.xlsx — re-run /wiki-extract-table <stem>.xlsx
to update with new sources you add to the SR's cites:.
```

# Hard constraints

- **NEVER skip Phase 1.** The comprehension gate is the whole point
  of this workflow. Even if all instructions look clear, present the
  classification summary and ask "anything to clarify before I
  extract?".
- **NEVER overwrite the template.** Output goes to a sibling
  `<stem>-filled.<ext>` file. The template is the user's reusable
  spec.
- **NEVER write fake values.** If the LLM can't find the answer,
  the cell stays empty (or holds the literal `not reported`). No
  paraphrasing to fit a scale.
- **For Implicit (empty-instruction) columns: refuse to extract
  without explicit user clarification.** Don't guess from the column
  name alone — `tms_sessions` could mean count, list of frequencies,
  or duration per session.
