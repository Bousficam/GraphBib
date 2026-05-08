# LLM Wiki Agent — Academic Edition

This wiki is an **academic knowledge base** for research on **stroke motor
rehabilitation via MI-BCI and TMS**, grounded in neural control theory and
white-matter anatomy (DTI). It is maintained entirely by Claude Code: open
this repo in Claude Code and talk to it.

The agent's three jobs, in priority order:

1. **Synthesize concepts** across the literature with traceable links.
2. **Map methodologies and recommendations** so the wiki answers *"how is X
   measured/intervened on?"* and *"what does the literature recommend?"*.
3. **Cite sources rigorously** — every factual claim points to a `[[source]]`
   with a page number, ready for APA reuse.

---

## Slash Commands (Claude Code)

| Command | What to say |
|---|---|
| `/wiki-ingest` | `ingest raw/papers/<file>.md` |
| `/wiki-convert` | `/wiki-convert "/path/to/PDF/library"` (PDF → Markdown pipeline) |
| `/wiki-query` | `query: what does the literature say about MI-BCI for chronic stroke?` |
| `/wiki-review` | `review topic: corticospinal integrity and motor recovery` |
| `/wiki-cite` | `cite: TMS-induced plasticity in M1` (returns 3-5 APA refs) |
| `/wiki-suggest-readings` | `suggest readings for: MotorImagery` (snowball candidates) |
| `/wiki-health` | `health` (fast, every session) |
| `/wiki-lint` | `lint the wiki` (expensive, periodic) |
| `/wiki-graph` | `build the knowledge graph` |

Plain English works too — describe what you want and Claude maps it to the
right workflow:

- *"Ingest this thesis: raw/theses/dupont-2023.md"*
- *"What methods are used to assess corticospinal tract integrity?"*
- *"Build a literature review on motor imagery training in chronic stroke"*
- *"Show me the open questions around TMS dose-response"*

Claude Code reads this file automatically and follows the workflows below.

---

## Sub-agents (delegation)

Six specialized sub-agents live in `.claude/agents/`. Delegate via the
`Agent` tool with `subagent_type=<name>` when the task fits — each
sub-agent has a focused system prompt, its own context window, and a
tier-appropriate model so the cost stays in line with the work.

| Sub-agent | Model | Use when… |
|---|---|---|
| `ingester` | sonnet | Ingesting one paper / chapter / note. Forces all 16 ingest steps including entity creation and concept extension. |
| `source-extender` | sonnet | Deepening an already-ingested source page that came out shallow (gaps in Background, missing outcomes, summary instead of enumerated recommendations). |
| `concept-builder` | sonnet | Extending one concept page from N sources to 1500–3500 word chapter depth. |
| `extractor` | haiku | Filling one cell of a SR data-extraction table. Type/scale validated. Grunt work — Haiku is sufficient. |
| `query-synthesizer` | sonnet | Answering a focused research question with cited evidence (`/wiki-query`). |
| `reviewer` | sonnet | Generating a `/wiki-review`-style structured literature review on a topic. Markdown with APA bibliography. |

For batch ingestion, use `/wiki-batch-ingest <DIR> [batch-size]` —
loops over `*.md` files in `DIR`, delegates each to the `ingester`
sub-agent, confirms with the user between batches.

The parent agent stays orchestrator; sub-agents do the focused work.

---

## Directory Layout

```
raw/                  # Immutable source documents — never modify these
  papers/             # Journal articles (kebab-case.md, one per article)
  theses/             # PhD/MSc theses (kebab-case.md)
  notes/              # Personal notes, conference talks, lab reports
wiki/                 # Claude owns this layer entirely
  index.md            # Catalog of all pages — updated on every ingest
  log.md              # Append-only chronological record
  overview.md         # Living synthesis across all sources
  sources/            # One summary page per ingested source
  entities/           # People, labs, institutions, instrument vendors
  concepts/           # Theoretical concepts (e.g. MotorImagery, Neuroplasticity)
  methods/            # Measurement instruments (EEG, FuglMeyer, MEP, KVIQ, DTI…)
  interventions/      # Treatment monographs (MI-BCI, rTMS, mirror therapy…)
  recommendations/    # Synthesized clinical/research recommendations by topic
  questions/          # Open research questions identified across the literature
  syntheses/          # Saved query answers and literature reviews
graph/                # Auto-generated graph data
tools/                # Standalone Python scripts (health.py, lint.py, etc.)
pdf2md/               # PDF -> Markdown conversion pipeline (marker + fallback + enrich)
```

---

## Citation Rule (Global)

**Every factual claim, finding, recommendation, or quantitative
statement in any wiki page MUST cite at least one
`[[source-slug]] (p. N)`.** APA 7 by default. Numerical results are
quoted verbatim, never paraphrased. Bibliographic frontmatter fields
(`title`, `authors`, `journal`, `year`, `doi`) are copied verbatim from
the source — never invented.

