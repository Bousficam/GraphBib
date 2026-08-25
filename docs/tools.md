# Standalone Tools

Reference for the Python helpers that complement the agent. These are
pure scripts - no LLM call unless explicitly noted - and the agent
runs them on user request.

## Domain configuration

GraphBib ships **domain-neutral**. The analyzer tools that need a
field-specific vocabulary read it from a single machine-readable file,
`tools/data/domain.json`, which mirrors the prose taxonomy you declare
in `context.md`. The shipped `domain.json` is the **neutral baseline**
(every section empty), so a fresh clone is not pre-configured for any
field.

Sections:

| Section | Shape | Consumed by |
|---|---|---|
| `regions`, `tracts` | `{key: {canonical, aliases:[plain strings]}}` | `brain_atlas_anchor.py`, `dti_aggregator.py` (tract context) |
| `dti_metrics` | `{CANON: [aliases]}` | `dti_aggregator.py` |
| `outcome_scales` | `{KEY: [regex fragments]}` | `effect_size_aggregator.py` |
| `cohort.{chronicity,side,lesion}` | `{category: [regex fragments]}` | `cohort_tracker.py` |
| `cohort.severity_scale` | `{name, regex}` (2 capture groups = range) | `cohort_tracker.py` |

Convention: `regions` / `tracts` aliases are **plain strings** (the
tools escape them and match on word boundaries); the `dti_metrics` /
`outcome_scales` / `cohort.*` values are **regex fragments**, OR-joined
raw (so numeric patterns like `>\s*6\s*month` work).

To configure a domain:

```bash
# activate a ready-made pack…
cp tools/data/domain.stroke.example.json tools/data/domain.json
# …or edit tools/data/domain.json directly.
```

These four tools are **domain-specific**: with the empty default they
print a "configure your domain" hint and exit (except `cohort_tracker`,
which still reports pooled sample sizes from frontmatter). They only do
domain work once `domain.json` is filled. `tools/organize_sources.py`
keeps its own taxonomy mirror (`FAMILY_FOLDER` / `IMAGING_METHODS`) in
Python, with a safe fallback to `articles/general/` for unknown
families.

## Concept consolidation (batched)

`tools/consolidate_concepts.py` batches concept-page extension: one
LLM call per concept, prompt-cached, integrating all pending sources
that touched that concept since its last update. ~70 % cheaper than
per-ingest extension on homogeneous corpora.

```bash
python tools/consolidate_concepts.py --report   # pending counts
python tools/consolidate_concepts.py <Concept>  # one
python tools/consolidate_concepts.py --since 7d
```

When run periodically, ingest step 8 (concept extension) may defer to
the batched run.

## Replication tracking

Each Academic Paper template includes a `replication_of: "<DOI>"`
frontmatter field - filled at ingest when the paper explicitly
replicates a prior study. `tools/replication_tracker.py` walks
`wiki/sources/`, follows the chains, and reports:

- **Replication chains** - original → replication(s), with consistent
  vs inconsistent findings flagged.
- **Single-study claims** - concept pages whose `## Empirical Evidence`
  rests on one source (a flag for confidence).
- **Replication candidates** - papers that could plausibly replicate
  an existing finding but don't claim it explicitly.

Run periodically; complements `/wiki-lint`.

## Ingest lint - claims against the article (`verify_ingest.py`)

The gate that closes an ingest (step 19 of `docs/workflows/ingest.md`).
For one source, it re-reads every numeric claim written during the
ingest and asks whether it is cited, referenced, and real:

```bash
python tools/verify_ingest.py --source <slug>
python tools/verify_ingest.py --source <slug> --json
python tools/verify_ingest.py --source <slug> --check-page-refs
```

Scope: the source page, plus every wiki page that wikilinks to
`[[<slug>]]` - and on those, only the lines citing this source. So a
concept page fed by ten sources is not re-audited on every ingest.
`--only-source-page` narrows it further; `--pages A.md B.md` names the
targets explicitly.

