---
description: Run PRISMA pass 2 — full-text screening. For each PDF in `screening/1st-pass/raw/` (converted to MD on demand), delegates one decision to the `screener-fulltext` sub-agent against `screening/criteria.md`. Writes per-pass report + updates the PRISMA flowchart. Final list of included articles is staged for `/extractor-table`.
argument-hint: "<project-name>  [--limit N]  [--only <slug>]  [--reset]"
---

Run the PRISMA full-text screening pass.

Arguments: $ARGUMENTS

# Prerequisites

The T/A pass must have produced at least these artifacts:

```
project-review/<vault>/<name>/
└── screening/
    ├── criteria.md                           # MUST exist
    ├── tiab-decisions.xlsx                    # MUST exist (from /extractor-screen-tiab)
    └── 1st-pass/
        ├── raw/<slug>.pdf                    # at least some PDFs
        └── markdown/<slug>.md                # auto-converted (or manually dropped)
```

If `tiab-decisions.xlsx` is missing, refuse and tell the user to run
`/extractor-screen-tiab <name>` first.

# Procedure

## Phase 0 — Parse args, verify state

Parse `$ARGUMENTS`:
- First positional = project name
- `--limit N` → cap delegations (smoke-test)
- `--only <slug>` → screen just that one article (useful for re-judging
  after a manual PDF replacement)
- `--reset` → discard `fulltext-decisions.xlsx` and start over (asks
  for confirmation)

Read `screening/criteria.md`. If empty, refuse.

Determine the candidate set:
- Source = rows of `tiab-decisions.xlsx` with `decision` ∈ {include, uncertain}
- Plus: any row the user manually flipped to `include` during the T/A
  audit (already on disk)
- Minus: any article whose MD body is missing AND whose PDF is missing
  (these are tagged `not-retrieved` and skipped)

Print the plan:

```
Will full-text-screen N candidates:
  - bodies available: K (PDF + MD ready)
  - need conversion : K (PDF present, MD missing)
  - not retrieved   : K (no PDF, no MD)
Proceed? [Y/n]
```

## Phase 1 — Ensure each candidate has a MD body

For each candidate whose `screening/1st-pass/markdown/<slug>.md` is
missing but whose `screening/1st-pass/raw/<slug>.pdf` is present,
convert via the same toolchain as `/wiki-convert`:

```bash
python pdf2md/marker_convert.py \
    --in  project-review/<vault>/<name>/screening/1st-pass/raw/<slug>.pdf \
    --out project-review/<vault>/<name>/screening/1st-pass/markdown/<slug>.md
```

(See `docs/workflows/conversion.md` for the canonical entrypoint in
your install.)

Skip if `marker` is unavailable — log the conversion gap and continue
with whatever MDs already exist.

## Phase 2 — Screen each candidate (delegate to `screener-fulltext`)

For each candidate with an available MD body:

Spawn `screener-fulltext` with:
- the project's `criteria.md` path
- the project's `contexte.md` path
- the project's `background/notes.md` path (or nothing if absent / empty)
- the article's slug
- the article MD path
  (`project-review/<vault>/<name>/screening/1st-pass/markdown/<slug>.md`)
- the row's title and DOI hygiene flags from `dedup.xlsx`
  (`doi_status`, `doi_title_match`, `doi_year_match`). The
  sub-agent's DOI cross-check uses these to detect wrong-PDF
  situations: a flagged title mismatch + a body whose title clearly
  describes a different paper → returns `exclude |
  wrong-pdf-fetched | ` and the orchestrator surfaces the slug for
  manual re-fetch.

The sub-agent returns ONE line — either the standard 3-field
format (for exclusions / uncertain) or the 4-field format with
metadata harvest (for includes):

```
<decision> | <reason> | <side_use>                  ← exclude / uncertain
<decision> | | | <metadata-json>                    ← include
```

where:
- `<reason>` for exclusions is **one or more** triplets of the shape
  `<tag>; "<verbatim excerpt>"; <source location>` (mandatory — see
  `.claude/agents/screener-fulltext.md`). Multiple triplets are
  joined by ` ;; ` (space-semicolon-semicolon-space). The FIRST
  triplet is the primary PRISMA exclusion motive; the rest are
  secondary.
- `<side_use>` is optional. When non-empty, it has either the bare
  category (`intro`, `discussion`, `method`, `reco`, `general`) OR
  the augmented form `<category>; "<quote>"; <location>` (preferred
  — auditable).
