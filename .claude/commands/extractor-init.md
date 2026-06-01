---
description: Bootstrap and interactively build a literature-review project under project-review/<vault>/<name>/. Multi-vault — projects are grouped per research domain (vault), independently of the wiki vaults. Creates the folder skeleton (contexte.md, background/, screening/, extraction/), then walks the user through filling contexte.md, co-designing the template (if blank), and authoring column-by-column instructions. Pairs with /extractor-table which runs the extraction.
argument-hint: "[<vault>/]<project-name>  [--from-source <SR-slug>]  [--columns col1,col2,...]  [--skeleton-only]"
---

Create and interactively build a fresh literature-review project.

Arguments: $ARGUMENTS

# Project folder vs. the wiki — IMPORTANT

GraphBib has **two distinct orchestrators**, each with its own
folder structure. They are intentionally **independent**:

| Orchestrator | Folder | Purpose | Obsidian? |
|---|---|---|---|
| **Wiki** | `wiki/<vault>/` + `raw/<vault>/` | The agent's knowledge graph: sources, concepts, methods, recommendations, questions, syntheses, entities. Read by Obsidian as a vault. | **YES** — opened as an Obsidian vault |
| **Extractor** | `project-review/<vault>/<name>/` | Self-contained literature-review project: contexte, background, screening, extraction. **NOT part of any Obsidian vault.** | **NO** — pure file system, opened in Excel / a code editor |

This command operates on the **Extractor side**. It does NOT touch
the wiki. Even when the project vault name matches a wiki vault
(e.g. both called `BCINET`), the two are independent — they share
only a research-domain label. The user must explicitly decide to
ingest a project-review's results into the wiki after the fact.

# Location

All literature-review projects live under
`project-review/<vault>/<name>/` at the repo root:

```
GraphBib/                            ← repo root
├── wiki/<vault>/                    ← Wiki orchestrator (independent)
├── raw/<vault>/                     ← Wiki orchestrator's raw inputs
├── docs/, tools/, pdf2md/           ← agent infrastructure
└── project-review/                  ← Extractor orchestrator
    ├── <vault-A>/                   ← one vault per research domain
    │   ├── mibci/                   ← project 1 (in vault-A)
    │   ├── tms-dose-response/       ← project 2 (in vault-A)
    │   └── dti-biomarkers/          ← project N (in vault-A)
    └── <vault-B>/                   ← another vault, independent
        └── cardiology-risk-factors/
```

The vault is part of the argument. Two equivalent invocations:

```
/extractor-init BCINET/mibci          # explicit vault + project
$PROJECT_VAULT=BCINET                 # env-driven default
/extractor-init mibci                 # uses $PROJECT_VAULT
```

Resolution priority for the vault:

1. The path argument contains a `/` → use everything before the `/` as the vault.
2. `$PROJECT_VAULT` env var is set → use it as the vault.
3. A single sub-vault exists under `project-review/` → use it.
4. Multiple sub-vaults exist → REFUSE; ask the user to disambiguate.
5. Legacy flat layout (`project-review/<name>/` projects at the root,
   no sub-vault folders) → REFUSE; ask the user to pick a vault
   (and optionally migrate existing projects via `mv`).

The vault name is independent from `$WIKI_VAULT`. Setting them to
the same string is fine and recommended for consistency, but not
enforced. Use a different env var deliberately when you want a
project-review under a different domain label than the wiki vault.

The container (`project-review/<vault>/`) is created on first run
if missing.

The command **refuses** to create a project anywhere else (inside
`wiki/`, `raw/`, `docs/`, `tools/`, or as a sibling of these).
`project-review/<vault>/<name>` is the only valid path.

# What this command creates