| Check | Severity | Meaning |
|---|---|---|
| `not_in_article` | high | a number on the page appears nowhere in the converted article |
| `broken_citation` | high | the `[[wikilink]]` carrying the claim resolves to no page |
| `missing_page_ref` | medium | numeric claim with no `(p. N)` on the line or above it |
| `number_reformatted` | low | same value, printed differently (`0.050` vs `0.05`, `+5.0` vs `5.0`) |
| `page_ref_mismatch` | low | with `--check-page-refs`: the number sits on a different printed page |

Exit code 1 when a finding reaches `--fail-on` (default `high`);
`--warn-only` always exits 0.

What it deliberately ignores: page references, figure/table/section
numbers, reference-list markers (`[43, 44]`, `refs 42-48`), ordered-list
markers, DOIs, ISO dates, and digits glued to a word (`P300`). Page
references are inherited from a section heading or from the line
introducing a table or a block quote, which is how the wiki actually
anchors verbatim tables.

Findings are candidates, not verdicts. A `not_in_article` finding is
often a real defect (a transposed table row, a digit dropped in
transcription, a value the agent computed and presented as quoted), but
it can also mean the number was read off a figure, or that the OCR
dropped every minus sign in the paper. Step 19 of the ingest workflow
lists what to do in each case - the one thing never allowed is leaving
an unverifiable number on the page unannotated.

## Figures - pairing and back-fill (`figure_pairs.py`, `backfill_figures.py`)

`figure_pairs.py` is the deterministic half of a `## Figures` section:
it pairs each extracted image with its caption, resolves the page, and
computes the relative path from the wiki page down to the image. Full
rule in `docs/workflows/figures.md`.

```bash
python tools/figure_pairs.py --source <slug>              # inspect
python tools/figure_pairs.py --source <slug> --markdown   # ready to paste
python tools/figure_pairs.py --source <slug> --no-pdf     # skip the PDF pass
```

Page resolution, in order: the converted markdown's own page anchors;
the caption located in the PDF text layer (needs `pymupdf`, optional -
without it the page degrades to unknown, it never crashes); marker's
file-name index. Any of those gives a PDF page, which becomes a
**printed** page through the article's Crossref record - a page range
("111-118") gives an offset, an article number ("118824", modern
Elsevier / Frontiers / PLOS) means the article paginates from 1. With
neither, the output stays `(PDF p. N - confirm the printed page)` or
`(p. ?)`. It never prints a page nobody established.

`backfill_figures.py` applies that to sources ingested before the
workflow existed:

```bash
python tools/backfill_figures.py --all                 # dry run
python tools/backfill_figures.py --all --mode new --apply
python tools/backfill_figures.py --all --mode pages --apply
```

- `new` adds a section where there is none. Purely additive.
- `pages` repairs the page references of an existing section and leaves
  its titles and captions alone. It rewrites a reference only when the
  new one is strictly better, or when the old one is provably the known
  artifact: sections written before this tool printed marker's 0-based
  file-name index as if it were a page, which is exactly `pdf_page - 1`
  for the figure the heading points at.

The wiki is user content and is not versioned, so every file touched is
copied to `.maintenance/figures_backfill_backup/` first (the original,
not the last write).

## DOI lint - is it this paper's DOI? (`verify_doi.py`)

The last gate of an ingest (step 20). A DOI that resolves is not a DOI
that is correct:

```bash
python tools/verify_doi.py --source <slug>
python tools/verify_doi.py --all           # sweep the vault
python tools/verify_doi.py --source <slug> --json
```

It fetches the Crossref record for the page's `doi:` and compares it
with the frontmatter - title (SequenceMatcher >= 0.75), first author,
year (one year of slack for online-first), container title. It also
flags a DOI already carried by another source page, which means the
paper is being ingested twice.

