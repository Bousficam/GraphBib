---
description: Run PRISMA pass 2 — full-text screening. For each PDF in `screening/1st-pass/raw/` (converted to MD on demand), delegates one decision to the `screener-fulltext` sub-agent against `screening/criteria.md`. Writes per-pass report + updates the PRISMA flowchart. Final list of included articles is staged for `/extractor-table`.
argument-hint: "<project-name>  [--limit N]  [--only <slug>]  [--reset]"
---

Run the PRISMA full-text screening pass.

Arguments: $ARGUMENTS

# Prerequisites

The T/A pass must have produced at least these artifacts:

```
project-review/<name>/
└── screening/
    ├── criteria.md                           # MUST exist
    ├── tiab-decisions.csv                    # MUST exist (from /extractor-screen-tiab)
    └── 1st-pass/
        ├── raw/<slug>.pdf                    # at least some PDFs
        └── markdown/<slug>.md                # auto-converted (or manually dropped)
```

If `tiab-decisions.csv` is missing, refuse and tell the user to run
`/extractor-screen-tiab <name>` first.

# Procedure

## Phase 0 — Parse args, verify state

Parse `$ARGUMENTS`:
- First positional = project name
- `--limit N` → cap delegations (smoke-test)
- `--only <slug>` → screen just that one article (useful for re-judging
  after a manual PDF replacement)
- `--reset` → discard `fulltext-decisions.csv` and start over (asks
  for confirmation)

Read `screening/criteria.md`. If empty, refuse.

Determine the candidate set:
- Source = rows of `tiab-decisions.csv` with `decision` ∈ {include, uncertain}
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
    --in  project-review/<name>/screening/1st-pass/raw/<slug>.pdf \
    --out project-review/<name>/screening/1st-pass/markdown/<slug>.md
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
  (`project-review/<name>/screening/1st-pass/markdown/<slug>.md`)

The sub-agent returns ONE line:

```
<decision> | <reason> | <side_use>
```

where:
- `<reason>` for exclusions has the shape
  `<tag>; "<verbatim excerpt>"; <source location>` (mandatory — see
  `.claude/agents/screener-fulltext.md`).
- `<side_use>` is optional. When non-empty, it has either the bare
  category (`intro`, `discussion`, `method`, `reco`, `general`) OR
  the augmented form `<category>; "<quote>"; <location>` (preferred
  — auditable).

**Batch in parallel**: 3–5 sub-agents at a time (sonnet — heavier
than the T/A pass).

Parse each output strictly:

1. Split on top-level `|` → must yield 3 fields (or 2 for the legacy
   format; pad with empty `<side_use>`).
2. Validate `<decision>` ∈ {include, exclude, uncertain}.
3. Validate `<side_use>` head (first `;`-separated token) ∈
   {empty, intro, discussion, method, reco, general}.
4. If `<decision> ≠ exclude` AND `<side_use>` is non-empty, log as
   `error` (protocol violation).
5. For exclusions, verify `<reason>` parses into 3 `;`-separated
   parts (tag, excerpt, location). Otherwise log as `error`.

Append each result to `screening/fulltext-decisions.csv` with columns:

```
slug, doi, pmid, title, decision, tag, excerpt, location, side_use,
side_excerpt, side_location, screener_note, timestamp
```

For `include`, the tag/excerpt/location columns are empty and
side_* are empty. For `exclude`, tag/excerpt/location are mandatory;
side_* are filled only when the screener flagged the article.

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

Default = `a`. For each audited row, show:
- title, slug, decision, tag, excerpt, location, side_use,
  side_excerpt, side_location
- Then ask:
  `keep / flip-to-include / flip-to-exclude / set-side <category> / clear-side / view-body`
- `<category>` ∈ {intro, discussion, method, reco, general}
- `view-body` opens the MD path so the user can verify against the
  excerpt
- Flips and side edits are written to `fulltext-decisions.csv` and
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

### wrong-population (n = K)
- **<slug-1>** — "<verbatim excerpt>" (Methods §"Participants")
- **<slug-2>** — "<excerpt>" (Table 1)
- …

### not-RCT (n = K)
- **<slug-3>** — "<excerpt>" (Methods §"Study design")
- …

(One subsection per criterion tag, each with the per-article evidence.)

## Manual overrides (from audit gate)

- <slug>: flip <orig> → <new> (reason: <user note>)

## Errors to triage

- <slug>: <raw sub-agent output>
```

## Phase 4 — Update PRISMA flowchart

```bash
python tools/screen_prisma.py project-review/<name>
```

Now both passes are reflected in the chart: identified → after-dedup
→ T/A screened → reports sought → reports retrieved → reports
assessed → included.

## Phase 5 — Stage included articles + side references

### 5a — Included → extraction/articles/

For each row in `fulltext-decisions.csv` with `decision = include`:
- Copy `screening/1st-pass/markdown/<slug>.md` to
  `project-review/<name>/extraction/articles/<slug>.md` (cp, never mv
  — the screening register stays intact).
- Update (or create) `project-review/<name>/contexte.md`'s
  `## Source list` block with the slug if it isn't already listed.

### 5b — Side-flagged excludes → extraction/biblio/side/<category>/

For each row in `fulltext-decisions.csv` with `decision = exclude`
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

| Slug | DOI / PMID | Title | Why side (verbatim) | Source location |
|---|---|---|---|---|
| <slug> | <doi> | <title> | <side_excerpt> | <side_location> |
```

T/A-only side flags (rows with no body) are NOT copied here — they
were never read in full, so the recommendation is speculative.
They stay listed in
`extraction/biblio/side/<category>/pending.md` (from `/extractor-screen-tiab`
Phase 4b) for the user to either fetch the body and re-run the
full-text pass with `--only <slug>`, or accept the speculative tag.

This lets the user run `/extractor-table project-review/<name>/`
straight away without an extra manual copy step, with side
references pre-organized by where they belong in the review.

## Phase 6 — Final guidance

```
✓ Full-text screening done.
  Included      : N studies
  See: project-review/<name>/screening/reports/fulltext-report.md
  See: project-review/<name>/screening/reports/prisma-flowchart.md

Articles ready for extraction:
  project-review/<name>/extraction/articles/

Next step:
  /extractor-table project-review/<name>/
```

# Hard constraints

- **NEVER screen an article whose T/A decision was `exclude`** — those
  articles are out by definition. If the user wants to re-judge one,
  they must flip it to `include` in `tiab-decisions.csv` first
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
  reads the FINAL `fulltext-decisions.csv` after user overrides.
- **NEVER assign a side category outside
  {intro, discussion, method, reco, general}**. The orchestrator
  rejects malformed categories as `error`.
