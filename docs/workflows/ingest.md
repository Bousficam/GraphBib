# Ingest Workflow

Triggered by: *"ingest <file>"* or `/wiki-ingest`. Most ingestions are
delegated to the `ingester` sub-agent (`Agent(subagent_type=ingester, …)`),
which enforces this 20-step procedure non-negotiably.

## Supported formats

Markdown (`.md`) ingested directly. Non-markdown files auto-converted
beforehand:

- **PDFs (papers, theses)** → `pdf2md/pdf2md_marker.py` (with
  `pdf2md_fallback.py` for failures), then
  `pdf2md/enrich_frontmatter.py` for Crossref bibliographic metadata.
- **Other formats** (`.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`, …) →
  markitdown.

## What an ingest does NOT do

Two things that used to happen here are now out of scope. Doing them
during an ingest is a defect, not a bonus:

- **Reading the reference list or the abbreviation list** - see step 1.
- **Citation snowball** (`cites:`, `## Cites`, `## Notable References`,
  "candidates not yet in the wiki") - a standalone workflow now, run on
  demand: `docs/workflows/snowball.md` / `/wiki-snowball`. An ingest
  never surfaces snowball candidates and never reports a count of them.

## Steps (in order)

### 1 - Read the source, minus the parts that carry no claim

Read the source file via the Read tool (auto-convert non-markdown),
**skipping two blocks entirely**:

- the **reference list / bibliography** - `## References`,
  `## Bibliography`, `Works Cited`, `Littérature citée`, or an unheaded
  run of numbered `[12] Author A, Author B. Title...` entries at the end;
- the **abbreviation / acronym list** - `List of Abbreviations`,
  `Glossary`, `Acronyms`, `Liste des abréviations`, and the
  abbreviation table some journals print on page 1.

Neither block contains an extractable claim, and together they are often
a third to a half of a converted paper (nearly all of it for a thesis).
Reading them buys nothing and spends the context window that the Results
and Methods sections need.

Locate the cut before reading:

```bash
grep -n -i -E '^#{1,4} *(references|bibliography|works cited|literature cited|réf|abbrevi|list of abbreviations|glossary|acronyms|nomenclature)' <source.md>
wc -l <source.md>
```

then `Read(file_path=..., limit=<first matching line - 1>)`, and read any
appendix that follows the reference list as a separate ranged Read. For
a long document, apply `docs/workflows/long-document-ingestion.md`.

Consequences, all of them intended:

- **Do not write a `## References` section** on the wiki page. The
  bibliography stays in `raw/`, where the snowball workflow reads it.
- **`## Cites` is left as the template's placeholder**, empty. It is
  populated later by `/wiki-snowball`, never by the ingest.
- **Expand acronyms from their first use in the prose** ("motor imagery
  (MI)"), which is where the paper defines them anyway. An acronym the
  body never expands is kept verbatim and flagged
  *"(not expanded in the body)"* - never guessed from an abbreviation
  table you did not read, and never invented.
- In-text citation markers stay useful: `[24]` or "(Carlsson et al.
  2018)" in the body is transcribed as the paper prints it, with
  `reported via` provenance per the Indirect Citation Rule. Resolving
  `[24]` to a full reference is the snowball workflow's job.

### 2 - Read context

`wiki/index.md`, `wiki/overview.md`, plus any obviously related
concept / method pages already in the wiki.

### 3 - Choose the source template

Pick by *study design* (visible in title / abstract / methods cues),
then **read the template file before writing**:

| Detected type | Template |
|---|---|
| Empirical: RCT, cohort, cross-sectional, case-control, case-series | `docs/templates/source-academic-paper.md` |
| Systematic review (with or without meta-analysis), PRISMA-aware | `docs/templates/source-systematic-review.md` |
| Narrative review (no systematic search, thematic structure) | `docs/templates/source-narrative-review.md` |
| Scoping review, PRISMA-ScR, evidence mapping | `docs/templates/source-scoping-review.md` |
| Methodological paper (introduces new method / protocol / pipeline) | `docs/templates/source-methodological-paper.md` |
| Theoretical / conceptual / framework paper (no data) | `docs/templates/source-theoretical-paper.md` |
| Thesis (PhD / MSc / HDR) | `docs/templates/source-thesis.md` |
| Academic book / monograph / edited volume / handbook / textbook (`raw/<vault>/books/*`) | `docs/templates/source-book.md` (parent); chapters of edited volumes use `source-academic-paper.md` with the `parent_book` / `book_editors` / `pages_in_book` extra frontmatter fields documented in `source-book.md` |
| Lab notes / personal notes (`raw/<vault>/notes/*`) | reuse `source-academic-paper.md`, omit fields that don't apply; or use `docs/templates/diary.md` / `docs/templates/meeting.md` |

