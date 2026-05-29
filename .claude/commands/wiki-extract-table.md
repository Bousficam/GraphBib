---
description: Drive a systematic-review data extraction in a project folder (contexte.md, instructions.md, template, articles, output). Analyzes the template, debriefs with the user, persists clarifications to instructions.md, runs deterministic + LLM extraction into TWO outputs (detailed + coded), then proposes adaptive refinements based on the extracted data.
argument-hint: "<project-folder>  OR  <template.xlsx>  OR  --from-source <SR-slug>"
---

Run the systematic-review data extraction workflow.

Arguments: $ARGUMENTS

# Project folder convention (preferred)

A literature-review project lives in its own folder:

```
my-mibci-review/
├── contexte.md          # Project scope: research question, inclusion criteria, dates
├── instructions.md      # Per-column extraction spec (agent-authored from Phase 1)
├── template.xlsx        # 2-row Excel template (slug + variable + instruction)
├── articles/            # Source markdown files (or symlinks to raw/papers/)
└── output/
    ├── extraction-detailed.xlsx   # Verbatim values with units / quotes
    └── extraction-coded.xlsx      # Strict per-instruction format (publication-ready)
```

When `$ARGUMENTS` is a folder, this is the assumed layout. When it's a
single `.xlsx`/`.csv`, the legacy "one-template, sibling output" mode
applies (outputs land alongside the template, no `contexte.md` / no
`instructions.md`).

# Template format (2-row)

| Row | What |
|---|---|
| 1 | Column headers (variable names) |
| 2 | Instructions per column — polymorphic content |
| 3+ | One row per source (slug in first column) |

Row 2 cell content drives extraction:

| Format | Interpretation |
|---|---|
| `a \| b \| c` | Categorical — pick verbatim |
| `a, b, c` (short tokens) | Categorical — comma-separated |
| `0=lo, 1=hi` | Ordinal coded — return the code |
| `(years)` / `(0-100)` | Quantitative type hint |
| Sentence (3+ words) | Natural-language instruction |
| **Empty** | **Implicit variable** — agent ASKS in Phase 1 |

# Procedure

## Phase 0 — Bootstrap or locate the project

**A. `$ARGUMENTS` is a folder path** — use as project root. Confirm it
contains `template.xlsx` (or .csv). If `contexte.md` exists, read it
to ground domain assumptions. If `instructions.md` exists, treat it
as the source of truth for column instructions (may override row 2 of
the template after a mismatch check).

**B. `$ARGUMENTS` is a template file** — legacy single-file mode. The
template path is the spec; outputs land alongside; no
`contexte.md` / `instructions.md` involvement.

**C. `$ARGUMENTS` starts with `--from-source <SR-slug>`** — bootstrap
a new project folder:

```bash
mkdir -p <SR-slug>-review/{articles,output}
python tools/extract_data.py --from-source <SR-slug> -o <SR-slug>-review/template.xlsx --no-spec
```

Then prompt the user to fill row 2 (or skip and let Phase 1 handle
empty instructions interactively), and re-invoke
`/wiki-extract-table <SR-slug>-review/`.

## Phase 1 — Comprehension debrief (the gate)

```bash
python tools/extract_data.py <template> --analyze --instructions-row 1
```

This emits JSON with per-column classification. Process and present:

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
question** so the user can answer concisely (see examples in the
old slash command if helpful: dropout reasons, adherence, costs).

**WAIT** for user answers. Then propose to:
1. Update the template's row 2 in-place with the clarified instructions
2. Write/update `instructions.md` in the project root with the
   detailed clarifications (long-form, narrative, edge cases)

```
I'll update:
  • template.xlsx row 2 (short, machine-readable)
  • instructions.md   (long, human-readable, narrative)

Confirm? [Y/n]
```

On confirm, edit both files. The template's row 2 stays terse; the
instructions.md captures the WHY of each decision plus edge cases
the user mentioned. Format for `instructions.md`:

```markdown
# Extraction instructions — <project name>

> Updated YYYY-MM-DD by the extraction agent.

## adherence_pct
**Row-2 instruction**: % participants who completed ≥ 80% of planned sessions

**Detail**: Look for "adherence", "compliance", "completion rate" in the
Methods or Results. If the paper reports completion of sessions rather
than participants, infer participant-level adherence as the lowest
session-completion threshold. If only "X dropped out" is reported,
compute (N - X) / N × 100.

**Edge cases**: Per-protocol vs intention-to-treat — prefer ITT.

## cost
...
```

This file becomes the durable spec — version-controlled, editable,
and survives template re-generation.

## Phase 2 — Deterministic extraction (free, 0 tokens)

```bash
python tools/extract_data.py --project <folder> --instructions-row 1
# OR for single-file mode:
python tools/extract_data.py <template> --instructions-row 1 --coded
```

`--project` mode automatically:
- Reads the template at `<folder>/template.xlsx`
- Writes `extraction-detailed.xlsx` to `<folder>/output/`
- ALSO writes `extraction-coded.xlsx` (strict per-instruction format)

