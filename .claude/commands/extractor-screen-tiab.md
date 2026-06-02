---
description: Run PRISMA pass 1 — title/abstract screening. Dedupes the identified records, fetches missing abstracts via DOI/PMID (PubMed → OpenAlex → Crossref cascade), delegates one decision per record to the `screener-tiab` sub-agent, auto-fetches the PDFs of included articles, writes the per-pass report, and updates the PRISMA flowchart. The sub-agent never reads PDFs — only title + abstract.
argument-hint: "<project-name>  [--force-metadata]  [--limit N]  [--no-fetch]"
---

Run the PRISMA title/abstract screening pass.

Arguments: $ARGUMENTS

# Prerequisites

The project must have a populated screening phase:

```
project-review/<vault>/<name>/
├── contexte.md
└── screening/
    ├── criteria.md                 # MUST exist and be non-empty
    └── identified/
        ├── pubmed.csv              # MUST have at least one CSV here
        ├── scopus.csv              # (one per source database)
        └── …
```

If `criteria.md` is missing, refuse and tell the user to run
`/extractor-screen-init <name>`.

If `identified/` is empty, refuse and explain the expected CSV
columns (title, authors, year, doi, pmid, abstract, journal — title
is the only one strictly required, all others optional).

# Procedure

## Phase 0 — Parse args, verify state

Parse `$ARGUMENTS`:
- First positional = project name
- `--force-metadata` → re-fetch abstracts even when already present
- `--limit N` → cap the screener delegations at N (smoke-test mode)
- `--no-fetch` → skip the metadata fetch and the auto-fetch of PDFs;
  decisions are made strictly from what's already in the CSVs (use
  this on flaky network or after a previous run already populated
  abstracts)

Print the plan:

```
Will run:
  1. Dedupe identified CSVs            → screening/dedup.xlsx
  2. Fetch missing abstracts + heal DOIs → updates dedup.xlsx (cached)
                                          + screening/reports/doi-warnings.md
  3. Screen each record (T/A only)     → screening/tiab-decisions.xlsx
  4. Auto-fetch PDFs of inclusions     → screening/1st-pass/raw/
  5. Write report + update PRISMA      → screening/reports/
Proceed? [Y/n]
```

**Prerequisite — DOI hygiene gate (recommended).** If
`screening/reports/doi-warnings.md` does not exist (Phase 2 has not
yet flagged any DOI issues) AND `dedup.xlsx` is already populated
with rows, suggest running `/extractor-screen-validate <project>`
first — it surfaces wrong-paper DOIs and `anon-YYYY` slugs BEFORE
the T/A pass commits decisions. If the user declines, proceed —
Phase 2 below runs the same DOI healing under the hood, and the
screener-tiab agent's Step 0 will still auto-mark `uncertain` for
mismatches. The standalone validate command is faster (no abstract
cascade) and surfaces issues in a dedicated audit gate.

## Phase 1 — Deduplicate

```bash
python tools/screen_dedupe.py project-review/<vault>/<name>
```

Reports: records read, skipped (no ID / no title), unique after dedup.
Writes `screening/dedup.xlsx` and `screening/reports/dedup-log.md`.

## Phase 2 — Fetch missing abstracts

Skip if `--no-fetch` was passed.

```bash
python tools/screen_fetch_metadata.py project-review/<vault>/<name>
```

(or with `--force` when `--force-metadata` was passed)

This populates the `abstract` column in `dedup.xlsx` from PubMed →
OpenAlex → Crossref, in that order. Cached in
`tools/.cache/screen_metadata.json`. Records with no DOI and no PMID
are left alone.

Summarize the cascade outcome to the user:

```
Abstract fetch:
  already_had_abstract       : K
  fetched_via_pubmed         : K
  fetched_via_openalex       : K
  fetched_via_crossref       : K
  not_found                  : K
```

## Phase 3 — Screen each record (delegate to `screener-tiab`)

Read `screening/criteria.md` and (if present and non-empty)
`background/notes.md` ONCE (passed as context to each delegation).
Read `screening/dedup.xlsx`.