- `<metadata-json>` (4th field, ONLY for `decision = include`) is
  a single-line JSON object with keys `sites`, `recruitment_start`,
  `recruitment_end`, `team`, `n`, `registration`. The screener-fulltext
  agent harvests these from the article body so the overlap audit
  in Phase 4b can flag suspected dataset reuse. Empty object `{}`
  is valid (body too sparse to harvest).

**Batch in parallel**: 3–5 sub-agents at a time (sonnet — heavier
than the T/A pass).

Parse each output strictly:

1. Split on top-level `|` → 3 fields (exclude / uncertain) or 4
   fields (include with metadata harvest). Legacy 2-field format
   is padded with empty `<side_use>`.
2. Validate `<decision>` ∈ {include, exclude, uncertain}.
3. Validate `<side_use>` head (first `;`-separated token) ∈
   {empty, intro, discussion, method, reco, general}.
4. If `<decision> ≠ exclude` AND `<side_use>` is non-empty, log as
   `error` (protocol violation).
5. For exclusions, split `<reason>` on ` ;; ` → list of triplets.
   Each triplet must parse into 3 `;`-separated parts (tag,
   excerpt, location). Otherwise log as `error`. The FIRST triplet
   populates `tag` / `excerpt` / `location` columns (primary motive
   for the PRISMA flowchart); the remaining triplets are
   concatenated back with ` ;; ` and stored in `reasons_secondary`.
6. For `decision = include`, parse the 4th field (`<metadata-json>`)
   as JSON. Store the raw JSON string in the `metadata_json`
   column. If parsing fails OR the field is absent (legacy
   3-field output), store `{}` and log a `warn` (the include is
   still recorded, just without overlap-detection metadata).

Append each result to `screening/fulltext-decisions.xlsx` with columns
in this order — **slug first, then what the agent did (decision +
evidence), then article context** (so audit gates show the verdict
before the metadata):

```
slug, decision, tag, excerpt, location, reasons_secondary,
side_use, side_excerpt, side_location, screener_note,
metadata_json,
doi, pmid, title, timestamp
```

The `metadata_json` column carries the harvested dataset
descriptors for includes (sites / recruitment window / team / n /
registration) as a single-line JSON string. Exclusions and
uncertains leave the cell empty.

Use `tabular.append_record` from `tools/tabular.py` to append each
row — it handles xlsx natively and creates the file with the
styled header on the first call. Legacy CSVs written before this
reorder are still parsed correctly (both `tabular.read_records`
and pandas key off the header row, not column position) — only
newly-written rows follow the new order. Legacy decisions written
before the multi-reason format have an empty `reasons_secondary`
cell, which the audit gate displays as `—`.

For `include`, the tag/excerpt/location columns are empty,
`reasons_secondary` is empty, and side_* are empty. For
`exclude`, tag/excerpt/location are mandatory (primary motive);
`reasons_secondary` is filled when the screener returned ≥ 2
reasons; side_* are filled only when the screener flagged the
article.

For articles without a body (`not-retrieved`), record a row with
`decision = not-assessed` and `tag = body-missing` — they will show
up in the "Reports not retrieved" branch of the PRISMA flowchart.

## Phase 2b — User audit gate (mandatory)

After all candidates are screened, show the user:

```
✓ Full-text screening complete — N candidates judged

Decision breakdown:
  include       : K
  exclude       : K
  uncertain     : K
  not-assessed  : K   (no body — manual fetch still pending)

Side-use flags (within excludes):
  intro       : K
  discussion  : K
  method      : K
  reco        : K
  general     : K
  (no side)   : K

Top exclusion reasons (full text):
  wrong-population   : K
  wrong-design       : K
  wrong-outcome      : K
  …

Options:
  [a]   Audit a sample (default: all `uncertain` + 10% of others)
  [u]   Show all `uncertain` rows
  [e]   Show all `exclude` rows (with verbatim excerpts)
  [side] Audit all rows with a side_use flag (verify category + quote)
  [c]   Continue — write reports & flowchart
  [s]   Stop here — re-run later
```

Default = `a`. For each audited row, display in this order
(slug → decision + evidence → article info):

```
<slug>
  decision           : <decision>
  primary motive     : <tag or "—">
    excerpt          : "<verbatim excerpt or "—">"
    location         : <location or "—">
  reasons_secondary  : <reasons_secondary or "—">   ← full ";;"-joined list
  side_use           : <side_use or "—">
    side_excerpt     : "<side_excerpt or "—">"
    side_location    : <side_location or "—">
  note               : <screener_note or "—">
  ─
  doi                : <doi or "—">
  pmid               : <pmid or "—">
  title              : <title>
```