`--coded` produces a SECOND output where:
- Categorical cells hold the canonical label only (e.g. `RCT` not `RCT (n=42, blinded)`)
- Ordinal-coded cells hold the integer code (e.g. `0` for "low risk")
- Quantitative cells strip units (e.g. `12.4` not `12.4 ± 3.1 years`)
- NL cells pass through unchanged

The detailed version is for audit / spot-checking. The coded version
is what you feed to R / Python / Excel pivot tables.

Reports per-cell method counts; if many cells stay empty (>30%),
suggest Phase 3.

## Phase 3 — LLM extraction (opt-in, costs tokens)

```bash
python tools/extract_data.py --project <folder> --instructions-row 1 --llm
```

Per-cell delegation to the `extractor` sub-agent for empty cells with
a non-empty instruction. Both outputs (detailed + coded) are rewritten
with the LLM fills.

LLM cache: keyed by (slug, column, instruction-hash); re-runs on
unchanged instructions are free.

## Phase 4 — Recap and audit

Print:

```
Extraction summary
  Detailed: <folder>/output/extraction-detailed.xlsx (M of N cells filled)
  Coded:    <folder>/output/extraction-coded.xlsx    (strict format)

Per-cell method:
  frontmatter: K | regex: K | llm: K | manual: K | empty: K | invalid: K
```

Spot-check guidance: open both files side by side, compare a few rows
to catch any mis-coding (a categorical value that didn't match any
allowed label will appear blank in the coded file — that's the signal
to refine the instruction).

## Phase 5 — Adaptive refinement proposals (the new feedback loop)

**Read the detailed output and look for patterns** that suggest the
column spec should evolve:

### Triggers to surface

1. **Variable should be added** — when the same kind of information
   appears in many sources but no column captures it.
   - *"7/12 papers report a baseline NIHSS but you have no `baseline_nihss`
     column. Add it?"*

2. **Variable should be split** — when one column accumulates
   heterogeneous content.
   - *"`intervention_dose` values include frequency (Hz), intensity (%),
     and session count mixed. Split into `frequency_hz`, `intensity_pct`,
     `n_sessions`?"*

3. **Instruction needs refinement** — when extraction is inconsistent.
   - *"`follow_up_duration` has 4 cells in weeks, 3 in months, 2 in
     'end of treatment'. Refine to 'weeks only, convert if needed' and
     re-extract?"*

4. **Allowed-values mismatch** — when a categorical column has cells
   blank in the coded output but populated in the detailed.
   - *"`design`: 'controlled clinical trial' in [kim-2018] didn't match
     any allowed value. Add 'CCT' to the scale, or refine
     [kim-2018]'s extraction?"*

5. **Many `not reported`** — when extraction success rate < 30% for a
   column.
   - *"`adverse_events`: 9 of 12 cells are 'not reported'. Is this column
     answerable from this corpus, or should the instruction be relaxed
     ('any safety info, even narrative')?"*

### Procedure

After Phase 4, scan the detailed output. For each trigger, surface
ONE proposal as a question; cap the total at 5 proposals per run to
avoid overload.

```
Adaptive refinement proposals (5 max):

1. ADD COLUMN  baseline_nihss
   Found in 7/12 sources, no column captures it.
   Confirm? [Y/n]

2. SPLIT COLUMN  intervention_dose
   Current values mix freq + intensity + sessions.
   Propose split into: frequency_hz | intensity_pct | n_sessions
   Confirm? [Y/n]

3. REFINE  follow_up_duration
   Current row-2: "follow-up timepoint"
   Proposed:    "follow-up duration in WEEKS (convert from months: ×4.345)"
   Confirm? [Y/n]
```

On each `Y`:
- For ADD: append column to template row 1, leave row 2 empty so the
  next Phase 1 catches it for clarification
- For SPLIT: replace one column with N new ones, copy verbatim values
  across, mark row 2 as "needs clarification"
- For REFINE: update template row 2 + `instructions.md` for that
  column; re-run Phase 2/3 only for that column

Append the decisions to `<folder>/log.md` (audit trail).

# Hard constraints

- **NEVER skip Phase 1.** Even if the template's row 2 looks complete,
  surface the classification summary and ask "anything to clarify?".
- **NEVER overwrite the template.** Outputs go to `output/` (project
  mode) or sibling files (single-file mode).
- **NEVER auto-apply adaptive proposals.** Each ADD / SPLIT / REFINE
  requires explicit user `Y`.
- **NEVER write fake values.** Empty cell or literal `not reported`.
  Never paraphrase to fit a scale.
- **Implicit (empty-instruction) columns: refuse to extract** until
  Phase 1 clarifies.

# Files written by this workflow

| File | When | Editable by user? |
|---|---|---|
| `template.xlsx` row 2 | After Phase 1 confirmation | Yes — re-run triggers re-debrief |
| `instructions.md` | After Phase 1 confirmation | Yes — long-form spec |
| `output/extraction-detailed.xlsx` | Phase 2 + 3 | No — regenerated each run |
| `output/extraction-coded.xlsx` | Phase 2 + 3 | No — regenerated each run |
| `log.md` | Phase 5 decisions | Append-only audit trail |
| `contexte.md` | Bootstrap (not auto-managed) | Yes — narrative scope |
