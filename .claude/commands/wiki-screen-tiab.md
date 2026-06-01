---
description: Run PRISMA pass 1 — title/abstract screening. Dedupes the identified records, fetches missing abstracts via DOI/PMID (PubMed → OpenAlex → Crossref cascade), delegates one decision per record to the `screener-tiab` sub-agent, auto-fetches the PDFs of included articles, writes the per-pass report, and updates the PRISMA flowchart. The sub-agent never reads PDFs — only title + abstract.
argument-hint: "<project-name>  [--force-metadata]  [--limit N]  [--no-fetch]"
---

Run the PRISMA title/abstract screening pass.

Arguments: $ARGUMENTS

# Prerequisites

The project must have a populated screening phase:

```
project-review/<name>/
├── contexte.md
└── screening/
    ├── criteria.md                 # MUST exist and be non-empty
    └── identified/
        ├── pubmed.csv              # MUST have at least one CSV here
        ├── scopus.csv              # (one per source database)
        └── …
```

If `criteria.md` is missing, refuse and tell the user to run
`/wiki-screen-init <name>`.

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
  1. Dedupe identified CSVs            → screening/dedup.csv
  2. Fetch missing abstracts           → updates dedup.csv (cached)
  3. Screen each record (T/A only)     → screening/tiab-decisions.csv
  4. Auto-fetch PDFs of inclusions     → screening/1st-pass/raw/
  5. Write report + update PRISMA      → screening/reports/
Proceed? [Y/n]
```

## Phase 1 — Deduplicate

```bash
python tools/screen_dedupe.py project-review/<name>
```

Reports: records read, skipped (no ID / no title), unique after dedup.
Writes `screening/dedup.csv` and `screening/reports/dedup-log.md`.

## Phase 2 — Fetch missing abstracts

Skip if `--no-fetch` was passed.

```bash
python tools/screen_fetch_metadata.py project-review/<name>
```

(or with `--force` when `--force-metadata` was passed)

This populates the `abstract` column in `dedup.csv` from PubMed →
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

Read `screening/criteria.md` ONCE (for context to pass to each
delegation). Read `screening/dedup.csv`.

For each row in `dedup.csv` (capped by `--limit` if given), spawn
`screener-tiab` with:
- the project's `criteria.md` path
- the row's slug, title, abstract, year, journal, authors, doi, pmid

The sub-agent returns one line: `<decision> | <reason>`. Parse it
strictly. If parsing fails, log as `error` and continue (do NOT
crash — the parent agent gathers all errors at the end).

**Batch in parallel** when sensible (5–10 sub-agents at a time) — the
sub-agent is `haiku` and Read-only.

Append each result to `screening/tiab-decisions.csv` with columns:

```
slug, doi, pmid, title, year, journal, decision, reason, screener_note, timestamp
```

Where `screener_note` is anything after the `#` comment in the
sub-agent's reason field. `decision` ∈ {include, exclude, uncertain,
error}.

## Phase 3b — User audit gate (mandatory)

After all records are screened, show the user a triage summary:

```
✓ T/A screening complete — N records judged

Decision breakdown:
  include    : K
  uncertain  : K   (default to retrieve)
  exclude    : K
  error      : K   (parsing failure, see below)

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
  [c]   Continue to PDF fetch (Phase 4)
  [s]   Stop here — re-run later
```

Default = `a` (sample audit). For each shown row, ask
`keep / flip-to-include / flip-to-exclude`. Write all flips to
`tiab-decisions.csv` and log them at the end of
`screening/reports/tiab-report.md` under `## Manual overrides`.

## Phase 4 — Auto-fetch PDFs for included articles

Skip if `--no-fetch`.

Collect DOIs of `include` AND `uncertain` records (PRISMA: pass T/A
includes to full text). Run:

```bash
python tools/fetch_oa.py --from-stdin \
    --output-dir project-review/<name>/screening/1st-pass/raw/ \
    < <doi-list>
```

(The existing `tools/fetch_oa.py` handles Unpaywall + Crossref
download. Filename convention is `<first-author>-<year>.pdf` — the
filenames will match `dedup.csv`'s `slug` for ~all cases.)

Reconcile the downloaded PDFs against the inclusion list. Anything
that didn't download → write a row in
`screening/1st-pass/missing.md` with:
- slug
- DOI / PMID
- title (truncated to 80 chars)
- "Where to try" (suggested manual sources: institutional access,
  ResearchGate, author email, Sci-Hub disclaimer per local law)
- "User note" (empty)

Print the count split: fetched / paywalled / failed.

## Phase 5 — Convert PDFs to MD (for the upcoming full-text pass)

For each downloaded PDF in `screening/1st-pass/raw/<slug>.pdf` whose
MD counterpart `screening/1st-pass/markdown/<slug>.md` is missing,
convert:

```bash
python pdf2md/marker_convert.py \
    --in  project-review/<name>/screening/1st-pass/raw/<slug>.pdf \
    --out project-review/<name>/screening/1st-pass/markdown/<slug>.md
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

> Auto-generated by `/wiki-screen-tiab` on YYYY-MM-DD.

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
python tools/screen_prisma.py project-review/<name>
```

Overwrites `screening/reports/prisma-flowchart.md` with the current
counts.

## Phase 8 — Final guidance

```
✓ T/A screening done.
  See: project-review/<name>/screening/reports/tiab-report.md
  See: project-review/<name>/screening/reports/prisma-flowchart.md

Next step:
  - Manually fetch any paywalled PDFs listed in
    project-review/<name>/screening/1st-pass/missing.md
    and drop them into screening/1st-pass/raw/<slug>.pdf
  - Then run:
    /wiki-screen-fulltext <name>
```

# Hard constraints

- **NEVER read PDFs in this command.** Pass 1 is T/A only. Even if a
  PDF is already in `1st-pass/raw/`, do not pass its content to the
  screener — pass only the row's title + abstract.
- **NEVER auto-overwrite `dedup.csv` once decisions exist.** If
  `tiab-decisions.csv` is non-empty, REFUSE to re-run dedup unless
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