For each row in `dedup.xlsx` (capped by `--limit` if given), spawn
`screener-tiab` with:
- the project's `criteria.md` path
- the project's `background/notes.md` path (or nothing if absent / empty)
- the row's slug, title, abstract, year, journal, authors, doi, pmid
- the row's DOI hygiene flags: `doi_status`, `doi_title_match`,
  `doi_year_match` (when present — these columns are populated by
  Phase 2 or by an explicit `/extractor-screen-validate` run). The
  agent's Step 0 uses them to auto-mark `uncertain` when the DOI
  resolves to a wrong-paper title — saves a full-text fetch on a
  paper that isn't what the abstract claims it is.

The sub-agent returns one line: `<decision> | <reason> | <side_use>`.
Parse it strictly:

1. Split on `|` → must yield exactly 3 fields. If 2, treat as legacy
   format (side_use = empty). If anything else, log as `error`.
2. Validate `<decision>` ∈ {include, exclude, uncertain}.
3. Validate `<side_use>` ∈ {empty, intro, discussion, method, reco,
   general}. If `<decision> ≠ exclude` AND `<side_use>` is non-empty,
   log as `error` (protocol violation).
4. Strip any `# <comment>` from the reason / side_use fields into a
   separate `screener_note` column.

If parsing fails, log as `error` and continue (do NOT crash — the
parent agent gathers all errors at the end).

**Batch in parallel** when sensible (5–10 sub-agents at a time) — the
sub-agent is `haiku` and Read-only.

Append each result to `screening/tiab-decisions.xlsx` with columns
in this order — **slug first, then what the agent did, then article
context** (so a human can scan decisions without scrolling past
metadata):

```
slug, decision, reason, side_use, screener_note,
doi, pmid, title, year, journal, timestamp
```

Where `decision` ∈ {include, exclude, uncertain, error}. Use
`tabular.append_record` from `tools/tabular.py` to append each
row — it handles xlsx natively (load workbook, append, save) and
creates the file with the styled header on the first call. Legacy
CSVs written before this reorder are still parsed correctly
(both `tabular.read_records` and pandas key off the header row,
not column position) — only newly-written rows follow the new
order.

## Phase 3b — User audit gate (mandatory)

After all records are screened, show the user a triage summary:

```
✓ T/A screening complete — N records judged

Decision breakdown:
  include    : K
  uncertain  : K   (default to retrieve)
  exclude    : K
  error      : K   (parsing failure, see below)

Side-use flags (within excludes):
  intro       : K
  discussion  : K
  method      : K
  reco        : K
  general     : K
  (no side)   : K

Top exclusion reasons:
  wrong-population   : K
  not-RCT            : K
  wrong-outcome      : K
  …

Errors to triage (showing first 5):
  - <slug>: <raw sub-agent output>
  …

Options:
  [a]   Audit a sample of decisions (default: random 10% or N=20 max)
  [u]   Show all `uncertain` rows for spot-check
  [e]   Show all `exclude` rows
  [side] Audit all rows with a side_use flag (verify category)
  [c]   Continue to PDF fetch (Phase 4)
  [s]   Stop here — re-run later
```

Default = `a` (sample audit). For each shown row, display in this
order (slug → decision → article info):

```
<slug>
  decision : <decision>
  reason   : <reason>
  side_use : <side_use or "—">
  note     : <screener_note or "—">
  ─
  doi      : <doi or "—">
  pmid     : <pmid or "—">
  title    : <title>
  journal  : <journal> (<year>)
```

Then prompt:

```
keep / flip-to-include / flip-to-exclude / set-side <category> / clear-side
```

Where `<category>` ∈ {intro, discussion, method, reco, general}.
Write all flips and side-edits to `tiab-decisions.xlsx` and log them
at the end of `screening/reports/tiab-report.md` under
`## Manual overrides`.

## Phase 4 — Auto-fetch PDFs for included articles

Skip if `--no-fetch`.