The full spec — including the **Indirect Citation Rule** (literature vs
results), the **`reported via [[X]]` provenance pattern**, and rules
for **knowledge construction from introductions** — lives at
`docs/rules/citation.md`. Read it before any ingest.

---

## Depth & Completeness Rules

A source page is the agent's **only chance** to mine that paper for the
wiki. Extraction must be **exhaustive, not representative** — the
default failure mode is condensing 8 results into 2 bullets, or
summarizing a guideline's recommendation table instead of enumerating
each row.

The full spec — IMRAD-specific completeness expectations per
subsection, the special case for guidelines / meta-analyses /
consensus statements (e.g. Lefaucheur), anti-patterns, length
expectations per paper type, and the **mandatory self-critique gate**
applied at end of ingest — lives at
`docs/rules/depth-completeness.md`. Read it before any ingest, and
re-read its self-critique gate before declaring the ingest complete.

---

## Page Format (Canonical Frontmatter)

Every wiki page starts with this frontmatter:

```yaml
---
title: "Page Title"
type: source | entity | concept | method | intervention | recommendation | question | synthesis
tags: []
sources: []          # list of source slugs that inform this page
last_updated: YYYY-MM-DD
---
```

Use `[[PageName]]` wikilinks to link to other wiki pages. Sub-typed pages
(source, method, etc.) extend this base with type-specific fields, defined
below.

---

## Conversion Workflow

Triggered by: *"convert pdfs from <path>"*, *"run the conversion pipeline"*,
or `/wiki-convert <SRC> [DST]`.

This workflow turns a directory of PDFs into ingestion-ready Markdown
sources. It is **separate from ingestion** — it produces the input that
the Ingest Workflow consumes.

### Phases

1. **Marker conversion** (`pdf2md/pdf2md_marker.py SRC DST`) — high-fidelity
   PDF → Markdown, mirrored arborescence, idempotent. Writes `marker_report.json`.

2. **Mistral OCR (opt-in)** (`pdf2md/pdf2md_mistral.py SRC DST`) —
   retries marker `errors`/`suspicious` via Mistral Document AI.
   Better on tables, equations, scans. Needs `MISTRAL_API_KEY` (free
   experimental at `console.mistral.ai`; script prompts if missing).
   Writes `mistral_report.json`. Skip if no key.

3. **Fallback** (`pdf2md/pdf2md_fallback.py SRC DST`) — last resort,
   pymupdf4llm. Writes `fallback_report.json`.

4. **Enrich frontmatter** (`pdf2md/enrich_frontmatter.py DST`) — Crossref
   lookup populates `title`, `authors`, `journal`, `year`, `doi`. Same pass
   extracts a raw `cites:` list from the References section by regex.
   Writes `enrich_report.json`.

5. **Validate + curate citations** (`tools/parse_references.py --curate --all DST`) —
   each extracted DOI is checked against Crossref; broken or missing DOIs
   are recovered via free-text bibliographic search when score and title
   overlap thresholds pass. Writes the validation cache to
   `tools/.cache/doi_validation.json` (gitignored).

### Agent procedure

1. Confirm SRC exists and contains PDFs; default DST to `raw/papers/`.
2. Run Phase 1 (marker), surface `marker_report.json`.
3. Phase 2 (Mistral) is **opt-in** — if marker left errors/suspicious,
   ask: *"N entries unprocessed. Run Mistral OCR (free experimental
   plan, prompts for MISTRAL_API_KEY)? Otherwise go to Phase 3."*.
4. Run Phase 3 (pymupdf4llm), Phase 4 (enrich) — surface each report.
5. Phase 5 is network-heavy (5-13 min); **ask before launching** Crossref
   curation. Otherwise stop and tell the user to run it later.
6. Print recap (converted / metadata / cites: / total) and suggest
   ingestion via `/wiki-ingest`.

If any phase errors, stop and show the error before going further. The
pipeline is idempotent — the user can re-run the same command and only
the unfinished work will be redone.

---

## Long Document Ingestion (Theses ≥ 100 pages)

For long theses, ingesting in one pass produces shallow source pages.
Workflow: **split with `pdf2md/split_thesis.py`**, then ingest the
parent (lightweight thesis-level synthesis) and each chapter
separately (Academic Paper template, with `parent_thesis: <slug>`).

Full workflow at `docs/workflows/long-document-ingestion.md` (Step 0
split, Step 1 parent, Step 2 chapters, Step 3 aggregate, when NOT to
split).

---

## Ingest Workflow

Triggered by: *"ingest <file>"* or `/wiki-ingest`.

