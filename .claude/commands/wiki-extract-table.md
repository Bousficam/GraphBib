---
description: Drive a systematic-review data extraction in a project folder (contexte.md, instructions.md, template, articles, output). Analyzes the template, debriefs with the user, persists clarifications to instructions.md, runs deterministic + LLM extraction into TWO outputs (detailed + coded), then proposes adaptive refinements based on the extracted data.
argument-hint: "<project-folder>  OR  <template.xlsx>  OR  --from-source <SR-slug>"
---

Run the systematic-review data extraction workflow.

Arguments: $ARGUMENTS

# Project folder convention (preferred)

All literature-review extraction projects live under a single
container directory `project-review/` at the repo root. Each project
is its own sub-folder, **OUTSIDE the wiki / Obsidian vault**:

```
GraphBib/                            ← repo root
├── wiki/                            ← Obsidian vault — UNRELATED to this command
├── raw/, docs/, tools/, …           ← agent infrastructure
└── project-review/                  ← container for all extraction projects
    ├── mibci/                       ← THIS COMMAND operates on a sub-folder
    │   ├── contexte.md              #   project scope (extraction-relevant only)
    │   ├── instructions.md          #   per-column spec (Phase 1 fills this)
    │   ├── template.xlsx            #   2-row template (slug + variable + instruction)
    │   ├── articles/                #   source MD copies (or empty — uses wiki/sources/)
    │   └── output/
    │       ├── extraction-detailed.xlsx  # verbatim + units (audit)
    │       └── extraction-coded.xlsx     # strict per-instruction (publication-ready)
    ├── tms-dose-response/           ← project 2 — independent
    └── dti-biomarkers/              ← project N — independent
```

**The project folder is NOT part of any Obsidian vault.** `wiki/` is
read by Obsidian; `project-review/*/` are pure file system, opened
in Excel / a text editor. The wiki is the agent's knowledge graph
(persistent, shared across projects); each project sub-folder is a
self-contained analytical artifact for ONE specific systematic review.

Bootstrap a fresh project via `/wiki-extract-init <name>` (creates
`project-review/<name>/` + interactive build of contexte.md +
template + instructions.md).

When `$ARGUMENTS` is a folder under `project-review/`, this is the
assumed layout. When it's a single `.xlsx`/`.csv`, the legacy
"one-template, sibling output" mode applies (outputs land alongside
the template, no `contexte.md` / no `instructions.md`).

**Refuse** to operate on a folder that lives inside `wiki/` — that
would conflate the knowledge graph with an extraction artifact.

# Template format (2-row)

| Row | What |
|---|---|
| 1 | Column headers (variable names) |
| 2 | Instructions per column — polymorphic content |
| 3+ | One row per source (slug in first column) |

Row 2 cell content drives extraction:

| Format | Inferred type | Closure | Example |
|---|---|---|---|
| `a \| b \| c` | nominal | **strict** | `RCT \| cohort \| cross-sectional` |
| `a \| b \| c \| ...` | nominal | **open** (novel values flagged) | `RCT \| cohort \| ...` |
| `a, b, other` | nominal | **open** (the `other` token signals openness) | `acute, subacute, other` |
| `a, b, c` (no `...` / `other`) | nominal | **strict** | `acute, subacute, chronic` |
| `0=label, 1=label` | ordinal coded | strict | `0=low, 1=high` |
| `(int)` / `(integer)` / `(count)` / `(n)` | int | — | `(int)` → bare integer, rounds if source decimal |
| `(years)` / `(0-100)` / `(mV)` | float | — | `(years)` → number + unit verbatim |
| Sentence (3+ words) | NL (text or quant) | — | `Fugl-Meyer UE baseline mean, intervention arm only` |
| **Empty** | implicit | — | **Agent ASKS in Phase 1** |

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

This emits JSON with per-column classification: `kind`,
`inferred_type` (int / float / ordinal / nominal / text), `closed`
(strict vs open categorical), `allowed_values`. Process and present
to the user with all four properties visible:

```
Template analyzed: <path>  (N columns, M data rows)

CLEAR — I'll extract these confidently:
  • year             nominal int        (e.g. 2024)
  • n_intervention   type_hint int      (will round if source decimal)
  • baseline_FM      type_hint float    (range 0-66, units stripped in coded output)
  • design           categorical strict  values: [RCT, cohort, cross-sectional]
                                          (no match → coded blank)
  • intervention     categorical open    values: [BCI, TMS, tDCS, ...]
                                          (novel value kept verbatim + flagged)
  • risk_of_bias     categorical strict  codes:  [0=low, 1=some concerns, 2=high]
                                          (returns code in coded output)
  • adherence_rule   nl text             instruction: "% participants completing ≥ 80%
                                          of planned sessions"

NEEDS YOUR CLARIFICATION (empty / ambiguous / closure unclear):
  • adherence_pct    instruction empty — what should I extract?
  • dropout_reasons  instruction "list main reasons" — how many max?
                                          verbatim quotes or paraphrase?
  • intervention     CLOSURE? Currently inferred as OPEN (because of "..."),
                                          but for a strict scoping review
                                          you may want CLOSED. Confirm?
```

For each NEEDS-CLARIFICATION column, ask **a specific, leading
question**. For **closure ambiguity** specifically, ask the user:

  > *"Column `<name>` has the allowed values [a, b, c]. If a paper
  > reports a value not in this list (e.g. 'mixed BCI' or 'sham +
  > standard PT'), should I (1) **strict** — drop the cell in the
  > coded output, OR (2) **open** — keep the novel value verbatim
  > and flag it for you to widen the spec later?"*

Closed-by-default is safer for clean coded output; open-by-default
is safer when the user is exploring a heterogeneous corpus.

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

## Phase 1b — Mid-extraction instruction update protocol

This protocol applies during **both Phase 2 and Phase 3**. When the
extractor encounters a case where the current instruction is
insufficient, it **pauses** before recording the cell and asks the user.

### Triggers (pause required)

1. **Strict categorical — no match**: the article reports a value not
   in the allowed list and the instruction is STRICT (no `| ...`)
2. **Ambiguous instruction for this specific article**: the article
   presents the information in a format not anticipated by the
   instruction (e.g., instruction says "Fixed (Xs)" but the article
   gives a range with a mechanism)
3. **Multiple plausible extractions**: the instruction doesn't specify
   which of two reported values to prefer (e.g., per-arm vs total N)
4. **Instruction gap revealed by data**: the article reports something
   clearly relevant to the column but the instruction doesn't cover it

### Pause format

```
⚠️ Extraction pause — [article-slug], column [col-name]

Article reports: "[verbatim excerpt]"
Current instruction: "[row-2 instruction]"
Issue: [specific description — why the instruction is insufficient]

Options:
  [A] Adapt instruction (applies to ALL future articles):
      Proposed: "[new instruction text]"
  [B] One-off for this article: "[value to use]" (instruction unchanged)
  [C] Mark NR and continue

Choice?
```

### On user response

- **[A]**: Update `template.xlsx` row 2 AND `instructions.md` for that
  column immediately. Use the adapted instruction for the current cell
  and all subsequent articles. Confirm: `✓ Instruction updated — continuing.`
- **[B]**: Record the one-off value verbatim. Continue without touching
  the instruction.
- **[C]**: Record `NR`. Continue.

**Cap**: surface at most **3 pauses per article** to avoid interrupting
every cell. If more than 3 ambiguities arise for one article, batch the
remaining ones and present them after that article's extraction is
complete.

After resolving pauses, **re-persist** the updated instruction to both
`template.xlsx` row 2 and `instructions.md` (a single write per column,
not per article).

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

`--coded` produces a SECOND output where each value is stripped to
the strict per-instruction form. Cell format conventions:

| Column type | Detailed cell | Coded cell |
|---|---|---|
| `(int)` | `12.4 ± 3.1 years \| Table 1 row "Age"` | `12` *(rounded)* |
| `(years)` (float) | `12.4 ± 3.1 years \| Table 1 row "Age"` | `12.4` |
| Categorical strict | `RCT (n=42, blinded) \| Methods §"Study design"` | `RCT` |
| Categorical strict, no match | `controlled clinical trial \| Methods` | *(blank)* |
| Categorical open, no match | `controlled clinical trial \| Methods` | `controlled clinical trial` *(novel, kept)* |
| Ordinal coded | `low risk \| Table 4` | `0` |
| NL | `Free narrative text \| p.7 §"..."` | `Free narrative text` *(passthrough, source suffix stripped)* |

Note the **`| <source location>` suffix on every detailed value**:
the extractor agent always appends where it found the value
(`Table 3`, `Fig 2 caption`, `p.4 §"Demographic characteristics"`,
`Methods §"Statistical analysis"`, …). The coded output strips this
suffix; the detailed output keeps it so you can audit any cell
back to the page.

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