```
project-review/<vault>/<name>/
├── contexte.md             # narrative scope — SHARED by screening + extraction
├── log.md                  # unified audit trail across both phases
├── background/             # USER-AUTHORED context for the sub-agents
│   ├── notes.md            # domain primer read by screener-tiab/fulltext + extractor
│   ├── raw/                # user drops context PDFs here (seminal works, prior reviews)
│   └── markdown/           # converted MDs (or user-dropped MDs)
├── screening/              # PRISMA pass 1 + 2 (populated by /extractor-screen-* commands)
│   ├── criteria.md         # PICO + IN/OUT criteria (built by /extractor-screen-init)
│   ├── identified/         # user drops CSV exports here (pubmed.csv, scopus.csv, …)
│   ├── 1st-pass/
│   │   ├── raw/            # PDFs auto-fetched after T/A inclusion
│   │   ├── markdown/       # converted for full-text reading
│   │   └── missing.md      # paywalled — user to fetch manually
│   └── reports/            # tiab / fulltext / prisma-flowchart
└── extraction/             # phase 2 — data extraction (this command's main focus)
    ├── instructions.md     # per-column spec — empty preamble, filled by Phase 1
    ├── template.xlsx       # 2-row template (slug + instruction)
    ├── articles/           # source MDs (fed by screening or linked from wiki/sources/)
    ├── output/             # extraction outputs land here (empty for now)
    └── biblio/
        ├── side/           # excluded articles flagged as worth citing
        │   ├── intro/      # cited in introduction / motivation
        │   ├── discussion/ # cited in discussion / interpretation
        │   ├── method/     # methodological references (scale validation, technique)
        │   ├── reco/       # clinical / practice recommendations to cite
        │   └── general/    # useful side reference, category unclear
        ├── raw/            # COPIES of included PDFs (portable project artifact)
        └── markdown/       # COPIES of post-ingestion MD from wiki/sources/
```

Two distinct context concepts:

| Folder | Purpose | Who writes |
|---|---|---|
| `background/` | INPUT context. Articles the user has identified as foundational (motivation, seminal works, prior reviews, glossary). The sub-agents READ `background/notes.md` to ground their domain knowledge. | User — manually drops PDFs + authors `notes.md` |
| `extraction/biblio/side/` | OUTPUT side references identified during screening. Articles EXCLUDED from extraction but worth citing in the review. | Screener sub-agents — auto-flagged; user can override at audit gate |

The `screening/` and `extraction/` skeletons are created empty
(folders only). The PICO + criteria interactive build is delegated
to `/extractor-screen-init <name>` so this command stays focused on the
extraction phase setup.

Naming: the user passes a SHORT name (`mibci`, `tms-dose`,
`dti-biomarkers`) — the agent does NOT append `-review` since the
parent `project-review/` already conveys "this is a review project".
Use kebab-case for multi-word names.

**Backward compatibility**: projects bootstrapped before the
screening phase (flat layout — template at the project root) keep
working — `tools/extract_data.py` and `/extractor-table` detect
the layout automatically. Run `mv` manually if you want to migrate
an old project into the phased layout:

```bash
cd project-review/<name>
mkdir -p extraction
mv instructions.md template.xlsx articles output biblio extraction/
```

# Procedure

## Step 1 — Confirm scope + resolve the vault

Parse `$ARGUMENTS`:
- First positional argument:
  - `<vault>/<project-name>` → explicit vault + project (e.g.
    `BCINET/mibci-stroke`). Use everything before the FIRST `/` as
    the vault, the rest as the project name (further slashes are
    rejected as invalid).
  - `<project-name>` → vault is resolved by Step 1b below.
- `--from-source <SR-slug>` (optional) — seed the template's data
  rows from the SR's `cites:` list.
- `--columns col1,col2,...` (optional) — column set for the template;
  default is the 27-column SR set in `tools/extract_data.py`.
- `--skeleton-only` (optional) — skip the interactive build, just
  create the empty files. The user can run Phase 1 of
  `/extractor-table` later to clarify instructions.

## Step 1b — Vault resolution (when not given in the argument)

```bash
ls -la project-review/ 2>&1 | head -20
```

Apply this priority:

1. **`$PROJECT_VAULT` env var is set** → use it as the vault. Verify
   that `project-review/$PROJECT_VAULT/` exists (create the empty
   container later) and confirm with the user:
   `Use $PROJECT_VAULT=<vault> for this project? [Y/n]`
2. **`project-review/` doesn't exist or is empty** → ASK the user
   for a vault name (kebab-case, e.g. `BCINET`, `cardiology`).
   Suggest reusing `$WIKI_VAULT` if it's set (with explicit
   confirmation — the user must opt in, since the two are
   independent):
   `Reuse $WIKI_VAULT=<vault> as the project-review vault? [y/N]`