**Supported formats** — Markdown (`.md`) ingested directly. Non-markdown files
auto-converted to Markdown beforehand:
- **PDFs (papers, theses)** -> use `pdf2md/pdf2md_marker.py` (marker-pdf,
  with `pdf2md/pdf2md_fallback.py` for PDFs marker can't handle), then
  `pdf2md/enrich_frontmatter.py` to populate bibliographic metadata via
  Crossref.
- **Other formats** (`.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`, ...) -> markitdown.

Steps (in order):

1. **Read the source** fully via the Read tool (auto-convert if non-markdown).
2. **Read context**: `wiki/index.md`, `wiki/overview.md`, plus any obviously
   related concept/method pages already in the wiki.
3. **Choose the source template** based on the paper's *study design*
   (visible in title / abstract / methods cues), then **read the template
   file** before writing:

   | Detected type | Template |
   |---|---|
   | Empirical: RCT, cohort, cross-sectional, case-control, case-series | `docs/templates/source-academic-paper.md` |
   | Systematic review (with or without meta-analysis), PRISMA-aware | `docs/templates/source-systematic-review.md` |
   | Narrative review (no systematic search, thematic structure) | `docs/templates/source-narrative-review.md` |
   | Scoping review, PRISMA-ScR, evidence mapping | `docs/templates/source-scoping-review.md` |
   | Methodological paper (introduces new method / protocol / pipeline) | `docs/templates/source-methodological-paper.md` |
   | Theoretical / conceptual / framework paper (no data) | `docs/templates/source-theoretical-paper.md` |
   | Thesis (PhD / MSc / HDR) | `docs/templates/source-thesis.md` |
   | Lab notes / personal notes (`raw/notes/*`) | reuse `source-academic-paper.md`, omit fields that don't apply; or use Diary / Meeting if applicable |

   **Detection cues** when the type isn't explicit:
   - Has **PRISMA flow diagram** + risk-of-bias table → systematic review.
   - Has **PRISMA-ScR flow** + concept map / typology / no quality
     appraisal → scoping review.
   - **No Methods section**, thematic sub-headings, "we discuss" framing
     → narrative review.
   - **No Methods section**, postulates / definitions / model architecture
     → theoretical paper.
   - **Validation against a reference method**, software/algorithm
     description → methodological paper.

   Set the `study_design:` frontmatter field accordingly so that
   downstream tools (`tools/method_matrix.py`, `cohort_tracker.py`, etc.)
   can filter on type.

   Always also read `docs/rules/depth-completeness.md` (depth
   expectations, self-critique gate) and `docs/rules/citation.md`
   (Indirect Citation Rule, `reported via [[X]]` provenance, knowledge
   construction from introductions).
4. **Generate `citation_apa` and `bibtex_key`** from the frontmatter
   (`authors`, `year`, `title`, `journal` or `university`, `doi`). Use APA 7.
5. **Write the source page** to its **thematic destination** using the
   chosen template. Apply the routing rule from `## Source Organization`:
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

   Set `intervention_family` (principal therapy) and
   `intervention_subfamily` (paradigm, e.g. `mi-bci`, `rtms`, `itbs`)
   in the frontmatter so `tools/organize_sources.py` can later promote
   well-populated subfamilies to tier-2 folders.
6. **Parse references** (`tools/parse_references.py`): extract DOIs from the
   source's `## References` / `## Bibliography` section, populate
   `cites:` in the frontmatter, fill the `## Cites` section with wikilinks
   for in-wiki papers and raw DOIs for snowball candidates.

   The script has three phases (each opt-in):
   - default — regex extraction (offline, fast).
   - `--validate` — checks each extracted DOI against Crossref; invalid
     DOIs (often from line-break breakage by marker) are dropped.
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
7. **Update entity pages — MANDATORY**. Every paper has at least one
   author. Create or update `wiki/entities/<FirstAuthor>.md` and the
   page for the corresponding institution when identifiable. **A wiki
   with zero entities after multiple ingests means this step is being
   silently skipped — do not let that happen.**
8. **Update concept pages** — for each key concept discussed, **read
   the existing page and ADD to it** (sub-claim under
   `## Empirical Evidence`, variant under `## Definitions`, framework
   under `## Theoretical Foundations`, etc.). Verifying the page
   exists is NOT enough; it must be extended with this source's
   contribution.
9. **Update method pages** — for each method in the source's `methods:`
   frontmatter, the `## Used In This Wiki` entry MUST include a
   2-sentence description of HOW THIS PAPER USED IT (parameters,
   sample, deviations from standard) — not a bare wikilink.
   **Reminder**: methods are *measurement instruments* (EEG, FuglMeyer,
   MEP, KVIQ). Treatments belong on intervention pages — see 9b.
9b. **Update intervention pages**: if the source describes a therapeutic
    intervention (BCI, TMS, mirror therapy, robot training, etc.), ensure
    `wiki/interventions/<intervention-slug>.md` exists. Tag the source's
    frontmatter with `intervention_family: "BCI"` (or similar) so the
    intervention page can aggregate. When ≥ 2 sources share an
    `intervention_family`, the intervention page should reach full depth
    (Definition → Identified Studies → Pooled Outcomes → Best Practices).
10. **Update recommendation pages**: if the source proposes recommendations,
    route them to the relevant `wiki/recommendations/<topic>.md` (create
    if needed) under the appropriate evidence-strength section.
    **For guidelines, meta-analyses, or consensus statements**, this step
    is critical: enumerate **every** recommendation from the paper's
    recommendation tables (don't summarize), preserve evidence levels
    (A / B / C) verbatim, and create one `recommendations/<topic>.md`
    page per condition / protocol family. See **Depth & Completeness
    Rules → Guidelines, meta-analyses, consensus statements**.
11. **Update question pages**: if the source identifies an open question
    or explicit gap, append to `wiki/questions/<slug>.md` (create if needed).
12. **Flag contradictions** with existing wiki content explicitly, with
    page numbers on both sides.
13. **Update `wiki/index.md`** — add entries under all touched sections.
14. **Update `wiki/overview.md`** if the synthesis warrants revision.
15. **Append to `wiki/log.md`**: `## [YYYY-MM-DD] ingest | <Title>`.
16. **Post-ingest validation + Self-critique gate** — first run the
    **Self-critique gate** defined in `Depth & Completeness Rules`
    (re-read source page, verify exhaustive extraction; for guidelines
    verify every recommendation enumerated). Expand any incomplete
    section by re-reading the source. Then check broken `[[wikilinks]]`,
    verify all new pages are in `index.md`, run `tools/update_cited_by.py`
    to refresh `## Cited By` sections wiki-wide, and print a change
    summary including counts: *N concepts updated, M methods touched,
    K recommendations refined, J snowball candidates surfaced*.

### For theses specifically — citation snowball

Theses are dense citation hubs. After ingesting a thesis:

- **Surface high-value references** in the `## Notable References` section
  of the source page (10-30 references the thesis builds on heavily).
- **Suggest snowball ingestion**: at the end of the post-ingest summary,
  list the references *not yet in the wiki* and ask the user whether to
  ingest them next. Do not auto-ingest.

---

## Source Templates

Two templates are extracted to keep this file lean:

- **Academic Paper** (default for `raw/papers/*` and for thesis chapter sub-sources) → `docs/templates/source-academic-paper.md`. Full IMRAD body, frontmatter, Reporting Standard Alignment, Extraction Checklist.
- **Thesis** (default for `raw/theses/*`) → `docs/templates/source-thesis.md`. Parent-thesis page format used jointly with the Long Document Ingestion workflow.

Generic source pages (notes, lab reports) reuse the Academic Paper shape, omitting fields that don't apply. Diary / Meeting templates for non-academic content are listed at the end of this file.

---
## Concept Page Format

Concept pages are the **synthesis layer** — short academic chapters (1,500–3,500 words target), built incrementally as new sources touch them. Stub-vs-chapter rule: pages may start as stubs but expand toward chapter depth once 3+ sources have touched them.

Full spec at `docs/templates/concept.md`.

---
## Method Page Format

Measurement instruments / scales / techniques (EEG, KVIQ, MEP, FuglMeyer, DTI…). One page per method, in `wiki/methods/<MethodName>.md`. Each entry under `## Used In This Wiki` MUST describe how the source paper used the method (parameters, deviations) — not a bare wikilink.

Full spec at `docs/templates/method.md`.

---
## Intervention Page Format

Therapeutic interventions delivered to participants (BCI, TMS, mirror, robot, mental practice…). Distinct from `methods/`. Page created when ≥ 2 sources share an `intervention_family`. Documents Mechanism of Action, Variants, Protocol Parameters synthesized across studies, Identified Studies table, Pooled Outcomes, Best Practices, Patient Selection.

Full spec at `docs/templates/intervention.md`.

---
## Recommendation Page Format

One page per topic, grouped by **strength of evidence** (Strong / Moderate / Conflicting). For guideline papers, every recommendation in the original table is enumerated and routed here per `docs/rules/depth-completeness.md`.

Full spec at `docs/templates/recommendation.md`.

---
## Question Page Format

Open research questions identified across the literature. One page per question, in `wiki/questions/<slug>.md`. Sections: The Gap / Why It Matters / What's Known / What's Missing / Suggested Studies / Connections.

Full spec at `docs/templates/question.md`.

---
## Entity Page Format

People, labs, institutions, instrument vendors. One page per entity, in `wiki/entities/<EntityName>.md`. The Citation Rule applies — every biographical or affiliative claim cites a source with page number.

Full spec at `docs/templates/entity.md`.

---
## Query Workflow

Triggered by: *"query: <question>"* or `/wiki-query`.

Steps:
1. Read `wiki/index.md` to identify candidate pages.
2. Read those pages with the Read tool.
3. Synthesize an answer with **inline citations as `[[source-slug]] (p. N)`** —
   the Citation Rule applies to query answers too.
4. End the answer with an APA bibliography (one entry per cited source,
   pulled from each source page's `citation_apa` field).
5. Ask the user whether to file the answer as `wiki/syntheses/<slug>.md`.

---

## Review Workflow

Triggered by: *"review topic: <topic>"* or `/wiki-review`.

This is the wiki's headline output: a structured literature review on a
topic, citation-ready.

Steps:
1. Read `wiki/index.md` and identify all sources tagged with the topic
   (search `tags`, `domain`, and `[[wikilinks]]`).
2. Read those source pages, plus relevant `concepts/`, `methods/`,
   `recommendations/`, and `questions/` pages.
3. Produce a structured review with this layout:

   ```markdown
   # <Topic> — Literature Review (YYYY-MM-DD)

   ## Background and key concepts
   Narrative grounded in [[concepts/...]] pages, every claim cited.

   ## Methods used in the literature
   Table: method | sources | strengths | limitations.

   ## Main findings
   Grouped by sub-theme. Every factual claim cites a source page.

   ## Recommendations
   Pulled verbatim from [[recommendations/...]] pages.

   ## Open questions
   Pulled from [[questions/...]] pages.

   ## Bibliography (APA)
   Generated from the `citation_apa` field of each cited source.
   ```

4. Apply the Citation Rule — *no claim without a source*.
5. Ask the user whether to file as `wiki/syntheses/<topic>-review.md`.

---

## Cite Workflow

Triggered by: *"cite: <topic>"* or `/wiki-cite`.

Returns 3-5 APA-formatted citations from the wiki most relevant to the
topic, with one-sentence relevance rationale per citation. No body, just
references — useful when drafting a paragraph and needing cite-ready refs.

---

## Suggest-Readings Workflow

Triggered by: *"suggest readings for: <concept>"* or `/wiki-suggest-readings`.

Surfaces complementary readings to deepen a concept. Two modes:

**Internal mode** (default — runs `tools/suggest_readings.py <concept>`):
- Walks `wiki/sources/`, collects every source tagged with the concept.
- Aggregates each source's `cites:` frontmatter (DOIs cited).
- Surfaces DOIs cited by **2+ wiki sources** but not yet present in any
  `wiki/sources/*.md` `doi:` field.
- Sorted by citation frequency. Each candidate shows: count, DOI, the
  wiki sources that cite it.

**Forward mode** (`--forward`, OpenAlex):
- For each wiki source with a DOI, lists top-50 papers citing it.
- Aggregates co-citations across the wiki, ranks candidates by:
  `score = co_citation × 100 + velocity + log10(venue_h)`
- Filter: `co_citation ≥ 2 OR (velocity ≥ 2.5 AND venue_h ≥ 30)`.
  Velocity = `cited_by_count / max(1, age_years)` normalises the bias
  for recent papers. Cached in `tools/.cache/openalex_forward.json`.

Output: a Markdown list of candidates with their bibliographic
metadata. The user picks which to ingest.

To **auto-fetch the open-access PDFs** of selected candidates, pipe to
`tools/fetch_oa.py` (uses Unpaywall):

```bash
python tools/suggest_readings.py --forward --top 30 \
  | python tools/fetch_oa.py --from-stdin
```

`fetch_oa.py` queries Unpaywall for each DOI, downloads the OA PDF
when available to `raw/papers/<author-year>.pdf`, skips paywalled /
non-OA / already-downloaded entries. Status per DOI in
`raw/papers/fetch_oa_report.json`. Set `UNPAYWALL_EMAIL=you@example.org`
once (Unpaywall ToS).

---

## Data Extraction (systematic review tables)

`tools/extract_data.py` populates a SR data-extraction table
(Excel `.xlsx` or CSV) from `wiki/sources/`. Three filling layers
applied per cell, in order:

1. **Frontmatter** (always on) — known column headers map to YAML
   fields (title, authors, year, doi, study_design, …).
2. **Body regex** (always on) — built-in patterns for clinical fields
   (n per arm, age mean, baseline FM, ΔFM, p-value, Cohen's d, CI,
   trial-registration ID, …).
3. **LLM** (`--llm`) — for cells still empty AND with a per-column
   rule provided in an `INSTRUCTIONS` row (see below), calls Claude
   via litellm. Cached in `tools/.cache/extract_llm.json`.

Cells already populated by the user are never overwritten.

### Spec rows (INSTRUCTIONS / TYPE / SCALE)

Three rows above the data describe each column. The slug cell of each
spec row contains the marker (`INSTRUCTIONS`, `TYPE`, `SCALE`):

```
slug          | year         | risk_of_bias                     | design
INSTRUCTIONS  | Pub year     | Cochrane RoB 2 overall           | Study design
TYPE          | quantitative | ordinal                          | nominal
SCALE         | (YYYY)       | 0=low, 1=some concerns, 2=high   | RCT, cohort, cross-sectional
cervera-2020  |              |                                  |
```

- **INSTRUCTIONS** — natural-language extraction rule per column.
- **TYPE** — `quantitative` | `ordinal` | `nominal` | `text`.
- **SCALE** — quantitative: unit hint `(years)`; ordinal/nominal coded
  `0=low, 1=high` (LLM returns the code); enum `RCT, cohort` (LLM
  returns one verbatim); text: leave empty.

The tool validates extracted values against TYPE/SCALE; mismatches are
flagged in stderr and counted as `invalid` in the run summary.

`--from-source` inserts the three rows pre-filled with sensible defaults
for the SR column set; edit them in Excel before running `--llm`.
Skip with `--no-spec`.

### Modes

```bash
# Pre-fill a NEW template from a SR's cites: (writes an INSTRUCTIONS row by default)
python tools/extract_data.py --from-source cervera-2020 -o cervera-ext.xlsx

# Fill an existing template (frontmatter + regex)
python tools/extract_data.py cervera-ext.xlsx

# Same + LLM fallback for unfilled cells (default Haiku, ANTHROPIC_API_KEY)
python tools/extract_data.py cervera-ext.xlsx --llm

# Force Sonnet for trickier extraction:
LLM_MODEL=claude-sonnet-4-6 python tools/extract_data.py cervera-ext.xlsx --llm
```

**Model tiers**: `LLM_MODEL_FAST` (Haiku) vs `LLM_MODEL` (Sonnet).

Default SR column set and recognized header aliases live at the top of
`tools/extract_data.py` (`DEFAULT_SR_COLUMNS`, `FM_MAP`, `BODY_PATTERNS`).
Extend the ontology there for domain-specific fields.

The agent should run this tool on user request, summarize the per-cell
method counts (frontmatter / regex / llm / manual / empty) and the
per-row status (complete / partial / empty / not_found), and surface
which columns remained empty so the user knows what to fill manually.

---

## Concept Consolidation (batched)

`tools/consolidate_concepts.py` batches concept-page extension (one LLM
call per concept, prompt-cached, integrates all pending sources). ~70 %
cheaper than per-ingest on homogeneous corpora.

```bash
python tools/consolidate_concepts.py --report   # pending counts
python tools/consolidate_concepts.py <Concept>  # one
python tools/consolidate_concepts.py --since 7d
```

When run periodically, ingest step 8 may defer extension.

---

## Replication Tracking

Each Academic Paper template includes a `replication_of: "<DOI>"` frontmatter
field. When a paper explicitly attempts to replicate a prior study, the
agent fills it in at ingest. `tools/replication_tracker.py` walks
`wiki/sources/`, follows the `replication_of:` chains, and outputs a
report grouped into:

- **Replication chains** — original → replication(s) with consistent
  vs inconsistent findings flagged.
- **Single-study claims** — concept pages whose `## Empirical Evidence`
  rests on one source (a flag for confidence).
- **Replication candidates** — papers in the wiki that could plausibly
  replicate an existing finding but don't claim it explicitly.

Run this periodically; it complements `/wiki-lint`.

---

## Audit Trail (git as history)

Because the wiki is a git repo, `git log` and `git blame` already provide
a free audit trail — every ingestion appends to `wiki/log.md` with
`## [YYYY-MM-DD] ingest | <Title>`, and each commit touches the wiki pages
the source affected.

`tools/audit_page.py <wiki-page>` (commit 3) wraps `git blame` to map
each line of the page to the ingest commit that introduced it, surfacing
which source contributed which paragraph. Useful for:
- Defending a claim during a thesis review.
- Identifying when a concept's definition shifted.
- Untangling synthesis lines that reference multiple sources.

---

## Lint Workflow

Triggered by: *"lint the wiki"* or `/wiki-lint`.

Use Grep and Read tools to check for:

**Structural / wiki-wide**
- **Orphan pages** — wiki pages with no inbound `[[links]]`.
- **Broken links** — `[[wikilinks]]` pointing to pages that don't exist.
- **Missing entity pages** — entities mentioned in 3+ pages but lacking
  their own page.
- **Stale summaries** — pages older than the most recent source they cite.

**Academic-specific**
- **Missing DOI** — sources without `doi` (excluding theses, where DOI
  may legitimately be empty if not archived).
- **Missing `citation_apa`** — sources where this field is empty.
- **Uncited claims** — bullets in `## Key Findings`, `## Recommendations`,
  `## Summary` that don't contain `(p. ` — likely uncited.
- **Missing `study_design`** in source frontmatter.
- **Conflicting concept definitions** — same concept defined incompatibly
  across pages (use LLM semantic check).
- **Snowball debt** — references in any thesis's `## Notable References`
  marked ☐ for >30 days.
- **Data gaps** — surface as candidate `[[questions/...]]` pages.

Output a lint report and ask whether to save to `wiki/lint-report.md`.

---

## Health Workflow

Triggered by: *"health"* or `/wiki-health`.

Run: `python tools/health.py` (or `python tools/health.py --json`).

Fast structural integrity checks — **zero LLM calls**, safe every session:
- **Empty / stub files** — pages with no content beyond frontmatter.
- **Index sync** — `wiki/index.md` entries vs actual files on disk.
- **Log coverage** — source pages missing a corresponding `ingest` entry
  in `wiki/log.md`.

Output a health report. Use `--save` to write to `wiki/health-report.md`.

### Health vs Lint Boundary

| Dimension | `health` | `lint` |
|---|---|---|
| **Scope** | Structural integrity | Content quality (incl. citation hygiene) |
| **LLM calls** | Zero | Yes |
| **Cost** | Free | Tokens |
| **Frequency** | Every session | Every 10-15 ingests |
| **Tool** | `tools/health.py` | `tools/lint.py` |
| **Run order** | First | After health passes |

> Run `health` first — linting an empty file wastes tokens.

---

## Graph Workflow

Triggered by: *"build the knowledge graph"* or `/wiki-graph`.

Run `tools/build_graph.py`:
- Pass 1: parse all `[[wikilinks]]` -> deterministic `EXTRACTED` edges.
- Pass 2: infer implicit relationships -> `INFERRED` edges with confidence.
- Run Louvain community detection.
- Output `graph/graph.json` + `graph/graph.html`.

If Python/dependencies aren't set up, generate the graph data manually:
1. Use Grep to find all `[[wikilinks]]`.
2. Build a node/edge list, write `graph/graph.json`.
3. Write `graph/graph.html` from the vis.js template.

---

## Source Organization (thematic folders)

`wiki/sources/` is **not flat**. New sources are written directly into
thematic sub-folders so the corpus stays browsable in Obsidian. Theses
are kept apart from articles. The Indirect Citation Rule and `[[wikilinks]]`
work the same way regardless of folder depth (Obsidian resolves by
file basename).

### Layout

```
wiki/sources/
├── theses/<slug>/<slug>.md             # parent + chapter sub-sources
└── articles/
    ├── bci/        [<subfamily>/]      # mi-bci, ao-bci, hybrid…
    ├── tms/        [<subfamily>/]      # rtms, itbs, ctbs…
    ├── tdcs/
    ├── mirror-therapy/
    ├── robot-therapy/
    ├── mental-practice/
    ├── physio/
    ├── imaging/    [<modality>/]       # dti, fmri, eeg (observational)
    ├── reviews/    <form>/             # systematic, scoping, narrative
    ├── theory/                          # framework / conceptual papers
    ├── methodology/                     # new methods / pipelines
    └── general/                         # fallback
```

### Routing rule (first match wins)

Apply at ingest step 5 to choose the destination path:

1. `tags` contains `thesis` → `theses/<slug>/<slug>.md`
2. `tags` contains `thesis-chapter` → `theses/<parent_thesis>/<slug>.md`
3. `study_design ∈ {systematic-review, meta-analysis}` → `articles/reviews/systematic/<slug>.md`
4. `study_design == scoping-review` → `articles/reviews/scoping/<slug>.md`
5. `study_design == narrative-review` → `articles/reviews/narrative/<slug>.md`
6. `study_design == theoretical` → `articles/theory/<slug>.md`
7. `study_design == methodological` → `articles/methodology/<slug>.md`
8. `intervention_family` set (≠ `none`) → `articles/<family>/[<intervention_subfamily>/]<slug>.md`
9. `methods` contains DTI / fMRI / EEG with no intervention → `articles/imaging/<modality>/<slug>.md`
10. Otherwise → `articles/general/<slug>.md`

### Principal vs adjuvant

When a study combines multiple interventions (e.g. MI-BCI + concurrent
rTMS), the **dossier = principal intervention**, decided in this order:

1. Title / abstract framing — *"we tested X"* → X is principal.
2. Experimental vs control arm — what distinguishes them is principal.
3. If still ambiguous, first item in `interventions:` is principal.

The agent sets `intervention_family:` to the principal. Adjuvants
remain listed in `interventions:` (full list).

Examples:
- *"MI-BCI training with concurrent rTMS conditioning"* →
  `intervention_family: BCI`, `intervention_subfamily: hybrid` →
  `articles/bci/hybrid/`.
- *"cTBS over contralesional M1, with standard physiotherapy as
  control"* → `intervention_family: TMS`, `intervention_subfamily: ctbs`
  → `articles/tms/ctbs/`.

### Tier-2 subfolders (`mi-bci/`, `rtms/`, …)

Created **only when ≥ 3 papers share the same subfamily** to avoid a
forest of nearly-empty folders. The agent fills `intervention_subfamily:`
at ingest, but writes to the tier-1 folder by default.

`tools/organize_sources.py --promote --threshold 3` periodically scans
the corpus, counts subfamily groups, and `git mv`s papers into tier-2
subfolders for groups that pass the threshold.

### Reorganization workflow

```bash
# Preview first (no file moved)
python tools/organize_sources.py --dry-run

# Apply tier-1 routing only
python tools/organize_sources.py

# Apply tier-1 + promote established subfamilies to tier-2
python tools/organize_sources.py --promote --threshold 3
```

The tool uses `git mv` so file history is preserved.

---

## Naming Conventions

- **Source slugs (papers)**: `kebab-case`
  (e.g. `cervera-2020-mi-bci-meta-analysis.md`).
- **Thesis slugs**: `lastname-year-shorttitle`
  (e.g. `dupont-2023-mi-bci-stroke.md`).
- **Entity pages**: `TitleCase.md`
  (e.g. `MaryamMaarek.md`, `INSERM-U1216.md`).
- **Concept pages**: `TitleCase.md`
  (e.g. `MotorImagery.md`, `Neuroplasticity.md`, `CorticospinalTract.md`).
- **Method pages**: `TitleCase.md`
  (e.g. `EEG.md`, `DTI.md`, `FuglMeyer.md`, `MEP.md`, `KVIQ.md`).
- **Intervention pages**: `kebab-case.md` matching the family or variant
  (e.g. `mi-bci.md`, `rtms.md`, `itbs.md`, `mirror-therapy.md`).
- **Recommendation pages**: `kebab-case.md`
  (e.g. `mi-bci-stroke-rehab.md`).
- **Question pages**: `kebab-case.md`
  (e.g. `tms-dose-response-chronic-stroke.md`).
- **Synthesis pages**: `kebab-case.md` (often `<topic>-review.md`).

### Domain quick reference (stroke / MI-BCI / TMS / DTI)

Likely entries you'll create — keep names consistent:

- **Concepts**: `MotorImagery`, `MotorRecovery`, `Neuroplasticity`,
  `CorticospinalTract`, `M1`, `PremotorCortex`, `SMA`, `NeuralControlTheory`,
  `WhiteMatterIntegrity`, `Hemiparesis`, `StrokeChronicity`.
- **Methods**: `EEG`, `MI-BCI`, `TMS`, `rTMS`, `DTI`, `Tractography`, `MEP`,
  `FuglMeyer`, `ARAT`, `BoxAndBlocks`, `KVIQ`, `MIQ-RS`, `MentalChronometry`,
  `FA-MetricExtraction`.
- **Recommendation topics**: `mi-bci-stroke-rehab`,
  `tms-protocols-motor-recovery`, `dti-biomarkers-prognosis`.

---

## Index Format

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources — Papers
- [Paper Title](sources/<slug>.md) — one-line summary (Year, Journal)

## Sources — Theses
- [Thesis Title](sources/<slug>.md) — one-line summary (Year, University)

## Concepts
- [Concept Name](concepts/<Name>.md) — one-line definition

## Methods
- [Method Name](methods/<Name>.md) — what it measures

## Interventions
- [Intervention Name](interventions/<slug>.md) — therapy family, target outcome

## Recommendations
- [Topic](recommendations/<topic>.md) — one-line scope

## Questions
- [Question](questions/<slug>.md) — status

## Entities
- [Entity Name](entities/<Name>.md) — one-line description

## Syntheses
- [Title](syntheses/<slug>.md) — what question it answers
```

## Overview Page Format

`wiki/overview.md` is a living synthesis across all sources. Refreshed when synthesis warrants revision. Citation Rule applies under `## Key Findings (synthesized)`.

Full spec at `docs/templates/overview.md`.

---
## Log Format

Each entry starts with `## [YYYY-MM-DD] <operation> | <title>` so it's
grep-parseable:

```
grep "^## \[" wiki/log.md | tail -10
```

Operations: `ingest`, `query`, `review`, `cite`, `health`, `lint`, `graph`.

---

## Domain-Specific Templates (non-academic)

Kept available for diary entries or meeting notes mixed into `raw/notes/`.

### Diary / Journal Template

```markdown
---
title: "YYYY-MM-DD Diary"
type: source
tags: [diary]
date: YYYY-MM-DD
---
## Event Summary
## Key Decisions
## Energy & Mood
## Connections
## Shifts & Contradictions
```

### Meeting Notes Template

```markdown
---
title: "Meeting Title"
type: source
tags: [meeting]
date: YYYY-MM-DD
---
## Goal
## Key Discussions
## Decisions Made
## Action Items
```