Collect DOIs of `include` AND `uncertain` records (PRISMA: pass T/A
includes to full text). Run with the **full cascade + title
verification + enriched missing.md** options:

```bash
python tools/fetch_oa.py --from-stdin \
    --output-dir project-review/<vault>/<name>/screening/1st-pass/raw/ \
    --with-titles project-review/<vault>/<name>/screening/dedup.xlsx \
    --missing-md  project-review/<vault>/<name>/screening/1st-pass/missing.md \
    < <doi-list>
```

What `fetch_oa.py` does on every DOI:

1. **Provider cascade** (with version preference):
   `unpaywall → openalex → semanticscholar → europepmc →
   publisher-direct → arxiv → biorxiv → core`. Each provider adds
   10–20% of incremental recall over Unpaywall alone (Semantic
   Scholar catches author-uploaded PDFs including a large fraction
   of ResearchGate-hosted copies — direct RG fetch is blocked by
   Cloudflare; Europe PMC is biomedical-specific; arXiv / bioRxiv
   cover preprints; CORE aggregates institutional repos;
   publisher-direct uses URL patterns for PLOS / eLife / MDPI /
   Frontiers / JMIR). Within each provider, ALL candidate URLs
   are tried (OpenAlex often returns 3-5 per DOI from different
   repos). The cascade commits as soon as a
   `publishedVersion`/`acceptedVersion` PDF is found; preprint or
   unknown-version hits are held as a fallback and only kept if
   no later provider does better.
2. **Sanity download** — file > 1 KB AND starts with `%PDF` header.
3. **Title verification** — when pymupdf is installed AND
   `--with-titles` was passed, extracts the first-page title from
   the downloaded PDF and compares it to the row's `title` via
   `crossref.title_similarity`. Sim < 0.5 → rejects the file
   (deletes it, tries the next provider). Closes the wrong-paper
   gap: a landing page disguised as a PDF, or a paper that turned
   out to be a different study, gets discarded instead of
   accepted silently.

Filename convention is `<first-author>-<year>.pdf` — the filenames
will match `dedup.xlsx`'s `slug` for ~all cases.

After the run, `screening/1st-pass/missing.md` is auto-generated
for every unsuccessful DOI with: title, first-author / journal /
year (via Crossref), the list of providers we already tried, a
ResearchGate search URL, and a ready-to-copy reprint-request email
template. The user works down the file, finds the PDFs manually,
and drops them into `screening/1st-pass/raw/<slug>.pdf`.

`fetch_oa_report.json` (next to the PDFs) tracks per-DOI
`attempts` so a future `--retry-failed` run knows which providers
to skip. Use it any time:

```bash
# Re-try every previously-failed DOI without re-trying providers
# that already returned a bad URL on the last run
python tools/fetch_oa.py --output-dir <same dir> --retry-failed \
    --with-titles <project>/screening/dedup.xlsx \
    --missing-md  <project>/screening/1st-pass/missing.md
```

Print the count split to the user: fetched / paywalled /
oa_no_pdf / not_available / verification_failed. Plus the
provider-level success breakdown that `fetch_oa.py` prints — it
tells you which aggregators carry the most weight for your
corpus.

## Phase 4b — Stage side-flagged articles into extraction/biblio/side/

For each row in `tiab-decisions.xlsx` with `decision = exclude` AND
`side_use ≠ empty`:

- If a PDF was successfully fetched in Phase 4 (it shouldn't be —
  Phase 4 only fetched includes — but T/A exclude+side rows MAY
  also get a fetch attempt if the user opts in), copy the PDF to
  `extraction/biblio/side/<category>/raw/<slug>.pdf` and the MD (if
  converted) to `extraction/biblio/side/<category>/<slug>.md`.
- Otherwise, append the row to
  `extraction/biblio/side/<category>/pending.md` so the user knows
  to fetch / convert manually later. Format:

```markdown
| Slug | Side category | Why (T/A note) | DOI / PMID | Title |
|---|---|---|---|---|
| <slug> | <side_use> | <reason from screener_note or empty> | <doi> | <title> |
```