Then prompt:

```
keep / flip-to-include / flip-to-exclude / set-side <category> / clear-side / view-body
```
- `<category>` ∈ {intro, discussion, method, reco, general}
- `view-body` opens the MD path so the user can verify against the
  excerpt
- Flips and side edits are written to `fulltext-decisions.xlsx` and
  logged under `## Manual overrides` in
  `screening/reports/fulltext-report.md`

## Phase 3 — Write the per-pass report

`screening/reports/fulltext-report.md`:

```markdown
# Full-text screening report — <project-name>

> Auto-generated by `/extractor-screen-fulltext` on YYYY-MM-DD.

## Summary

- Candidates (from T/A pass)          : N
- Bodies available                    : N
- Bodies not retrieved                : N (manual fetch outstanding)
- Reports assessed for eligibility    : N
- Included in review                  : N
- Excluded at full text               : N

## Exclusions by reason (with verbatim evidence)

> PRISMA flowchart counts articles ONCE under their PRIMARY
> exclusion motive. The "also fires on" annotation surfaces every
> additional criterion the article violated — kept transparent for
> audit, but not double-counted in the per-criterion totals.

### wrong-population (n = K)
- **<slug-1>** — "<verbatim excerpt>" (Methods §"Participants")
  - also fires on: `not-RCT`, `n-too-small`
- **<slug-2>** — "<excerpt>" (Table 1)
- …

### not-RCT (n = K)
- **<slug-3>** — "<excerpt>" (Methods §"Study design")
  - also fires on: `wrong-outcome`
- …

(One subsection per criterion tag — each article appears under its
PRIMARY motive only; secondary motives appear as a sub-bullet for
transparency. Total count across subsections = total full-text
exclusions, not the sum of individual criterion firings.)

## Manual overrides (from audit gate)

- <slug>: flip <orig> → <new> (reason: <user note>)

## Errors to triage

- <slug>: <raw sub-agent output>
```

## Phase 4 — Update PRISMA flowchart

```bash
python tools/screen_prisma.py project-review/<vault>/<name>
```

Now both passes are reflected in the chart: identified → after-dedup
→ T/A screened → reports sought → reports retrieved → reports
assessed → included.

## Phase 4b — Overlap audit (suspected dataset reuse)

Two papers reporting the same trial / same cohort would
double-count patients in the review. The screener-fulltext agent
harvested dataset metadata (sites, recruitment window, team, n,
trial registration) for every include — now we cluster.

```bash
python tools/screen_overlap.py project-review/<vault>/<name>
```

Writes:
- `screening/reports/overlap-clusters.md` — suspected pairs
  grouped by confidence (HIGH = same trial registration, MEDIUM =
  same team + overlapping recruitment window + similar n, LOW =
  shared site + overlapping window).
- `screening/overlap-decisions.xlsx` — audit trail stub, filled
  in by the user at the gate below.

If no clusters were detected, print `✓ No overlap signals — N
includes appear to come from distinct cohorts.` and skip to
Phase 5.

If clusters were detected, surface them to the user:

```
⚠ Overlap audit — K suspected pairs (Confidence: H high / M medium / L low)

   HIGH (same trial registration):
     a-2020 ↔ a-2021  evidence: NCT02093924
     (titles + DOIs printed)

   MEDIUM (same team + window overlap + similar n):
     b-2020 ↔ b-2021  evidence: team=soekadar, window=88%, n=(24 vs 28)

   LOW (shared site + window overlap):
     c-2019 ↔ d-2019  evidence: sites=hospital x, window=59%

For each cluster, decide:
  [k1] keep-both    — distinct cohorts despite the signal (rare for HIGH)
  [p1] pick-one     — one paper supersedes the other (keep the more recent
                      or more complete report; the other is excluded with
                      tag `overlapping-dataset`)
  [m1] merge        — both papers report partial views of the same study;
                      keep both for extraction but flag the dependency
                      (one extraction row spans both papers)
  [s1] skip         — defer the decision for later, keep both for now
```

For each pair, capture the user's choice in
`screening/overlap-decisions.xlsx` (`user_action` column +
optional `rationale`). Then apply the action:

