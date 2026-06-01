---
description: Bootstrap the screening sub-folder of an existing extraction project and interactively build PICO + inclusion/exclusion criteria in `screening/criteria.md`. Creates the screening/ skeleton (criteria.md, identified/, 1st-pass/, reports/) if absent, then walks the user through PICO and criteria one element at a time. Pairs with `/wiki-screen-tiab` (PRISMA pass 1) and `/wiki-screen-fulltext` (PRISMA pass 2).
argument-hint: "<project-name>  [--skeleton-only]"
---

Bootstrap the screening phase of a literature-review project.

Arguments: $ARGUMENTS

# Where this lives

The screening phase is a sub-folder INSIDE an existing project under
`project-review/`:

```
project-review/<name>/
├── contexte.md                          # shared by screening + extraction
├── log.md                               # shared audit trail
├── screening/                           ← THIS COMMAND populates this
│   ├── criteria.md                      # PICO + IN/OUT criteria (built here)
│   ├── identified/                      # raw CSV exports (user drops them in)
│   ├── 1st-pass/{raw,markdown}/         # downloaded after pass 1
│   └── reports/                         # PRISMA flowchart + per-pass reports
└── extraction/                          # already-existing extraction phase
```

If `project-review/<name>/` does not exist yet, refuse and tell the
user to run `/wiki-extract-init <name>` first (which now creates the
full project including the empty `screening/` folder).

# What this command does

1. Verifies the project root exists.
2. Creates the `screening/` skeleton if missing.
3. Walks the user interactively through PICO + criteria.
4. Writes `screening/criteria.md`.
5. Tells the user how to drop their identified-records CSVs and what
   to run next.

# Procedure

## Step 1 — Resolve and verify the project

Parse `$ARGUMENTS`:
- First positional argument = project name (e.g. `mibci`)
- `--skeleton-only` (optional) — create empty files only, skip the
  interactive build

If the project name is empty, refuse and ask.

Build path `project-review/<name>/` and check it exists. If not:

```
✗ project-review/<name>/ does not exist.
  Run /wiki-extract-init <name> first to bootstrap the full project,
  then re-run /wiki-screen-init <name>.
```

If `screening/criteria.md` already exists and is non-empty, ASK
before overwriting:

```
screening/criteria.md already has content. Options:
  [edit]   Walk through it section by section, keep what's there
  [redo]   Discard and start over
  [skip]   Leave it alone, just create missing folders
```

## Step 2 — Create the skeleton

```bash
mkdir -p project-review/<name>/screening/identified \
         project-review/<name>/screening/1st-pass/raw \
         project-review/<name>/screening/1st-pass/markdown \
         project-review/<name>/screening/reports
```

Seed `screening/1st-pass/missing.md` (empty list — filled by
`/wiki-screen-tiab` when fetch_oa fails):

```markdown
# Articles included at T/A but not retrievable

> Filled by `/wiki-screen-tiab` after the auto-fetch pass. One row per
> included article whose PDF could not be downloaded (paywall,
> closed repository, dead link). Drop the PDF manually into
> `screening/1st-pass/raw/<slug>.pdf` when you locate it; the
> `/wiki-screen-fulltext` command will pick it up.

| Slug | DOI / PMID | Title | Where to try | User note |
|---|---|---|---|---|
```

Seed `screening/criteria.md` with the guided template
(below, Step 3 writes it).

If `--skeleton-only`, jump to Step 5.

## Step 3 — Interactive PICO + criteria build

Ask questions ONE AT A TIME. Wait for each answer. Echo it back to
confirm before moving on. Cap at 12 turns; bail out gracefully if the
user says `skip`.

### Q1 — Population

```
Q1 — Population / Participants
  Who is the unit of analysis? Be specific:
   - condition (e.g. "ischemic stroke", "GBM glioma", "MDD")
   - severity / stage (e.g. "moderate to severe", "newly diagnosed")
   - age range (adults / pediatric / both)
   - exclude any obvious sub-population? (e.g. "exclude hemorrhagic")
```

Wait. Then:

### Q2 — Intervention / Exposure

```
Q2 — Intervention or Exposure
  What is the intervention or exposure under study?
   - intervention class (e.g. "MI-BCI", "rTMS", "tDCS")
   - any required dose / regimen constraints
   - explicitly OUT: which intervention classes are EXCLUDED?
     (e.g. "exclude pharmacological-only studies")
```

Wait. Then:

### Q3 — Comparator

```
Q3 — Comparator
  Is a comparator required, and if so which?
   - "sham" only
   - "any active control"
   - "no control needed (single-arm acceptable)"
   - or a specific comparator (e.g. "standard PT")
```

Wait. Then:

### Q4 — Outcome

```
Q4 — Outcome
  Which outcome(s) must the study report to be eligible?
   - primary outcome(s) — e.g. "Fugl-Meyer UE total"
   - is reporting at least one eligible outcome required, or all?
   - acceptable timepoint(s) — e.g. "post-treatment, with or without
     follow-up"
```

Wait. Then:

### Q5 — Study design

```
Q5 — Study design
  Which designs are eligible?
   - RCTs only?
   - RCT + non-randomized controlled?
   - + observational / cohort?
   - any?
  Anything explicitly excluded? (e.g. "exclude case reports, case series
  < 10 patients, editorials, conference abstracts only")
```