**Detection cues** when the type isn't explicit:

- **PRISMA flow diagram** + risk-of-bias table → systematic review.
- **PRISMA-ScR flow** + concept map / typology / no quality
  appraisal → scoping review.
- **No Methods section**, thematic sub-headings, *"we discuss"* framing
  → narrative review.
- **No Methods section**, postulates / definitions / model architecture
  → theoretical paper.
- **Validation against a reference method**, software / algorithm
  description → methodological paper.

Set the `study_design:` frontmatter field accordingly so that downstream
tools (`tools/method_matrix.py`, `cohort_tracker.py`, etc.) can filter
on type.

Always also read `docs/rules/depth-completeness.md` (depth expectations,
self-critique gate) and `docs/rules/citation.md` (Indirect Citation
Rule, `reported via [[X]]` provenance, knowledge construction from
introductions).

### 4 - Generate citation_apa and bibtex_key

From the frontmatter (`authors`, `year`, `title`, `journal` or
`university`, `doi`). APA 7.

### 5 - Write the source page to its thematic destination

Apply the routing rule from `docs/workflows/source-organization.md`:

- Theses → `wiki/sources/theses/<slug>/<slug>.md`.
- Reviews → `wiki/sources/articles/reviews/{systematic|scoping|narrative}/<slug>.md`.
- Empirical with intervention → `wiki/sources/articles/<family>/<slug>.md`
  (or `<family>/<subfamily>/<slug>.md` if the subfamily folder already exists).
- Methodological / theoretical → `wiki/sources/articles/{methodology|theory}/<slug>.md`.
- Imaging-only observational → `wiki/sources/articles/imaging/<modality>/<slug>.md`.
- Otherwise → `wiki/sources/articles/general/<slug>.md`.

Apply the Citation Rule strictly. Distinguish
`## Background (from cited literature)` from `## Results (this paper's
findings)` - the **Indirect Citation Rule** applies.

Every claim carries its page reference. A page reference written once on
a section heading or on the line introducing a table or a quote covers
what follows it; a claim that sits under neither must carry its own.
Step 19 checks this mechanically.

Set `intervention_family` (principal therapy) and `intervention_subfamily`
(paradigm - `mi-bci`, `rtms`, `itbs`, …) so `tools/organize_sources.py`
can later promote subfamilies to tier-2 folders.

### 6 - Entity pages - OFF BY DEFAULT (opt-in)

**Do NOT create author or institution entity pages by default.**
Authorship is already captured verbatim in the source page's
`authors:` / `editors:` frontmatter, which is sufficient for
attribution and citation. Creating an `wiki/entities/<Author>.md` for
every author bloats the graph with hundreds of low-signal stubs.