The full-text pass (`/extractor-screen-fulltext`) will re-evaluate
side-use on a more reliable basis (body); rows with a body in
`screening/1st-pass/markdown/` already are not duplicated here —
they're handled by the full-text pass.

Note: most T/A `exclude + side` flags are speculative (decided from
abstract only). The full-text pass overrides them.

## Phase 5 — Convert PDFs to MD (for the upcoming full-text pass)

For each downloaded PDF in `screening/1st-pass/raw/<slug>.pdf` whose
MD counterpart `screening/1st-pass/markdown/<slug>.md` is missing,
convert:

```bash
python pdf2md/marker_convert.py \
    --in  project-review/<vault>/<name>/screening/1st-pass/raw/<slug>.pdf \
    --out project-review/<vault>/<name>/screening/1st-pass/markdown/<slug>.md
```

(Or whichever conversion entrypoint matches `/wiki-convert`'s
plumbing in your install — `docs/workflows/conversion.md` is the
reference.)

If the conversion fails or marker is not installed, log it and
continue — the user can drop manually-converted MDs there later, or
run `/wiki-convert screening/1st-pass/raw/` separately.

## Phase 6 — Write the per-pass report

`screening/reports/tiab-report.md` — narrative summary:

```markdown
# Title / Abstract screening report — <project-name>

> Auto-generated by `/extractor-screen-tiab` on YYYY-MM-DD.

## Summary

- Records identified (all DBs)       : N
- After dedup                        : N
- Title/abstract screened            : N
- Included for full-text             : N (include + uncertain)
- Excluded at T/A                    : N

## Exclusions by reason

| Tag | n | % of T/A excluded |
|---|---|---|
| wrong-population | K | K% |
| not-RCT          | K | K% |
| …                | … | …  |

## Auto-fetch outcome

- PDFs successfully retrieved        : N
- Paywalled / not found              : N (see `1st-pass/missing.md`)

## Manual overrides (from audit gate)

- <slug>: flip <orig> → <new> (reason: <user note>)
- …

## Errors to triage

- <slug>: <raw sub-agent output>
- …
```

## Phase 7 — Update PRISMA flowchart

```bash
python tools/screen_prisma.py project-review/<vault>/<name>
```

Overwrites `screening/reports/prisma-flowchart.md` with the current
counts.

## Phase 8 — Final guidance

```
✓ T/A screening done.
  See: project-review/<vault>/<name>/screening/reports/tiab-report.md
  See: project-review/<vault>/<name>/screening/reports/prisma-flowchart.md

Next step:
  - Manually fetch any paywalled PDFs listed in
    project-review/<vault>/<name>/screening/1st-pass/missing.md
    and drop them into screening/1st-pass/raw/<slug>.pdf
  - Then run:
    /extractor-screen-fulltext <name>
```

# Hard constraints

- **NEVER read PDFs in this command.** Pass 1 is T/A only. Even if a
  PDF is already in `1st-pass/raw/`, do not pass its content to the
  screener — pass only the row's title + abstract.
- **NEVER auto-overwrite `dedup.xlsx` once decisions exist.** If
  `tiab-decisions.xlsx` is non-empty, REFUSE to re-run dedup unless
  the user passes `--reset-dedup` (which the user must type
  explicitly).
- **NEVER skip the audit gate.** Phase 3b is mandatory. Auto-pilot
  T/A screening leads to silent over-/under-inclusion. The audit
  sample is small (10% or 20 max), so the gate stays light.
- **Default `uncertain` → retrieve.** This command moves `uncertain`
  to the full-text fetch list. The user can override at the audit
  gate. Do NOT silently treat `uncertain` as `exclude`.
- **NEVER claim screening is "done" before the PRISMA flowchart is
  regenerated.** The flowchart is the canonical state of the
  screening — it must be in sync with the CSVs at every reported
  milestone.
- **PASS `background/notes.md` to every screener-tiab invocation**
  when the file exists and is non-empty. Sub-agents must have the
  same context across all decisions for consistency. If the file is
  absent or empty, skip silently — do NOT fabricate context.
