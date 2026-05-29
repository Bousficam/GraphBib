---
description: Bootstrap and interactively build a literature-review extraction project under project-review/. Creates the folder skeleton (contexte.md, instructions.md, template, articles/, output/), then walks the user through filling contexte.md (review type, objective, research question, outcomes, style notes — with dynamic follow-ups for ambiguous answers, e.g. asking about population frame only when the review is clinical), co-designing the template (if blank), and authoring column-by-column instructions. Pairs with /wiki-extract-table which runs the extraction.
argument-hint: "<project-name>  [--from-source <SR-slug>]  [--columns col1,col2,...]  [--skeleton-only]"
---

Create and interactively build a fresh extraction project.

Arguments: $ARGUMENTS

# Project folder vs. the wiki — IMPORTANT

GraphBib has **two distinct types of folders**:

| Folder | Purpose | Obsidian? |
|---|---|---|
| `wiki/` (at repo root) | The agent's knowledge graph: sources, concepts, methods, recommendations, questions, syntheses, entities. Read by Obsidian as a vault. | **YES** — opened as an Obsidian vault |
| `project-review/<name>/` (sibling of wiki/) | Self-contained literature-review extraction project: contexte, instructions, template, articles, output. **NOT part of any Obsidian vault.** | **NO** — pure file system, opened in Excel / a code editor |

This command creates the **project folder**, which is **separate from
the wiki and outside any Obsidian vault**. The wiki keeps its job
(domain knowledge graph). The project folder is a focused
analytical artifact for ONE specific systematic review / literature
review.

# Location

All extraction projects live under a single container directory
`project-review/` at the repo root. Each project is a sub-folder
named after the user's project name:

```
GraphBib/                        ← repo root
├── wiki/                        ← Obsidian vault (knowledge graph)
├── raw/                         ← source MDs / PDFs
├── docs/, tools/, pdf2md/       ← agent infrastructure
└── project-review/              ← container for all extraction projects
    ├── mibci/                   ← project 1 (created by /wiki-extract-init mibci)
    ├── tms-dose-response/       ← project 2
    └── dti-biomarkers/          ← project N
```

The container (`project-review/`) is created on first run if missing.
Each new `/wiki-extract-init <name>` creates a sub-folder
`project-review/<name>/` — keeps the repo root clean, groups all
extraction work under one parent.

The command **refuses** to create a project anywhere else (inside
`wiki/`, `raw/`, `docs/`, `tools/`, or as a sibling of these).
`project-review/<name>` is the only valid path.

# What this command creates

```
project-review/<name>/
├── contexte.md           # narrative scope — agent seeds, user fills
├── instructions.md       # per-column spec — empty preamble, filled by Phase 1
├── template.xlsx         # 2-row template (slug + instruction)
├── articles/             # source MD files (linked or copied from wiki/sources/ later)
└── output/               # extraction outputs land here (empty for now)
```

Naming: the user passes a SHORT name (`mibci`, `tms-dose`,
`dti-biomarkers`) — the agent does NOT append `-review` since the
parent `project-review/` already conveys "this is a review project".
Use kebab-case for multi-word names.

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
Will create: ./project-review/<name>/
  ├── contexte.md   (seeded with extraction-relevant prompts)
  ├── instructions.md   (empty preamble)
  ├── template.xlsx   (M columns × N rows)
  │     M = 27 (default SR set) | <count from --columns>
  │     N = 0 (manual) | <count from --from-source cites>
  ├── articles/   (empty)
  └── output/   (empty)
Proceed? [Y/n]
```

If `project-review/<name>/` already exists and is non-empty:
- If any of `contexte.md`, `instructions.md`, `template.{xlsx,csv}` exist
  → REFUSE. Ask user to pick a different name or `rm -rf` themselves
  before re-running (don't overwrite their work).
- If folder exists but empty → proceed.

## Step 2 — Create the folder structure

```bash
mkdir -p project-review/<name>/articles project-review/<name>/output
```

The container `project-review/` is auto-created if it doesn't exist
yet (first project bootstrap).

## Step 3 — Seed contexte.md

Write `project-review/<name>/contexte.md` with a **minimal** guided template —
only what the extraction agent will actually consume. Inclusion /
exclusion criteria, date ranges, and language filters belong to the
**pre-extraction** screening phase (which papers to include in the
SR) and are NOT consulted during data extraction. Keep contexte.md
focused on what disambiguates extraction calls:

```markdown
# Project context — <project-name>

> Fill me before running /wiki-extract-table. The extraction agent
> reads this to calibrate extraction depth, disambiguate which
> value to extract, sanity-check numerics, and apply your style
> conventions.

## Review type

(systematic / meta-analysis / scoping / narrative / umbrella /
mapping / methodological. Drives extraction stringency — a
meta-analysis needs effect sizes + CIs + per-arm Ns, a scoping
review can be looser.)

## Review objective