Wait. Then:

### Q6 — Hard filters

```
Q6 — Hard filters
  Any non-content filters?
   - language (English only / English + French / any)
   - date range (e.g. 2010 onwards)
   - publication type (peer-reviewed full text only / accept preprints)
   - setting (clinical / in-vitro / animal)
```

Wait. Then:

### Q7 — Anything else?

```
Q7 — Any other criterion the screening agent must apply?
  (open-ended — e.g. "must report a per-arm sample size",
   "must declare conflicts of interest", "exclude studies using
   non-validated outcome scales")
```

## Step 4 — Persist `screening/criteria.md`

Write the answers as structured Markdown. Each criterion gets a
**short label tag** (used by the screener sub-agents in their
decision output). Choose tags that are mnemonic and stable
(e.g. `wrong-population`, `not-RCT`, `non-english`, `pre-2010`).

Format:

```markdown
# Eligibility criteria — <project-name>

> Source of truth for `/wiki-screen-tiab` and `/wiki-screen-fulltext`.
> Each criterion has a short tag — the screener sub-agents use those
> tags as exclusion reasons in `tiab-decisions.csv` and
> `fulltext-decisions.csv`.

## PICO

| Element | Definition |
|---|---|
| **P**opulation  | <answer to Q1> |
| **I**ntervention | <answer to Q2> |
| **C**omparator  | <answer to Q3> |
| **O**utcome     | <answer to Q4> |

## Inclusion criteria

| Tag | Criterion |
|---|---|
| `eligible-design`        | <from Q5 — included designs> |
| `eligible-population`    | <from Q1 — included population> |
| `eligible-intervention`  | <from Q2 — included intervention> |
| `eligible-comparator`    | <from Q3 — comparator requirement> |
| `eligible-outcome`       | <from Q4 — required outcome> |

## Exclusion criteria

(Listed in the ORDER the screener should evaluate. Tag = mnemonic
label the screener uses in its decision output.)

| # | Tag | Criterion | Verifiable from |
|---|---|---|---|
| 1 | `wrong-population`   | <verbatim — derived from Q1>     | Methods §Participants |
| 2 | `not-<design>`       | <e.g. `not-RCT`, derived from Q5>| Methods §Study design |
| 3 | `wrong-intervention` | <derived from Q2>                | Methods §Intervention |
| 4 | `no-comparator`      | <derived from Q3, if applicable> | Methods §Study design |
| 5 | `wrong-outcome`      | <derived from Q4>                | Methods §Outcomes / Results |
| 6 | `non-english`        | <if applicable from Q6>          | metadata / first page |
| 7 | `pre-<year>`         | <if applicable from Q6>          | metadata |
| 8 | `wrong-pub-type`     | <e.g. conference abstract only>  | metadata / DOI prefix |
| 9 | <free-form from Q7>  | <verbatim>                       | <where to look> |

## Notes for the screener sub-agents

- <if Q5 requires a specific N per arm, state it here>
- <if Q4 requires a specific timepoint, state it here>
- <any other domain prior that disambiguates a tag>

## Pre-screening decisions (audit)

(Append-only — fill as decisions evolve mid-screening.)

- **YYYY-MM-DD** — <criterion> — <decision> (<rationale>)
```

After writing, echo it back and ask:

```
✓ screening/criteria.md written. Reading it back:

[show file content, ~40 lines]

Edit / add anything? [n / paste edit]
```

Apply edits if any.

## Step 5 — Final guidance

Print:

```
✓ Screening phase ready at ./project-review/<name>/screening/

Next steps:

1. Drop your identified-record CSVs into:
   project-review/<name>/screening/identified/
   Expected columns (case-insensitive, all optional except title):
     title, authors, year, doi, pmid, abstract, journal
   One CSV per source database (pubmed.csv, scopus.csv, …) — the
   filename becomes the source_db tag in the dedup.

2. Run the title/abstract screening pass:
   /wiki-screen-tiab <name>
   It will dedupe, fetch missing abstracts, judge each record against
   criteria.md, auto-fetch PDFs of inclusions, and write the report.

3. Once you've finished fetching paywalled PDFs manually:
   /wiki-screen-fulltext <name>
   It will judge each retrieved article's body against criteria.md
   and update the PRISMA flowchart.

4. The included articles flow naturally into extraction via
   /wiki-extract-table project-review/<name>/
```

# Hard constraints

- **NEVER touch `project-review/<name>/extraction/`** — that's the
  extraction phase's territory. This command only writes under
  `project-review/<name>/screening/` and (when seeding the project)
  `project-review/<name>/contexte.md` if it's empty.
- **NEVER overwrite an existing non-empty `criteria.md`** without
  the `redo` confirmation in Step 1.
- **Ask ONE question at a time** in the interactive build. Wait for
  the answer, echo to confirm. The whole point is a guided
  conversation, not a wall of text.
- **NEVER invent criteria the user did not give.** If Q3 says "no
  comparator required", do NOT add an `eligible-comparator` row. The
  table rows are derived strictly from the user's answers.
- **Tags must be kebab-case, ≤ 32 chars, mnemonic.** No spaces, no
  uppercase, no punctuation other than `-`. The screener sub-agents
  emit them verbatim into CSV cells.