3. **Single sub-vault exists** (a `project-review/<sub>/` folder that
   itself contains existing projects with `contexte.md` /
   `extraction/` / `screening/`) → use it automatically; confirm
   with `Found existing vault project-review/<sub>/. Use it? [Y/n]`.
4. **Multiple sub-vaults exist** → REFUSE; list them and ask the
   user to either pass `<vault>/<name>` explicitly or export
   `$PROJECT_VAULT`.
5. **Legacy flat layout detected** (`project-review/<name>/` folders
   exist at the top, no sub-vaults) → ASK the user:
   - `[1] Pick a NEW vault and create project-review/<vault>/<name>/ here.`
   - `[2] Stay flat — create project-review/<name>/ next to the others (legacy mode).`
   - `[3] Cancel.`
   Default: [1]. If [2], the project is created at the legacy flat
   path and downstream commands will detect the layout
   automatically.

Once the vault is resolved, build the full target path:

```
project-review/<vault>/<project-name>/   # phased layout (preferred)
project-review/<project-name>/           # flat legacy fallback
```

Refuse if any reserved name conflicts: the vault and project name
must NOT match any of `screening`, `extraction`, `background`,
`contexte`, `log`, `criteria`, `instructions`, `template`,
`articles`, `output`, `biblio`.

Show the plan and ask before creating:

```
Will create: ./project-review/<vault>/<name>/
  ├── contexte.md                          (seeded — shared by both phases)
  ├── log.md                               (empty audit trail)
  ├── background/                          (user-authored sub-agent context)
  │   ├── notes.md                         (placeholder — user fills with a short primer)
  │   ├── raw/                             (empty — drop seminal PDFs / prior reviews here)
  │   └── markdown/                        (empty — converted MDs)
  ├── screening/                           (PRISMA pass 1 + 2 skeleton)
  │   ├── criteria.md                      (placeholder — built by /extractor-screen-init)
  │   ├── identified/                      (drop your CSV exports here)
  │   ├── 1st-pass/{raw,markdown}/         (filled after pass 1)
  │   └── reports/                         (auto-generated reports + PRISMA flowchart)
  └── extraction/                          (data-extraction phase)
      ├── instructions.md                  (empty preamble)
      ├── template.xlsx                    (M columns × N rows)
      │     M = 27 (default SR set) | <count from --columns>
      │     N = 0 (manual) | <count from --from-source cites>
      ├── articles/                        (empty — fed by screening or wiki/sources/)
      ├── output/                          (empty — extraction outputs)
      └── biblio/
          ├── side/{intro,discussion,method,reco,general}/  (auto-populated by screening)
          ├── raw/                         (empty — PDF copies of included articles)
          └── markdown/                    (empty — MD copies from wiki/sources/)
Proceed? [Y/n]
```

If `project-review/<vault>/<name>/` already exists and is non-empty:
- If `contexte.md`, `extraction/instructions.md`, or
  `extraction/template.{xlsx,csv}` exist → REFUSE. Ask user to pick a
  different name or remove the folder themselves (don't overwrite
  their work).
- If folder exists but empty → proceed.

## Step 2 — Create the folder structure

```bash
mkdir -p project-review/<vault>/<name>/background/raw \
         project-review/<vault>/<name>/background/markdown \
         project-review/<vault>/<name>/screening/identified \
         project-review/<vault>/<name>/screening/1st-pass/raw \
         project-review/<vault>/<name>/screening/1st-pass/markdown \
         project-review/<vault>/<name>/screening/reports \
         project-review/<vault>/<name>/extraction/articles \
         project-review/<vault>/<name>/extraction/output \
         project-review/<vault>/<name>/extraction/biblio/side/intro \
         project-review/<vault>/<name>/extraction/biblio/side/discussion \
         project-review/<vault>/<name>/extraction/biblio/side/method \
         project-review/<vault>/<name>/extraction/biblio/side/reco \
         project-review/<vault>/<name>/extraction/biblio/side/general \
         project-review/<vault>/<name>/extraction/biblio/raw \
         project-review/<vault>/<name>/extraction/biblio/markdown
```

Seed `background/notes.md` (placeholder):

