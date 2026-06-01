# Ingest Workflow

Triggered by: *"ingest <file>"* or `/wiki-ingest`. Most ingestions are
delegated to the `ingester` sub-agent (`Agent(subagent_type=ingester, …)`),
which enforces this 16-step procedure non-negotiably.

## Supported formats

Markdown (`.md`) ingested directly. Non-markdown files auto-converted
beforehand:

- **PDFs (papers, theses)** → `pdf2md/pdf2md_marker.py` (with
  `pdf2md_fallback.py` for failures), then
  `pdf2md/enrich_frontmatter.py` for Crossref bibliographic metadata.
- **Other formats** (`.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`, …) →
  markitdown.

## Steps (in order)

### 1 — Read the source

Read the source file fully via the Read tool (auto-convert non-markdown).

### 2 — Read context

`wiki/index.md`, `wiki/overview.md`, plus any obviously related
concept / method pages already in the wiki.

### 3 — Choose the source template

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

### 4 — Generate citation_apa and bibtex_key

From the frontmatter (`authors`, `year`, `title`, `journal` or
`university`, `doi`). APA 7.

### 5 — Write the source page to its thematic destination

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
findings)` — the **Indirect Citation Rule** applies.

Set `intervention_family` (principal therapy) and `intervention_subfamily`
(paradigm — `mi-bci`, `rtms`, `itbs`, …) so `tools/organize_sources.py`
can later promote subfamilies to tier-2 folders.

### 6 — Parse references

Run `tools/parse_references.py`: extract DOIs from the source's
`## References` / `## Bibliography`, populate `cites:` in the
frontmatter, fill `## Cites` with wikilinks for in-wiki papers and
raw DOIs for snowball candidates.

The script has three phases (each opt-in):

- default — regex extraction (offline, fast).
- `--validate` — checks each extracted DOI against Crossref; invalid
  DOIs (often broken at line breaks by marker) are dropped.
- `--curate` — for entries with no valid DOI, runs a Crossref
  bibliographic free-text search to recover the canonical DOI;
  accepted only when relevance score and title overlap pass thresholds.
  Recovered DOIs are tracked separately in `cites_curated:` for audit.

Run `--curate` after the conversion pipeline, on the full corpus:

```bash
python tools/parse_references.py --curate --all wiki/sources/
```

A local cache (`tools/.cache/doi_validation.json`) makes re-runs nearly
free.

### 7 — Update entity pages — MANDATORY

Every paper has at least one author. Create or update
`wiki/entities/<FirstAuthor>.md` and the institution page when
identifiable. **A wiki with zero entities after multiple ingests means
this step is being silently skipped — do not let that happen.**

### 8 — Update concept pages

For each key concept discussed, **read the existing page and ADD to
it** (sub-claim under `## Empirical Evidence`, variant under
`## Definitions`, framework under `## Theoretical Foundations`, etc.).
Verifying the page exists is NOT enough; it must be extended with this
source's contribution.

### 9 — Update method pages

For each method in the source's `methods:` frontmatter, the
`## Used In This Wiki` entry MUST include a 2-sentence description of
HOW THIS PAPER USED IT (parameters, sample, deviations from standard)
— not a bare wikilink. **Reminder**: methods are *measurement
instruments* (EEG, FuglMeyer, MEP, KVIQ). Treatments belong on
intervention pages — see 9b.

### 9b — Update intervention pages

If the source describes a therapeutic intervention (BCI, TMS, mirror
therapy, robot training, …), ensure
`wiki/interventions/<intervention-slug>.md` exists. Tag the source's
frontmatter with `intervention_family: "BCI"` (or similar) so the
intervention page can aggregate. When ≥ 2 sources share an
`intervention_family`, the intervention page should reach full depth
(Definition → Identified Studies → Pooled Outcomes → Best Practices).

### 10 — Update recommendation pages

If the source proposes recommendations, route them to
`wiki/recommendations/<topic>.md` (create if needed) under the
appropriate evidence-strength section.

**For guidelines, meta-analyses, or consensus statements**, this step
is critical: enumerate **every** recommendation from the paper's
recommendation tables (don't summarize), preserve evidence levels
(A / B / C) verbatim, and create one `recommendations/<topic>.md` per
condition / protocol family. See `docs/rules/depth-completeness.md` →
*Guidelines, meta-analyses, consensus statements*.

### 11 — Update question pages

If the source identifies an open question or explicit gap, append to
`wiki/questions/<slug>.md` (create if needed).

### 12 — Flag contradictions

Flag contradictions with existing wiki content explicitly, with page
numbers on both sides.

### 13 — Update wiki/index.md

Add entries under all touched sections.

### 14 — Update wiki/overview.md

Update only if the synthesis warrants revision.

### 15 — Append to wiki/log.md

Format: `## [YYYY-MM-DD] ingest | <Title>`.

### 16 — Post-ingest validation + Self-critique gate

First run the **Self-critique gate** defined in
`docs/rules/depth-completeness.md` (re-read source page, verify
exhaustive extraction; for guidelines verify every recommendation
enumerated). Expand any incomplete section by re-reading the source.

Then check broken `[[wikilinks]]`, verify all new pages are in
`index.md`, run `tools/update_cited_by.py` to refresh `## Cited By`
sections wiki-wide, and print a change summary including counts:
*N concepts updated, M methods touched, K recommendations refined,
J snowball candidates surfaced*.

## For theses specifically — citation snowball

Theses are dense citation hubs. After ingesting a thesis:

- **Surface high-value references** in the `## Notable References`
  section of the source page (10–30 references the thesis builds on
  heavily).
- **Suggest snowball ingestion**: at the end of the post-ingest
  summary, list the references *not yet in the wiki* and ask the user
  whether to ingest them next. Do not auto-ingest.

For long theses (≥ 100 pages), use the
`docs/workflows/long-document-ingestion.md` split workflow instead of
ingesting in one pass.