Only create or update an entity page when **explicitly requested** by
the user, or when an author/institution is itself a *subject* of the
wiki (e.g. a named protocol, lab, or person the research is *about* - 
not merely a paper's author). When in doubt, skip it.

If an entity page already exists, you may add the new source to its
`## Sources in This Wiki` list, but do not create new ones.

### 7 - Update concept pages

For each key concept discussed, **read the existing page and ADD to
it** (sub-claim under `## Empirical Evidence`, variant under
`## Definitions`, framework under `## Theoretical Foundations`, etc.).
Verifying the page exists is NOT enough; it must be extended with this
source's contribution.

### 8 - Update method pages

For each method in the source's `methods:` frontmatter, the
`## Used In This Wiki` entry MUST include a 2-sentence description of
HOW THIS PAPER USED IT (parameters, sample, deviations from standard)
 - not a bare wikilink. **Reminder**: methods are *measurement
instruments* (EEG, FuglMeyer, MEP, KVIQ). Treatments belong on
intervention pages - see step 9.

### 9 - Update intervention pages

If the source describes a therapeutic intervention (BCI, TMS, mirror
therapy, robot training, …), ensure
`wiki/interventions/<intervention-slug>.md` exists. Tag the source's
frontmatter with `intervention_family: "BCI"` (or similar) so the
intervention page can aggregate. When ≥ 2 sources share an
`intervention_family`, the intervention page should reach full depth
(Definition → Identified Studies → Pooled Outcomes → Best Practices).

### 10 - Update recommendation pages

If the source proposes recommendations, route them to
`wiki/recommendations/<topic>.md` (create if needed) under the
appropriate evidence-strength section.

**For guidelines, meta-analyses, or consensus statements**, this step
is critical: enumerate **every** recommendation from the paper's
recommendation tables (don't summarize), preserve evidence levels
(A / B / C) verbatim, and create one `recommendations/<topic>.md` per
condition / protocol family. See `docs/rules/depth-completeness.md` →
*Guidelines, meta-analyses, consensus statements*.

### 11 - Update question pages

If the source identifies an open question or explicit gap, append to
`wiki/questions/<slug>.md` (create if needed).

### 12 - Flag contradictions

Flag contradictions with existing wiki content explicitly, with page
numbers on both sides.

### 13 - Update wiki/index.md

Add entries under all touched sections.

### 14 - Update wiki/overview.md

Update only if the synthesis warrants revision.

### 15 - Append to wiki/log.md

Format: `## [YYYY-MM-DD] ingest | <Title>`.

### 16 - Self-critique gate

Run the **Self-critique gate** defined in
`docs/rules/depth-completeness.md` (re-read the source page, verify
exhaustive extraction; for guidelines verify every recommendation is
enumerated). Expand any incomplete section by re-reading the source.

Then check broken `[[wikilinks]]`, verify all new pages are listed in
`index.md`, and run `tools/update_cited_by.py` to refresh `## Cited By`
sections wiki-wide.

### 17 - Slug-align the raw input

```bash
python tools/audit_raw.py --source <slug> --apply
```

Renames the raw PDF / converted MD / extracted-images dir to match the
slug (`raw/<vault>/papers/<slug>.{pdf,md}` + `<slug>_images/`) and
rewrites the `source_file` / `source_pdf` frontmatter pointers. Doing it
here keeps the raw side aligned per ingest, and step 19 needs
`source_file` to point at the right article.

### 18 - Figures

Both converters extract images into `raw/<vault>/papers/<slug>_images/`
(marker names them `_page_3_Figure_2.jpeg`, Mistral `img-7.jpeg`). If
that directory exists, write the `## Figures` section yourself - **do
not delegate**. A sub-agent cannot spawn another sub-agent, so an
`Agent(subagent_type=source-illustrator, ...)` call from inside an
ingest fails silently and the source ships with no figures.

```bash
python tools/figure_pairs.py --source <slug>              # inspect
python tools/figure_pairs.py --source <slug> --markdown   # ready to paste
```

The tool pairs each image with its caption (multi-panel runs included),
recovers the page across both naming conventions - correcting a marker
PDF page into the printed page with the article's Crossref range -
computes the relative path from the page down to the image, and filters
tables, duplicates and page furniture. Exit code 1 means nothing to
illustrate: skip the step.

Then read what it produced, drop any figure that is clearly not one,
check the links resolve, and paste the section after `## Results` and
before `## Cites`. Captions are verbatim; a page the tool could not
recover stays `(p. ?)` or `(PDF p. N - confirm the printed page)` until
someone checks the article. Never replace either with a plausible
number.

Full rule, including who runs this in the other contexts:
`docs/workflows/figures.md`.

### 19 - Minimal ingest lint: is every result real?

The last gate, and the one that fails the ingest. Every result written
during this session must be **cited**, **referenced**, and **actually
present in the article that was ingested**.

```bash
python tools/verify_ingest.py --source <slug>
```

The tool checks the source page plus every wiki page that links to
`[[<slug>]]` (on those, only the lines citing this source), and reports
per numeric claim:

| Check | Severity | Meaning |
|---|---|---|
| `not_in_article` | high | a number on the page is nowhere in the converted article |
| `broken_citation` | high | the `[[wikilink]]` carrying the claim resolves to no page |
| `missing_page_ref` | medium | numeric claim with no `(p. N)`, on the line or above it |
| `number_reformatted` | low | same value, printed differently (`0.050` vs `0.05`) |
| `page_ref_mismatch` | low | opt-in `--check-page-refs`: the number sits on another page |

**Findings are candidates, not verdicts.** For each one, re-read the
flagged line against the article and resolve it - do not just re-run the
tool:

- **Number wrong** (transposed row, dropped digit, wrong column) → fix
  the number on the page.
- **Number computed by you** (a percentage, a difference, a duration the
  paper never prints) → either remove it or mark it explicitly as
  derived, e.g. *"≈19.5 min (derived: 20 min total minus the 30 s ramp,
  not stated as such p. S81)"*. Numbers the paper does not print must
  never read as quotations.
- **Number read off a figure** (PRISMA counts, forest plot values) →
  keep it and say where it came from: *"(read from Fig. 4, p. 10; not in
  the text layer)"*.