```markdown
# Background — <project-name>

> Optional but recommended. Short domain primer read by every
> sub-agent (screener-tiab, screener-fulltext, extractor) at session
> start. Use it to:
>
> - Disambiguate domain terminology (e.g. "what 'chronic' means in
>   this corpus", "which intervention class label is canonical").
> - Point to the seminal studies and key prior reviews that frame
>   the question.
> - Record motivation: why does this review exist, what gap does it
>   fill, what prior reviews are out of date.
>
> Keep it short — under 800 words. Drop the PDFs of cited works
> into `background/raw/`; their MDs (auto-converted or manually
> dropped) live in `background/markdown/`.
>
> The sub-agents read this file only — they do NOT read every PDF
> in `background/raw/`. The notes file is your distilled summary.

## Motivation

(Why this review? What problem does it answer?)

## Seminal works

(Key prior reviews / foundational papers the sub-agents should
recognize. Cite by author-year.)

- <author-year>: <one-line description>

## Glossary / terminology disambiguation

(Terms with multiple synonyms in the literature, terms with
domain-specific meaning.)

- **<term>**: <how this review defines it>

## Domain priors

(Conventions the sub-agents should apply when uncertain.)

- <prior 1>
- <prior 2>
```

Seed the placeholder `screening/criteria.md`:

```markdown
# Eligibility criteria — <project-name>

> Placeholder. Run /extractor-screen-init <project-name> to populate
> interactively (PICO + inclusion + exclusion criteria with mnemonic
> tags consumed by the screener-tiab and screener-fulltext sub-agents).
>
> Skip this file if you already have a fixed list of slugs to extract
> and don't need a PRISMA screening pass — go straight to
> /extractor-table.
```

Seed an empty `log.md`:

```markdown
# Project log — <project-name>

Append-only chronological record of every project operation
(screening pass 1, pass 2, extraction phases, manual edits).
Format: `## [YYYY-MM-DD] <operation> | <summary>`
```

Seed `screening/1st-pass/missing.md` (empty table — `/extractor-screen-tiab`
fills it for articles whose PDFs couldn't be auto-fetched):

```markdown
# Articles included at T/A but not retrievable

> Filled by `/extractor-screen-tiab` after the auto-fetch pass.
> Drop the PDF manually into `screening/1st-pass/raw/<slug>.pdf`
> when you locate it; `/extractor-screen-fulltext` picks it up.

| Slug | DOI / PMID | Title | Where to try | User note |
|---|---|---|---|---|
```

The container `project-review/` is auto-created if it doesn't exist
yet (first project bootstrap).

The `extraction/biblio/side/` folder is left empty — the user adds
PDFs or MDs manually for background references and intro sources
(not extracted but cited).

## Step 3 — Seed contexte.md

Write `project-review/<vault>/<name>/contexte.md` (root level — shared by
screening and extraction) with a **minimal** guided template —
only what the extraction agent will actually consume. Inclusion /
exclusion criteria, date ranges, and language filters belong to the
**pre-extraction** screening phase (which papers to include in the
SR) and are NOT consulted during data extraction. Keep contexte.md
focused on what disambiguates extraction calls:

```markdown
# Project context — <project-name>

> Fill me before running /extractor-table. The extraction agent
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

Write `project-review/<vault>/<name>/instructions.md`:

```markdown
# Extraction instructions — <project-name>

> Auto-populated by the `/extractor-table` Phase 1 debrief.
> Each column gets a section with the row-2 terse instruction
> plus narrative detail and edge cases.

(Empty — run `/extractor-table project-review/<vault>/<name>/` to populate.)
```

## Step 5 — Create the template

### Path A — `--from-source <SR-slug>` provided

```bash
python tools/extract_data.py \
    --from-source <SR-slug> \
    -o project-review/<vault>/<name>/extraction/template.xlsx \
    --no-spec
```

`--no-spec` skips the legacy INSTRUCTIONS/TYPE/SCALE rows so you get
a clean 2-row format the user fills via Phase 1 debrief.

Pass `--columns` if provided.

### Path B — no --from-source

Create an empty template with just headers + empty row 2:

```python
python tools/extract_data.py --from-source __empty__ -o project-review/<vault>/<name>/extraction/template.xlsx --no-spec --columns "<cols>"
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
wb.save("project-review/<vault>/<name>/extraction/template.xlsx")
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
✓ Project skeleton created at ./project-review/<vault>/<name>/

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
answers** into `project-review/<vault>/<name>/contexte.md`, replacing the
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
**Ask one column at a time**, in template order. Show the format
mini-table so the user can answer fast:

```
Column 1 of N — year
  What instruction?

    Type hint:         (int)          → integer (rounds decimals)
                       (years)        → float, units kept in detailed
    Categorical strict: a | b | c     → must pick one
    Categorical open:   a | b | ...   → novel values flagged
                        a, b, other   → ditto (the `other` token signals open)
    Ordinal coded:      0=low, 1=high → returns the code
    Natural language:   Sentence describing what to extract
    Skip:               (leave empty — implicit, clarify later)
```

Wait for answer. Echo back the agent's parsed interpretation to
confirm:

```
  → "Publication year, 4 digits"
    Parsed as: kind=nl, type=text, closure=n/a
  Confirm? [Y / re-enter]
```

For **categorical** instructions, the agent always confirms closure:

```
  → "RCT | cohort | cross-sectional"
    Parsed as: kind=categorical, type=nominal, closure=STRICT
                allowed = [RCT, cohort, cross-sectional]
    Strict means: if a paper reports e.g. "controlled clinical trial"
                  → the coded cell will be BLANK (no match dropped).
    Want OPEN instead? Add " | ..." to the end (then novel values are
    kept verbatim and flagged for you).
  Confirm STRICT? [Y / open / re-enter]
```

For **type-hint** instructions, the agent confirms int vs float:

```
  → "(years)"
    Parsed as: kind=type_hint, type=float
    Coded output will be the numeric value, units stripped: e.g.
                  "12.4 ± 3.1 years" (detailed) → "12.4" (coded)
    If you want INTEGER (rounds decimals), use "(int)" instead.
  Confirm float? [Y / int / re-enter]
```

Move to the next column. Continue until all columns done.

### Step 8c — Persist to both files

Write the instructions into:
- `extraction/template.xlsx` row 2 (terse, machine-readable — exactly
  what the user typed)
- `extraction/instructions.md` (long-form, with the column name as
  `## <name>` heading, the row-2 instruction, plus any clarifying
  detail the user added during 8b)

Confirm with a summary:

```
✓ template.xlsx row 2 filled (N columns).
✓ instructions.md written  ({categorical: K, NL: K, empty: K} kinds).
```

### Step 8d — Instruction review pass (mandatory)

After persisting, **scan ALL columns** and flag issues before declaring
the project ready. This step is NOT optional — it is the main quality
gate that prevents extraction failures downstream.

**Severity levels:**

| Level | Meaning |
|---|---|
| 🔴 Blocking | Extraction will fail or produce wrong values without fix |
| 🟠 Ambiguous | Extraction will be inconsistent across articles |
| 🟡 Clarify | Edge case not covered — extractor will have to guess |

**What to check for each column:**

1. **Empty instruction** 🔴 — must fill before extraction
2. **Strict categorical with no `NR` fallback** 🔴 — if a paper doesn't
   report the variable, the extractor has nowhere to go
3. **`Non Connu` / non-standard NR token** 🟠 — standardize to `NR`
4. **Categorical missing `| ...` for open list** 🟠 — if novel values
   are expected, list must be open
5. **Numeric column with no unit or range specified** 🟠 — extractor
   will report in the article's unit; downstream analysis breaks
6. **Multi-value column with no separator rule** 🟠 — multiple tasks /
   modalities reported: how to join?
7. **"As-reported" columns with no mode disambiguation** 🟡 — e.g. a
   duration that could be fixed, mean, or variable: instruction must
   say what to specify