(Why this review exists — the broader purpose / contribution.
Different from the research question. Examples:
 "Inform AHA/ESO guideline update on post-stroke motor rehab."
 "Map the methodological heterogeneity of TMS dose-response trials."
 "Identify gaps for an EU H2026 grant proposal.")

## Research question

(One sentence — what this review specifically answers. Used by the
agent to prioritize when a paper reports many candidates for the
"primary" outcome.)

## Primary outcomes of interest

(Which scales / which subscales the review hinges on. Anchors
extraction when the paper reports many variants — e.g.
*Fugl-Meyer Upper Extremity total* vs *FM-UE motor subscale only*.

Skip if the review is methodological / mapping / theoretical and
doesn't compare outcomes across papers.)

## Notes for the extraction agent

- Domain priors (e.g. *prefer ITT over PP analyses*)
- Unit conventions (e.g. *MEP amplitude is reported in mV or µV —
  always convert to mV*)
- Terminology disambiguation (e.g. *"chronic" = ≥ 6 months
  post-stroke*)
- Style preferences (e.g. *quote dose parameters verbatim — never
  paraphrase frequency / intensity / sessions*)
- Effect-size convention (meta-analyses only — *Cohen's d for
  continuous outcomes, log-OR for binary, both with 95% CI*)

## Source list

(Filled by the agent after `--from-source` or manually. One slug per
line, matching `wiki/sources/<slug>.md`.)

- cervera-2020
- khedr-2005
...
```

## Step 4 — Seed instructions.md (empty preamble)

Write `project-review/<name>/instructions.md`:

```markdown
# Extraction instructions — <project-name>

> Auto-populated by the `/wiki-extract-table` Phase 1 debrief.
> Each column gets a section with the row-2 terse instruction
> plus narrative detail and edge cases.

(Empty — run `/wiki-extract-table project-review/<name>/` to populate.)
```

## Step 5 — Create the template

### Path A — `--from-source <SR-slug>` provided

```bash
python tools/extract_data.py \
    --from-source <SR-slug> \
    -o project-review/<name>/template.xlsx \
    --no-spec
```

`--no-spec` skips the legacy INSTRUCTIONS/TYPE/SCALE rows so you get
a clean 2-row format the user fills via Phase 1 debrief.

Pass `--columns` if provided.

### Path B — no --from-source

Create an empty template with just headers + empty row 2:

```python
python tools/extract_data.py --from-source __empty__ -o project-review/<name>/template.xlsx --no-spec --columns "<cols>"
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
wb.save("project-review/<name>/template.xlsx")
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
✓ Project skeleton created at ./project-review/<name>/

Build the project now? I can walk you through:
  1. contexte.md   → research question, inclusion criteria, notes
  2. template      → which variables matter for this review
  3. instructions  → what to extract for each variable

[Y / skip — just leave the empty files for me to fill later]
```

If the user **skips**, jump to Step 9 (Final guidance) and stop.

If the user **confirms**, run Steps 7–8 in order.

## Step 7 — Build contexte.md (interactive)

Ask 5 structured questions ONE AT A TIME, waiting for each answer
before asking the next. Every question is **directly useful to the
extraction agent** — pre-extraction methodology (inclusion/exclusion,
search dates, language filters) is OUT OF SCOPE here, it belongs to
your SR protocol, not to contexte.md.

After the 5 structured questions, **ask 0–5 targeted follow-ups**
based on what's ambiguous or under-specified in the answers (Step 7b).

### Structured questions (always asked, in order)

```
Q1 — Review type?
    (Pick one: systematic / meta-analysis / scoping / narrative /
     umbrella / mapping / methodological. This calibrates extraction
     stringency — see the table below.)

       Type             Stringency / typical template focus
       ─────────────    ────────────────────────────────────────────
       systematic       Strict per-PRISMA; risk of bias mandatory
       meta-analysis    Adds effect size + 95% CI + per-arm N + heterogeneity
       scoping          Broader, descriptive; less stringent on outcomes
       narrative        Thematic synthesis; loose template
       umbrella         Review-of-reviews; metadata-heavy
       mapping          Methodological landscape; design + outcomes focus
       methodological   Tool / scale evaluation; psychometric data
```

Wait for answer. Then:

```
Q2 — Review objective?
    (Why this review exists — the broader purpose / contribution.
     Different from the research question.

     Examples:
      "Inform AHA/ESO guideline update on post-stroke motor rehab."
      "Map the methodological heterogeneity of TMS dose-response trials."
      "Identify gaps for an EU H2026 grant proposal.")
```

Wait. Then:

```
Q3 — Research question?
    (One sentence — what this review specifically answers. The agent
     uses it to prioritize when a paper reports many candidates for
     the "primary" outcome.

     Examples:
      "Does MI-BCI improve upper-limb motor recovery after chronic
       stroke vs sham?"
      "What's the dose-response of low-frequency rTMS over
       contralesional M1?")
```

Wait. Then:

```
Q4 — Primary outcomes of interest?
    (Which scales / subscales the review hinges on. Anchors
     extraction when the paper reports many variants.

     If your review is methodological / mapping / theoretical and
     does NOT compare outcomes across papers, just say "n/a — this
     review doesn't extract outcomes" and the agent will skip
     outcome-related follow-ups.

     Examples (when applicable):
      "Fugl-Meyer UE total score (0-66), not the motor or sensation
       subscales separately."
      "MEP amplitude peak-to-peak in mV; latency in ms — both from
       contralesional M1 stimulation only.")
```

Wait. Then:

```
Q5 — Domain priors / style notes for the extraction agent?
    (Unit conventions, ITT vs PP preference, terminology
     disambiguation, effect-size conventions (meta-analyses),
     anything else the agent should know to do consistent extraction.

     Examples:
      "Prefer ITT over PP analyses."
      "MEP amplitude reported in mV or µV — always convert to mV."
      "Distinguish acute / subacute / chronic — recovery dynamics
       differ profoundly."
      "Cohen's d for continuous outcomes, log-OR for binary; always
       report 95% CI." (if meta-analysis)
      "Quote dose parameters verbatim — never paraphrase frequency,
       intensity, or session count.")
```

### Step 7b — Targeted follow-up questions (dynamic)

After Q1–Q5 are answered, **review the answers together** and ask
0–5 follow-ups for whatever is still ambiguous or under-specified.
DO NOT ask follow-ups gratuitously — only when an answer leaves a
real extraction decision unclear.

Examples of when to ask follow-ups (with the actual phrasing):

- **Q1 = meta-analysis but no effect-size metric mentioned in Q5**
  → *"You said meta-analysis. Which effect size do you want extracted
  — Cohen's d, Hedges' g, log-OR, RR, or raw mean difference? Each
  needs different ancillary variables in the template."*

- **Q4 primary outcome is a multi-component scale, no subscale specified**
  → *"FM-UE — total score (0–66), motor subscale only (0–60), or
  motor + sensation? Papers report all three; pick now to avoid
  per-cell ambiguity."*

- **Q3 implies a clinical population but no sanity-check anchor given**
  → *"For numerical sanity checks: who's the population? E.g. age
  range, condition severity. Helps the agent flag impossible values
  (a baseline age of 8 in a chronic-stroke study, an MEP of 200 mV).
  Skip if non-clinical."*

- **Q1 = scoping but Q5 mentions ITT preference**
  → *"Scoping reviews usually don't extract analysis-arm details.
  Skip ITT/PP for this review, or keep it as an optional column?"*

- **Q5 has nothing about timepoint / follow-up**
  → *"Many papers report outcomes at multiple timepoints (end of
  treatment, 1 mo follow-up, 6 mo). Which timepoint anchors your
  primary outcome — extract latest, end-of-treatment, or specific
  follow-up?"*

- **Q3 mentions a comparator that hints at a complex design**
  → *"You mentioned 'sham BCI' — do you also accept active controls
  (e.g. standard PT)? If so, the extraction should distinguish
  sham vs active-control comparators."*

Each follow-up is a single targeted question. Wait for the answer
before asking the next. Cap at 5 total — if you have more concerns,
say so once at the end as a note ("Other potential ambiguities to
revisit: …") rather than running a long interrogation.

### Step 7c — Persist

When all questions answered (structured + follow-ups), **write all
answers** into `project-review/<name>/contexte.md`, replacing the
seeded placeholders with the user's prose. Confirm:

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
✓ Project ready at ./project-review/<name>/

To run the extraction:
  /wiki-extract-table project-review/<name>/

  Phase 1 will re-check the instructions you just authored
  (catches empty / ambiguous columns), then Phase 2 + 3 produce
  output/extraction-{detailed,coded}.xlsx.

To add sources to extract:
  - List the slugs in project-review/<name>/contexte.md under "Source list"
  - Or copy / link the source MDs into project-review/<name>/articles/
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
  under `project-review/<name>/` at the repo root. Removing the project
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

- **ALWAYS create the project under `project-review/<name>/`.** Never
  at the repo root, never inside `wiki/`, `raw/`, `docs/`, `tools/`,
  `pdf2md/`, `.claude/`, or `graph/`. If the user passes a path with
  a slash in it (e.g. `project-review/foo` or `wiki/bar`), strip
  everything except the basename and use that as `<name>`. If the
  resulting name is empty or invalid, refuse and ask.
- **NEVER overwrite an existing `contexte.md`, `instructions.md`, or
  `template.{xlsx,csv}`** inside the target sub-folder. Ask the user
  to remove `project-review/<name>/` manually if they want a fresh
  project.
- **NEVER use a project name that conflicts with a reserved name**
  (`articles`, `output`, `contexte`, `instructions`, `template`,
  `log`) — these are sub-artifact names inside each project. Refuse
  and ask for a different name.
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