- **Conversion artefact** - the value is in the PDF but the OCR shredded
  the table, or dropped every minus sign → say so on the page and in the
  Extraction Checklist, per the OCR fidelity rule. Ask for a second OCR
  pass with the other backend rather than keeping a number nobody can
  check. Do not silently keep it.
- **Missing page reference** → add it. If the claim is genuinely a
  synthesis across the paper, say so in words rather than dropping the
  reference.

Re-run until `high` is 0 (exit code 0), or, when a `high` finding is a
documented conversion artefact, until every remaining one is explicitly
annotated on the page.

### 20 - Last lint: is the DOI this paper's DOI?

```bash
python tools/verify_doi.py --source <slug>
```

A DOI that resolves is not the same as a DOI that is correct. The
failure this catches is silent: `enrich_frontmatter.py` reads a DOI off
the converted PDF, and the first DOI printed on a paper is sometimes one
of **its references** or the journal's own registration. The page then
carries a valid Crossref DOI pointing at somebody else's article, and
every APA citation generated from it is wrong. So the check is not "does
it resolve" but "does Crossref return **this** paper".

| Check | Severity | Meaning |
|---|---|---|
| `doi_title_mismatch` | high | Crossref returns a different paper (title similarity < 0.75) |
| `doi_not_found` | high | the DOI resolves nowhere - 404 at Crossref AND at doi.org |
| `doi_malformed` | high | not a `10.xxxx/...` DOI |
| `doi_duplicate` | high | another source page already carries this DOI - the paper is already in the wiki |
| `doi_missing` | medium | no `doi:` on a page type that should have one (low for a thesis / book / note) |
| `doi_author_mismatch` | medium | first author differs from Crossref |
| `doi_year_mismatch` | medium | year differs by more than one (one year of slack for online-first) |
| `doi_journal_mismatch` | low | container title differs |
| `slug_family_mismatch` | low | the slug does not start with the Crossref first author |
| `doi_not_in_crossref` | low | registered with DataCite (dataset, preprint, software) - valid, just not cross-checkable here |
| `crossref_unreachable` | low | offline - re-run later, never a blocker |

How to resolve:

- **`doi_title_mismatch` / `doi_duplicate`** → stop and check the PDF's
  own header. If the DOI belongs to a cited reference, replace it with
  the paper's real DOI **read from the article**, then regenerate
  `citation_apa` and `bibtex_key` (step 4). If the paper really is
  already in the wiki under another slug, this ingest is a duplicate:
  report it and let the user decide (`/wiki-remove` on one of the two).
- **`doi_missing`** → the tool proposes a Crossref candidate from the
  title and first author. A candidate is a proposal, not an answer:
  confirm it against the article before writing it in. Bibliographic
  frontmatter is copied verbatim from the source, never invented. A
  thesis, a book or a lab note with no DOI is normal - leave the field
  empty.
- **`doi_author_mismatch` / `doi_year_mismatch`** → usually a
  frontmatter typo or an author order the converter scrambled; fix the
  page, not the DOI. A year off by one on an online-first article is
  tolerated already, so a reported mismatch is a real one.
- **`doi_not_in_crossref`** → nothing to fix. An OpenNeuro / Zenodo /
  figshare DOI is registered with DataCite, not Crossref; it resolves,
  so it is correct. Check the metadata against the landing page instead.
- **`crossref_unreachable`** → say so in the report and move on. Offline
  never blocks an ingest.

Finish when `high` is 0. Then print the change summary:
*N concepts updated, M methods touched, K recommendations refined,
L claims corrected by the lint, DOI verified against Crossref*.

## For theses specifically

Theses are dense citation hubs, but harvesting that hub is no longer
part of the ingest:

- `## Notable References` is **left empty** at ingest time. Filling it
  means reading the bibliography, which step 1 forbids. Run
  `/wiki-snowball <thesis-slug>` afterwards to populate it and to list
  the references not yet in the wiki.
- The ingest never proposes follow-up papers to read and never
  auto-ingests one.

For long theses (≥ 100 pages), use the
`docs/workflows/long-document-ingestion.md` split workflow instead of
ingesting in one pass.