- `pick-one`: in `fulltext-decisions.xlsx`, flip the dropped slug
  from `include` to `exclude` with `tag = overlapping-dataset` and
  `excerpt = "Supersedes/duplicates <other-slug> (<evidence>)"`.
  Re-run `python tools/screen_prisma.py ...` so the flowchart
  reflects the new exclusion.
- `merge`: keep both `include` rows but write a marker row in
  `screening/dependent-articles.md` (create if absent) so the
  extraction phase knows to read both as one study.
- `keep-both` / `skip`: no CSV change; the audit trail still
  records the user's decision.

Log all actions under `## Overlap audit` of
`screening/reports/fulltext-report.md`.

## Phase 5 — Stage included articles + side references

### 5a — Included → extraction/articles/

For each row in `fulltext-decisions.xlsx` with `decision = include`:
- Copy `screening/1st-pass/markdown/<slug>.md` to
  `project-review/<vault>/<name>/extraction/articles/<slug>.md` (cp, never mv
  — the screening register stays intact).
- Update (or create) `project-review/<vault>/<name>/contexte.md`'s
  `## Source list` block with the slug if it isn't already listed.

### 5b — Side-flagged excludes → extraction/biblio/side/<category>/

For each row in `fulltext-decisions.xlsx` with `decision = exclude`
AND `side_use ≠ empty`:

- Copy `screening/1st-pass/markdown/<slug>.md` to
  `extraction/biblio/side/<side_use>/<slug>.md`.
- Copy `screening/1st-pass/raw/<slug>.pdf` (if present) to
  `extraction/biblio/side/<side_use>/raw/<slug>.pdf`.
- Append a row to
  `extraction/biblio/side/<side_use>/index.md` (create with header
  if absent):

```markdown
# Side references — <category>

> Articles excluded from extraction but flagged as worth citing in
> this section of the review. Auto-populated by
> /extractor-screen-fulltext; user can manually override the category at
> the audit gate.

| Slug | Why side (verbatim) | Source location | DOI / PMID | Title |
|---|---|---|---|---|
| <slug> | <side_excerpt> | <side_location> | <doi> | <title> |
```

T/A-only side flags (rows with no body) are NOT copied here — they
were never read in full, so the recommendation is speculative.
They stay listed in
`extraction/biblio/side/<category>/pending.md` (from `/extractor-screen-tiab`
Phase 4b) for the user to either fetch the body and re-run the
full-text pass with `--only <slug>`, or accept the speculative tag.

This lets the user run `/extractor-table project-review/<vault>/<name>/`
straight away without an extra manual copy step, with side
references pre-organized by where they belong in the review.

## Phase 6 — Final guidance

```
✓ Full-text screening done.
  Included      : N studies
  See: project-review/<vault>/<name>/screening/reports/fulltext-report.md
  See: project-review/<vault>/<name>/screening/reports/prisma-flowchart.md

Articles ready for extraction:
  project-review/<vault>/<name>/extraction/articles/

Next step:
  /extractor-table project-review/<vault>/<name>/
```

# Hard constraints

- **NEVER screen an article whose T/A decision was `exclude`** — those
  articles are out by definition. If the user wants to re-judge one,
  they must flip it to `include` in `tiab-decisions.xlsx` first
  (manually or via the T/A audit gate's flip option).
- **NEVER use the abstract alone to decide at full text.** If the body
  is unavailable, the decision is `not-assessed` with
  `tag = body-missing` — NOT `uncertain` and NOT a re-cast of the T/A
  decision.
- **NEVER allow an `exclude` without a verbatim excerpt + location.**
  The sub-agent's contract requires it; the parent verifies and logs
  malformed responses as `error` (not `exclude`).
- **NEVER stage an `uncertain` or `exclude` into
  `extraction/articles/`.** Only confirmed `include` rows are copied.
- **NEVER claim full-text screening is done before regenerating the
  PRISMA flowchart.** The chart must always reflect the current state
  of the two decision CSVs.
- **NEVER skip the audit gate.** Even a small `--limit` run goes
  through Phase 2b.
- **PASS `background/notes.md` to every screener-fulltext
  invocation** when the file exists and is non-empty. Consistency
  across decisions matters. If absent or empty, skip silently — do
  NOT fabricate context.
- **NEVER auto-copy a side-flagged article if the audit gate
  rejected it** (`clear-side` action). Side staging in Phase 5b
  reads the FINAL `fulltext-decisions.xlsx` after user overrides.
- **NEVER assign a side category outside
  {intro, discussion, method, reco, general}**. The orchestrator
  rejects malformed categories as `error`.