8. **Derivable column not flagged as such** 🟡 — risk of inconsistent
   extraction (some papers compute it, others don't report it directly)
9. **Instruction conflates two distinct concepts** 🟠 → propose split
10. **Inconsistent terminology across columns** 🟡 (e.g. one column says
    "not reported", another says "NR" — standardize)

**Procedure:**

Present a table of all flagged issues (column name, severity, issue
description) in one block. Then go through each issue **ONE AT A TIME**,
starting with 🔴, then 🟠, then 🟡.

```
Instruction review — N issues found:

  🔴  col_name_1   Empty instruction — must fill
  🔴  col_name_2   No NR fallback for strict categorical
  🟠  col_name_3   "Non Connu" → standardize to NR
  🟠  col_name_4   Open list but no | ... at the end
  🟡  col_name_5   No separator rule for multi-value

Fix them one by one? [Y / skip all 🟡 / skip all]
```

- `Y` → go through each issue in order, one question per issue
- `skip all 🟡` → fix 🔴 and 🟠 only, skip informational
- `skip all` → log unresolved issues in `instructions.md` as a
  `## ⚠️ Unresolved review flags` section and proceed to Step 9

For each resolved issue, **update both `extraction/template.xlsx`
row 2 and `extraction/instructions.md`** in-place. Confirm once at
the end:

```
✓ N issues resolved. Template and instructions updated.
[list of changes made]
```

## Step 9 — Final guidance

Print:

```
✓ Project ready at ./project-review/<vault>/<name>/

The project has TWO phases — both optional, you can use either or both:

Phase 1 (optional) — PRISMA screening
  /extractor-screen-init     <name>         # build PICO + IN/OUT criteria
  (drop CSV exports in screening/identified/)
  /extractor-screen-tiab     <name>         # pass 1 — title/abstract
  (manually fetch paywalled PDFs into screening/1st-pass/raw/)
  /extractor-screen-fulltext <name>         # pass 2 — full text
  → included articles are auto-copied into extraction/articles/

Phase 2 — Data extraction
  /extractor-table project-review/<vault>/<name>/
  Phase 1 of that command re-checks the instructions you just authored
  (catches empty / ambiguous columns), then Phase 2 + 3 produce
  extraction/output/extraction-{detailed,coded}.xlsx.

To add sources to extract WITHOUT screening:
  - List the slugs in project-review/<vault>/<name>/contexte.md under "Source list"
  - Or copy / link the source MDs into project-review/<vault>/<name>/extraction/articles/
  - Or leave both empty and extract_data.py reads straight from wiki/sources/
```

# Notes

- The `extraction/articles/` folder is a **convenience** — the actual
  source MD files live in `wiki/sources/<...>/<slug>.md` and
  `extract_data.py` finds them there via `load_sources()`. Copying /
  linking to `articles/` is useful only if the user wants a portable
  project folder (e.g. to share with a collaborator who doesn't have
  the full wiki cloned), OR when `/extractor-screen-fulltext` populates
  it automatically with included articles. For solo, no-screening
  workflows, leave `articles/` empty — extraction reads straight
  from `wiki/sources/`.

- `extraction/output/` is created empty. The slash command
  `/extractor-table` writes there.

- **This command does NOT touch the wiki.** It only creates files
  under `project-review/<vault>/<name>/` at the repo root. Removing the
  project folder removes all artifacts; the wiki is unaffected.

- Each review lives in its OWN sibling folder. You can have many
  active reviews (`mibci/`, `tms-dose-response/`, `dti-biomarkers/`)
  — they don't interact, share no state, and each has its own
  `contexte.md` / `screening/` / `extraction/`.

- The project folder is intentionally NOT part of any Obsidian vault.
  Open `template.xlsx` in Excel / LibreOffice / Numbers; open
  `contexte.md` / `instructions.md` / `criteria.md` in any text
  editor. Obsidian stays focused on the wiki.

# Hard constraints

- **ALWAYS create the project under `project-review/<vault>/<name>/`.** Never
  at the repo root, never inside `wiki/`, `raw/`, `docs/`, `tools/`,
  `pdf2md/`, `.claude/`, or `graph/`. If the user passes a path with
  a slash in it (e.g. `project-review/foo` or `wiki/bar`), strip
  everything except the basename and use that as `<name>`. If the
  resulting name is empty or invalid, refuse and ask.
- **NEVER overwrite an existing `contexte.md`,
  `extraction/instructions.md`, or `extraction/template.{xlsx,csv}`**
  inside the target sub-folder. Ask the user to remove
  `project-review/<vault>/<name>/` manually if they want a fresh project.
- **NEVER use a project name that conflicts with a reserved name**
  (`articles`, `output`, `contexte`, `instructions`, `template`,
  `log`, `screening`, `extraction`, `biblio`, `criteria`) — these
  are sub-artifact names inside each project. Refuse and ask for a
  different name.
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
