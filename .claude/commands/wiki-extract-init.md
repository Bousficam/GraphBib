---
description: Bootstrap and interactively build a literature-review extraction project. Creates the folder skeleton (contexte.md, instructions.md, template, articles/, output/), then walks the user through filling contexte.md, co-designing the template (if blank), and authoring column-by-column instructions. Pairs with /wiki-extract-table which runs the extraction.
argument-hint: "<project-name>  [--from-source <SR-slug>]  [--columns col1,col2,...]  [--skeleton-only]"
---

Create and interactively build a fresh extraction project.

Arguments: $ARGUMENTS

# Project folder vs. the wiki — IMPORTANT

GraphBib has **two distinct types of folders**:

| Folder | Purpose | Obsidian? |
|---|---|---|
| `wiki/` (at repo root) | The agent's knowledge graph: sources, concepts, methods, recommendations, questions, syntheses, entities. Read by Obsidian as a vault. | **YES** — opened as an Obsidian vault |
| `<project>-review/` (sibling of wiki/) | Self-contained literature-review extraction project: contexte, instructions, template, articles, output. **NOT part of any Obsidian vault.** | **NO** — pure file system, opened in Excel / a code editor |

This command creates the **project folder**, which is **separate from
the wiki and outside any Obsidian vault**. The wiki keeps its job
(domain knowledge graph). The project folder is a focused
analytical artifact for ONE specific systematic review / literature
review.

# Location

The project folder is created **at the repo root**, as a sibling of
`wiki/`:

```
GraphBib/                        ← repo root
├── wiki/                        ← Obsidian vault (knowledge graph)
├── raw/                         ← source MDs / PDFs
├── docs/, tools/, pdf2md/       ← agent infrastructure
└── <project>-review/            ← THIS COMMAND creates folders here
```

The command **refuses** to create a project inside `wiki/`,
`raw/`, `docs/`, `tools/`, or any other repo top-level directory —
projects are first-class artifacts at the same level as those, not
nested under them.

# What this command creates

```
<project>-review/
├── contexte.md           # narrative scope — agent seeds, user fills
├── instructions.md       # per-column spec — empty preamble, filled by Phase 1
├── template.xlsx         # 2-row template (slug + instruction)
├── articles/             # source MD files (linked or copied from wiki/sources/ later)
└── output/               # extraction outputs land here (empty for now)
```

Naming: if `$ARGUMENTS` does not end in `-review`, append `-review` for
clarity (e.g. `mibci → mibci-review`). Override by passing the exact
folder name.

# Procedure

## Step 1 — Confirm scope

Parse `$ARGUMENTS`:
- First positional argument = project name (e.g. `mibci-stroke`)
- `--from-source <SR-slug>` (optional) — seed the template's data
  rows from the SR's `cites:` list
- `--columns col1,col2,...` (optional) — column set for the template;
  default is the 27-column SR set in `tools/extract_data.py`
- `--skeleton-only` (optional) — skip the interactive build, just
  create the empty files. The user can run Phase 1 of
  `/wiki-extract-table` later to clarify instructions.

Show the plan and ask before creating:

```
Will create: ./<project-name>-review/
  ├── contexte.md   (seeded with research-question prompts)
  ├── instructions.md   (empty preamble)
  ├── template.xlsx   (M columns × N rows)
  │     M = 27 (default SR set) | <count from --columns>
  │     N = 0 (manual) | <count from --from-source cites>
  ├── articles/   (empty)
  └── output/   (empty)
Proceed? [Y/n]
```

If the folder already exists and is non-empty:
- If any of `contexte.md`, `instructions.md`, `template.{xlsx,csv}` exist
  → REFUSE. Ask user to pick a different name or `rm -rf` themselves
  before re-running (don't overwrite their work).
- If folder exists but empty → proceed.

## Step 2 — Create the folder structure

```bash
mkdir -p <project>/articles <project>/output
```

## Step 3 — Seed contexte.md

Write `<project>/contexte.md` with a guided template the user fills:

```markdown
# Project context — <project-name>

> Fill me before running /wiki-extract-table. The extraction agent
> reads this to ground inclusion / exclusion decisions and to
> calibrate its style.

## Research question

(One sentence — the PICO question if clinical, the cause-effect
hypothesis if experimental, the construct under review if theoretical.)

## Inclusion criteria

- Population: ...
- Intervention / Exposure: ...
- Comparator (if applicable): ...
- Outcomes of interest: ...
- Study designs: RCT, cohort, ...
- Date range: YYYY-MM-DD to YYYY-MM-DD
- Languages: en, fr, ...

## Exclusion criteria

- ...

## Notes for the extraction agent

- Domain priors (e.g. *prefer ITT over PP analyses*)
- Style preferences (e.g. *quote dose parameters verbatim*)
- Known caveats (e.g. *MEP amplitude is reported in mV or µV — convert
  to mV*)

## Source list

(Filled by the agent after `--from-source` or manually. One slug per
line, matching `wiki/sources/<slug>.md`.)

- cervera-2020
- khedr-2005
...
```

## Step 4 — Seed instructions.md (empty preamble)

Write `<project>/instructions.md`:

```markdown
# Extraction instructions — <project-name>

> Auto-populated by the `/wiki-extract-table` Phase 1 debrief.
> Each column gets a section with the row-2 terse instruction
> plus narrative detail and edge cases.

(Empty — run `/wiki-extract-table <project>/` to populate.)
```

## Step 5 — Create the template

### Path A — `--from-source <SR-slug>` provided

```bash
python tools/extract_data.py \
    --from-source <SR-slug> \
    -o <project>/template.xlsx \
    --no-spec
```

`--no-spec` skips the legacy INSTRUCTIONS/TYPE/SCALE rows so you get
a clean 2-row format the user fills via Phase 1 debrief.

Pass `--columns` if provided.

### Path B — no --from-source

Create an empty template with just headers + empty row 2:

```python
python tools/extract_data.py --from-source __empty__ -o <project>/template.xlsx --no-spec --columns "<cols>"
```

If that doesn't work (since `__empty__` isn't a real slug), write the
template directly with openpyxl:

```python
python - <<'PY'
from openpyxl import Workbook
cols = ["slug", "year", "design", "n_intervention", "n_control",
        "baseline_outcome", "post_outcome", "p_value", "effect_size",
        "risk_of_bias", "notes"]  # or args.columns split
wb = Workbook()
ws = wb.active
ws.append(cols)        # row 1: variable names
ws.append([""] * len(cols))  # row 2: empty instructions (Phase 1 will fill)
wb.save("<project>/template.xlsx")
PY
```

Default column set (if no `--columns`): the 27-field SR set used by
`extract_data.py --from-source`. Keep it broad — users delete what
they don't need.

## Step 6 — Propose interactive build

After the skeleton is created, **propose** to fill it interactively
right now (default = yes, since this is usually what the user wants).
Ask:

```
✓ Project skeleton created at ./<project>-review/

Build the project now? I can walk you through:
  1. contexte.md   → research question, inclusion criteria, notes
  2. template      → which variables matter for this review
  3. instructions  → what to extract for each variable

[Y / skip — just leave the empty files for me to fill later]
```

If the user **skips**, jump to Step 9 (Final guidance) and stop.

If the user **confirms**, run Steps 7–8 in order.

## Step 7 — Build contexte.md (interactive)

Ask 5 short questions in sequence, ONE AT A TIME, waiting for each
answer before asking the next. Use Q&A style — keep your prompts
SHORT, suggest concrete examples to make answering fast:

```
Q1 — Research question?
    (One sentence. Examples:
      "Does MI-BCI improve upper-limb motor recovery after
       chronic stroke vs sham?"
      "What's the dose-response of low-frequency rTMS over
       contralesional M1?")
```

Wait for answer. Then:

```
Q2 — Inclusion criteria (PICO):
    Population: ?   (e.g. "chronic stroke patients > 6 mo post-onset")
    Intervention: ?  (e.g. "MI-BCI, ≥ 10 sessions")
    Comparator: ?   (e.g. "sham BCI or standard rehab")
    Outcomes: ?     (e.g. "Fugl-Meyer UE primary; ARAT secondary")
    Designs accepted: ?  (e.g. "RCT, controlled trials only")
    Date range: ?   (e.g. "2010-01-01 to today")
    Languages: ?    (e.g. "en, fr")
```

Wait. Then:

```
Q3 — Exclusion criteria?
    (e.g. "case reports, n < 5, paediatric")
```

Wait. Then:

```
Q4 — Domain priors / style notes for the extraction agent?
    (e.g. "Prefer ITT over PP analyses."
          "MEP amplitude reported in mV or µV — always convert to mV."
          "Distinguish acute/subacute/chronic — recovery dynamics
           differ profoundly.")
```

Wait. Then:

```
Q5 — Anything else to record in the context?
    (Notes, deadlines, collaborators, registration ID,
     anything that grounds your decisions later.)
```

Wait for the last answer, then **write all answers** into
`<project>-review/contexte.md`, replacing the seeded placeholders with
the user's prose. Confirm:

```
✓ contexte.md written. Reading it back:
[show the file content, ~30 lines]

Edit / add anything? [n / paste edit]
```

Apply edits if any, then proceed to Step 8.

## Step 8 — Build template + instructions.md (interactive)

### Step 8a — Co-design the template (if it's blank or empty)

Check the template's columns. If the template was created with
`--from-source` or `--columns`, the column set already exists →
skip to Step 8b.

If the template is BLANK (only `slug` column or nothing), co-design:

```
Let's decide which variables you'll extract. The default SR set has
27 columns; you can use it whole, a subset, or start from scratch.

  [a] Use the default SR set (27 columns)
  [b] Pick a category-by-category subset
  [c] Start blank and add one at a time
  [d] Paste a custom list
```

For **[b]**, walk through categories ONE AT A TIME:

```
  Identifiers — slug, first_author, year, journal, doi, country [Y/n]
  Design — study_design, n_total, n_intervention, n_control [Y/n]
  Population — age_mean, sex_pct_female, population, chronicity [Y/n]
  Baseline outcomes — baseline_fm, baseline_<scale> [Y/n]
  Intervention — intervention, intervention_subfamily, n_sessions, session_duration_min [Y/n]
  Outcomes — primary_outcome_delta, p_value, effect_size, confidence_interval [Y/n]
  Safety — adverse_events, dropouts [Y/n]
  Quality — risk_of_bias, trial_registration [Y/n]
  Free-form — notes [Y/n]
```

Aggregate the user's choices into the final column list, write it as
row 1 of the template (leaving row 2 empty — filled in 8b).

For **[c]** or **[d]**, prompt for the column names directly.

### Step 8b — Per-column instructions (one at a time)

For each column (except `slug`), ask the user the instruction.
**Ask one column at a time**, in template order:

```
Column 1 of N — year
  What instruction? (categorical | NL | unit hint | skip)
    Examples:
      Categorical:   "RCT, cohort, cross-sectional"
      NL:            "Publication year, 4 digits"
      Unit hint:     "(YYYY)"
      Skip:          (leave empty — implicit, you'll clarify later)
```

Wait for answer. Echo back to confirm:

```
  → "Publication year, 4 digits"   (kind: nl)
  Confirm? [Y / re-enter]
```

If categorical, the agent validates: "I'll interpret this as the
allowed values `[a, b, c]`. Pick one of these verbatim during
extraction. OK?"

Move to next column. Continue until all columns done.

### Step 8c — Persist to both files

Write the instructions into:
- `template.xlsx` row 2 (terse, machine-readable — exactly what the
  user typed)
- `instructions.md` (long-form, with the column name as `## <name>`
  heading, the row-2 instruction, plus any clarifying detail the
  user added during 8b)

Confirm with a summary:

```
✓ template.xlsx row 2 filled (N columns).
✓ instructions.md written  ({categorical: K, NL: K, empty: K} kinds).
```

## Step 9 — Final guidance

Print:

```
✓ Project ready at ./<project>-review/

To run the extraction:
  /wiki-extract-table <project>-review/

  Phase 1 will re-check the instructions you just authored
  (catches empty / ambiguous columns), then Phase 2 + 3 produce
  output/extraction-{detailed,coded}.xlsx.

To add sources to extract:
  - List the slugs in <project>-review/contexte.md under "Source list"
  - Or copy / link the source MDs into <project>-review/articles/
  - Or leave both empty and extract_data.py reads straight from wiki/sources/
```

# Notes

- The `articles/` folder is a **convenience** — the actual source MD
  files live in `wiki/sources/<...>/<slug>.md` and `extract_data.py`
  finds them there via `load_sources()`. Copying / linking to
  `articles/` is useful only if the user wants a portable project
  folder (e.g. to share with a collaborator who doesn't have the full
  wiki cloned). For solo workflows, leave `articles/` empty —
  extraction reads straight from `wiki/sources/`.

- `output/` is created empty. The slash command `/wiki-extract-table`
  writes there.

- **This command does NOT touch the wiki.** It only creates files
  under `<project>-review/` at the repo root. Removing the project
  folder removes all artifacts; the wiki is unaffected.

- Each review lives in its OWN sibling folder. You can have many
  active reviews (`mibci-review/`, `tms-dose-response-review/`,
  `dti-biomarkers-review/`) — they don't interact, share no state,
  and each has its own `contexte.md` / `instructions.md` /
  `template.xlsx`.

- The project folder is intentionally NOT part of any Obsidian vault.
  Open `template.xlsx` in Excel / LibreOffice / Numbers; open
  `contexte.md` / `instructions.md` in any text editor. Obsidian
  stays focused on the wiki.

# Hard constraints

- **NEVER create the project folder inside `wiki/`** (or any repo
  top-level directory). Projects are siblings of `wiki/`, at the repo
  root. If the user passes a path containing `wiki/`, `raw/`,
  `docs/`, `tools/`, `pdf2md/`, `.claude/`, or `graph/`, REFUSE and
  explain the project / wiki separation.
- **NEVER overwrite an existing `contexte.md`, `instructions.md`, or
  `template.{xlsx,csv}`.** Ask the user to remove the folder manually
  if they want a fresh project.
- **NEVER use a project name that conflicts with a repo top-level
  directory** (`raw`, `wiki`, `pdf2md`, `tools`, `docs`, `.claude`,
  `graph`). Refuse and ask for a different name.
- **NEVER call `extract_data.py --from-source` with a slug not present
  in `wiki/sources/`.** Verify first; if missing, suggest
  `/wiki-batch-ingest` first to ingest the SR.
- **In the interactive build (Steps 7–8): ask ONE question at a time,
  WAIT for the answer, echo back to confirm.** Do not batch 5
  questions into one prompt — that's the failure mode that turns the
  wizard into a wall of text the user skims and skips. The whole
  point of the interactive build is a guided conversation.
- **Allow the user to bail out at any step.** "skip / continue
  later" should always be a valid answer; on bail, fall through to
  Step 9 (Final guidance) and exit cleanly.