| Check | Severity |
|---|---|
| `doi_title_mismatch` - Crossref returns a different paper | high |
| `doi_not_found` - resolves nowhere, 404 at Crossref and at doi.org | high |
| `doi_malformed` - not a `10.xxxx/...` DOI | high |
| `doi_duplicate` - another source page already carries it | high |
| `doi_missing` - no `doi:` where one is expected | medium (low for thesis / book / note) |
| `doi_author_mismatch`, `doi_year_mismatch` | medium |
| `doi_journal_mismatch`, `slug_family_mismatch` | low |
| `doi_not_in_crossref` - DataCite DOI (dataset, preprint, software) | low |
| `crossref_unreachable` - offline | low, never blocks |

The failure it exists for: `pdf2md/enrich_frontmatter.py` reads a DOI
off the converted PDF, and the first DOI printed on a paper is sometimes
one of ITS references. The page then carries a valid DOI pointing at
somebody else's article, and every APA citation generated from it is
wrong. Resolving on title, not on HTTP status, is the whole point.

When `doi:` is missing, a Crossref bibliographic search on title + first
author proposes a candidate. A candidate is a proposal, never an answer:
confirm it against the article before writing it into the frontmatter.

A Crossref 404 is double-checked against the doi.org proxy before it is
called an error: a dataset DOI (OpenNeuro, Zenodo, figshare) is
registered with DataCite and legitimately absent from Crossref. It
resolves, so it is reported at `low` and never fails an ingest.

Shares `tools/.cache/crossref.json` with `parse_references.py` and
`fetch_oa.py`, so re-runs are free.

## Reference filing (`file_reference.py`)

Step 21 of the ingest, opt-in via `$WIKI_REF_FILING`. Renames a source's
master PDF to its slug and files it into the reference library as
`<library>/<theme>/<slug>.pdf`, then repoints `source_pdf:`.

```bash
python tools/file_reference.py --source <slug>              # dry run
python tools/file_reference.py --source <slug> --apply
python tools/file_reference.py --all                        # sizing
```

The theme is the one the ingest already decided - the page's folder
under `sources/`, then its `intervention_family`, `domain` and tags -
matched against shelves the library **already has**, shallowest first
(a root `Methodo/` is the general shelf; `BCI/Methodo/` is a niche that
would misfile a statistics paper). Matching tolerates the vocabulary
drift between a wiki and a personal library: `methodology` finds
`Methodo/`. With no match the PDF goes to the library root rather than
inventing a folder; `--allow-new-folders` opts into the opposite.

`WIKI_REF_MODE`: `copy` (default), `move`, `rename`.

Two rules keep the library from growing copies of the same paper.
A master **already inside the library** is moved within it, never
copied. And when the paper is **already shelved elsewhere under this
slug**, it is that copy which moves to the right shelf - the master is
not duplicated. A file correctly filed while a second copy still sits
somewhere else is reported as `duplicate` and never deleted: removing a
file from someone's library is their call.

Duplicates are found by file name, which is cheap; one still carrying a
human name ("Mensen 2013 TFCE.pdf") is invisible without hashing the
whole library on every ingest. A name already taken by a *different*
file is a `conflict` and is never overwritten. Applied operations are
journalled to `.maintenance/reference_filing.jsonl` with both paths and
the digest.

The library is not a second `raw/`. `raw/<vault>/papers/` keeps the
converted markdown and the extracted images, which every claim was
verified against and which `source_file` points at.

## Audit trail (git as history)

The wiki is a git repo - `git log` and `git blame` already provide a
free audit trail. Every ingestion appends to `wiki/log.md` with
`## [YYYY-MM-DD] ingest | <Title>`, and each commit touches the wiki
pages the source affected.

`tools/audit_page.py <wiki-page>` wraps `git blame` to map each line
to the ingest commit that introduced it. Useful for:

- Defending a claim during a thesis review.
- Identifying when a concept's definition shifted.
- Untangling synthesis lines that reference multiple sources.
