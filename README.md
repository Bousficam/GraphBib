# LLM Wiki Agent — Academic Edition

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A coding agent skill, specialized for academic research.** Drop a PDF library into `raw/` and tell the agent to ingest it — the wiki builds itself: source summaries with verbatim citations, concept pages structured as short academic chapters, methodology pages, recommendations grouped by evidence strength, open research questions, and a citation network that connects every paper to what it cites and what cites it.

This is a fork of [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) specialized for academic research workflows. The upstream supplies the core "agent maintains a wiki from source documents" pattern; this fork adds the IMRAD source templates, the Indirect Citation Rule, the PDF→Markdown pipeline (Marker + pymupdf4llm + Crossref), and the systematic-review tooling. Spiritually inspired by Andrej Karpathy's vision of LLMs as a new computing layer ("[Software 3.0](https://www.youtube.com/watch?v=LCEmiRjPEtQ)") — the agent doesn't just retrieve, it reads, structures, and writes back into a persistent knowledge graph.

> Most knowledge tools make you search your own notes. This one reads everything you've collected and writes a structured wiki that compounds over time — cross-references already built, contradictions already flagged, synthesis already done. **In this fork, every factual claim cites a source page with a page number, every paper's bibliography is parsed and validated against Crossref, and snowball candidates are surfaced automatically.**

This fork is configured for research on **stroke motor rehabilitation via MI-BCI and TMS**, anchored in neural control theory and white-matter anatomy (DTI). The schema adapts to other academic domains by editing `CLAUDE.md`.

```
ingest raw/papers/cervera-2020.md
```

```
raw/                  # Immutable source documents — never modified
├── papers/           # Journal articles
├── theses/           # PhD/MSc theses (with citation snowball)
└── notes/            # Lab reports, conference talks, personal notes
wiki/                 # Owned entirely by the agent
├── index.md          # Catalog of all pages — updated on every ingest
├── log.md            # Append-only chronological record
├── overview.md       # Living synthesis across all sources
├── sources/          # One academic summary per ingested source
├── entities/         # Authors, labs, institutions
├── concepts/         # Theoretical concepts, structured as book chapters
├── methods/          # Methodologies & instruments (EEG, TMS, DTI, FuglMeyer…)
├── recommendations/  # Clinical/research recommendations grouped by evidence
├── questions/        # Open research questions identified across the corpus
└── syntheses/        # Saved query answers and literature reviews
graph/
├── graph.json        # Persistent node/edge data (SHA256-cached)
└── graph.html        # Interactive vis.js visualization
pdf2md/               # PDF → Markdown conversion pipeline
tools/                # Standalone scripts (health, lint, citations…)
```

## Install

**Requires:** [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), or any agent that reads a config file.

```bash
git clone https://github.com/SamurAIGPT/llm-wiki-agent.git
cd llm-wiki-agent
```

Open in your agent — no API key or Python setup needed:

```bash
claude      # reads CLAUDE.md + .claude/commands/ (slash commands available)
codex       # reads AGENTS.md
opencode    # reads AGENTS.md
gemini      # reads GEMINI.md
```

## Usage

The agent understands natural language and shorthand triggers:

```
ingest raw/papers/cervera-2020.md          # ingest a markdown source
ingest raw/papers/                         # batch ingest a directory
review topic: MI-BCI in chronic stroke     # generate a literature review
query: what does the wiki say about
       corticospinal integrity?            # synthesize an answer with citations
suggest readings for: MotorImagery         # surface snowball candidates
cite: TMS-induced plasticity in M1         # 3-5 APA refs from the wiki
lint                                       # citation hygiene, orphans, gaps
build graph                                # build graph.html
```

Plain English works too:

```
"Ingest the Lefaucheur 2014 guidelines and route every recommendation
 to the right wiki/recommendations/<topic>.md page."

"Build a literature review on cTBS over contralesional M1 in subacute
 stroke. Save as a synthesis page."

"Extract data for the Cervera 2020 meta-analysis using the LLM mode."
```

**Claude Code** ships 12 slash commands wrapping the agent ecosystem:

| Discovery | Conversion | Ingestion | Output | Maintenance |
|---|---|---|---|---|
| `/wiki-snowball` | `/wiki-convert` | `/wiki-init` | `/wiki-query` | `/wiki-status` |
| `/wiki-discover` | | `/wiki-batch-ingest` | `/wiki-review` | `/wiki-maintain` |
| | | `/wiki-deepen` | `/wiki-extract-table` | `/wiki-remove` |

`/wiki-discover` chains *suggest → fetch → convert → ingest* end-to-end.
`/wiki-maintain` runs lint then delegates fixes to the librarian
sub-agent. Other agents (Codex, Gemini, etc.) use the natural language
triggers above, which work identically — every slash command has a
plain-English equivalent.

Markdown is the native ingestion format. For PDF-heavy academic
libraries, the next section describes the dedicated pipeline (Marker +
pymupdf4llm fallback + Crossref enrichment + curation).

### Specialist sub-agents

Eleven focused sub-agents live in `.claude/agents/`. Each has its own
context window and a tier-appropriate model — the parent agent stays
orchestrator while specialists do the focused work. Slash commands
above delegate automatically; you can also invoke them directly via
the `Agent` tool.

| Sub-agent | Model | Role |
|---|---|---|
| `suggest-reading` | sonnet | Find what to read next (snowball + OpenAlex forward) |
| `fetch-reading` | haiku | Download OA PDFs for a DOI list (Unpaywall) |
| `ingester` | sonnet | Ingest one source — forces all 16 ingest steps |
| `source-extender` | sonnet | Deepen an already-ingested shallow source |
| `concept-builder` | sonnet | Extend one concept page to chapter depth |
| `extractor` | haiku | Fill one cell of a SR data-extraction table |
| `query-synthesizer` | sonnet | Answer a focused research question |
| `reviewer` | sonnet | Generate a structured literature review |
| `lint` | sonnet | Audit (deterministic + cached semantic) |
| `librarian` | sonnet | Act on lint findings — auto-fix / delegate / confirm |
| `source-remover` | sonnet | Cleanly remove a source and every cross-reference |

## Academic Pipeline

End-to-end flow for converting a PDF library into a citation-rigorous wiki.
Each step is idempotent and can be re-run safely.

```
PDF library
   │
   ▼  pdf2md/pdf2md_marker.py     ← high-fidelity Marker conversion (free, primary)
   │  pdf2md/pdf2md_mistral.py    ← Document AI / OCR for hard PDFs (opt-in, paid)
   │  pdf2md/pdf2md_fallback.py   ← pymupdf4llm rescue (free, last resort)
   │
   ▼  Markdown files (raw/papers/)
   │
   ▼  pdf2md/enrich_frontmatter.py  ← Crossref → title, authors, journal, year, DOI
   │                                  Regex → cites: [DOIs]
   │
   ▼  tools/parse_references.py --curate
   │     ↳ Phase 1 — extract DOIs from References (regex)
   │     ↳ Phase 2 — validate each DOI against Crossref agency endpoint
   │     ↳ Phase 3 — recover broken/missing DOIs via Crossref free-text search
   │
   ▼  ingest in Claude Code
   │     ↳ Background / Methods / Results / Discussion / Cites sections
   │     ↳ Indirect Citation Rule (cite the original paper, not the transmitter)
   │     ↳ concept, method, recommendation, question pages auto-created/refined
   │     ↳ citation_apa + bibtex_key generated from frontmatter
   │
   ▼  tools/update_cited_by.py   ← Reverse citation index → ## Cited By sections
   │  tools/suggest_readings.py  ← Snowball candidates (DOIs cited 2+ times,
   │                               not yet in the wiki)
   │
   ▼  Living academic wiki
```

### Step 1 — PDF → Markdown

```bash
python pdf2md/pdf2md_marker.py "/path/to/PDFs" raw/papers
python pdf2md/pdf2md_fallback.py "/path/to/PDFs" raw/papers
```

`pdf2md_marker.py` walks the source directory recursively, runs each PDF
through [marker-pdf](https://github.com/VikParuchuri/marker), mirrors the
folder structure, and writes a frontmatter header (`source_pdf`, `title`,
`backend: marker`). Idempotent — already-converted files are skipped.
Output: `marker.log`, `marker_report.json` summarizing OK / suspicious /
errors.

`pdf2md_fallback.py` reads `marker_report.json` and reprocesses every PDF
that failed or produced a suspiciously short output, this time with
[pymupdf4llm](https://github.com/pymupdf/RAG) (CPU, no ML dependency).
Useful when Marker / Surya hits known MPS bugs on certain PDFs. The
backend used for each `.md` is recorded in its frontmatter.

#### Optional — Document AI tier for hard PDFs

For scanned papers, complex tables, equations, or two-column layouts
that defeat both Marker and pymupdf4llm, the pipeline supports a
middle tier backed by a hosted Document AI / OCR API. The reference
implementation uses **Mistral Document AI**:

```bash
export MISTRAL_API_KEY=...                  # console.mistral.ai
python pdf2md/pdf2md_mistral.py "/path/to/PDFs" raw/papers
```

Reads `marker_report.json` and only sends the entries Marker errored
on or flagged as suspicious — typically 10–20 % of a corpus. Paces
itself at ~2 req/s; the experimental plan is free with rate limits.
Output is mirrored to `raw/papers/` with `backend: mistral` in the
frontmatter so the source of each markdown is auditable.

The script is a thin adapter (PDF → API → markdown + frontmatter), so
**other Document AI providers plug into the same slot**: Google Cloud
Document AI, AWS Textract, Azure AI Document Intelligence, Adobe PDF
Extract, or Reducto. Copy `pdf2md_mistral.py`, swap the API call, keep
the same input/output contract (`marker_report.json` driver, mirrored
output path, `backend: <provider>` frontmatter), and the rest of the
pipeline is provider-agnostic.

### Step 2 — Enrich Bibliographic Metadata

```bash
python pdf2md/enrich_frontmatter.py raw/papers
```

For each `.md`, finds the DOI (regex over the body and the first PDF
page) and queries Crossref for canonical `title`, `authors`, `journal`,
`year`. Same pass also extracts a raw list of cited DOIs from the
References section into `cites: []`.

Outputs `enrich_report.json` with the breakdown: Crossref-resolved /
DOI-only / no-DOI / errors / how many sources got `cites:` populated.

### Step 3 — Validate and Curate Citations

```bash
python tools/parse_references.py --curate --all raw/papers
```

Three opt-in phases:
1. **Extract** — regex DOI extraction (offline, fast).
2. **Validate** — Crossref `/works/{doi}/agency` check; drops invalid
   DOIs (typically broken at line breaks during PDF extraction).
3. **Curate** — for entries with no valid DOI, free-text bibliographic
   search recovers the canonical DOI, accepted only when relevance
   score and title overlap pass thresholds.

Frontmatter:
```yaml
cites: [doi1, doi2, ...]              # all validated DOIs (regex + curated)
cites_curated: [doi3]                  # subset recovered via free-text (audit)
cites_unresolved:                      # entries no DOI could be assigned to
  - "Smith J, Brown K. ..."
```

Cache: `tools/.cache/doi_validation.json` — once a DOI is validated,
subsequent runs skip the network call. Estimated cost on a fresh
698-paper corpus: ~13 min; subsequent runs: ~5 min.

### Step 4 — Ingest into the Wiki

```bash
claude
```

Then in the agent:
```
ingest raw/papers/cervera-2020.md
ingest raw/papers/   # batch — process by length, ascending
```

Or in plain English:
```
"Ingest all PDFs under raw/papers/ in batches of 5, shortest first.
 Confirm after each batch."
```

Claude reads `CLAUDE.md` and applies the academic schema:
- **Source pages** with explicit `## Background (from cited literature)`,
  `## Methods`, `## Results (this paper's findings)`, `## Discussion` —
  each register cited correctly under the **Indirect Citation Rule**.
- **Concept pages** structured as short academic chapters (Overview,
  Historical Genesis, Definitions, Theoretical Foundations, Mechanisms,
  Operationalization, Empirical Evidence, Clinical Relevance, Debates,
  Seminal Papers, Related Concepts).
- **Method pages** documenting each instrument or technique (EEG, TMS,
  DTI, FuglMeyer, MI-BCI, KVIQ, Tractography…) with best practices and
  pitfalls aggregated across sources.
- **Recommendation pages** grouping clinical/research recommendations by
  evidence strength (Strong / Moderate / Conflicting).
- **Question pages** capturing the open research questions surfaced by
  each paper.
- **Entity pages** for authors and institutions.
- `citation_apa` and `bibtex_key` auto-generated; `## How to Cite`
  section in each source page is copy-paste ready.

For theses (`raw/theses/*`), Claude additionally extracts a
**citation snowball list** of high-value references the thesis builds on.

### Step 5 — Build and Maintain the Citation Network

```bash
python tools/update_cited_by.py
```

Walks `wiki/sources/`, builds the reverse-citation index from each
source's `cites:` frontmatter, and rewrites every source's `## Cited By`
section with `[[wikilinks]]` pointing to the papers that cite it. Run
after each batch of ingestions.

### Step 6 — Surface Complementary Readings

```bash
python tools/suggest_readings.py MotorImagery --enrich --top 20
```

For a given concept (or `--all` for wiki-wide), lists DOIs cited by
**2 or more wiki sources tagged with that concept** but not yet
ingested, with Crossref metadata (title, authors, journal, year). These
are your snowball candidates.

The agent-visible equivalent:
```
/wiki-suggest-readings MotorImagery
```

## Tooling Reference

The repo ships **16 standalone scripts**. They walk frontmatter and bodies,
write to `wiki/` or stdout, and require no LLM call (Crossref + regex only)
unless explicitly noted.

### Citation pipeline

| Script | Role |
|---|---|
| `pdf2md/pdf2md_marker.py` | PDF → Markdown via marker-pdf, mirrored arborescence |
| `pdf2md/pdf2md_mistral.py` | Optional Document AI / OCR tier (Mistral; swap for Google / AWS / Azure) |
| `pdf2md/pdf2md_fallback.py` | Rescue PDFs marker can't handle (pymupdf4llm) |
| `pdf2md/enrich_frontmatter.py` | Crossref → title / authors / journal / year + raw `cites:` |
| `tools/parse_references.py` | Validate + curate citations (3 phases: extract / validate / Crossref free-text) |
| `tools/update_cited_by.py` | Maintain `## Cited By` sections from `cites:` index |
| `tools/suggest_readings.py` | Surface snowball candidates per concept |

### Output / publication

| Script | Role |
|---|---|
| `tools/bibtex_export.py` | `wiki.bib` (master with section comments, `--per-concept`, `--per-intervention`, `--chapters` mapping) |
| `tools/coverage_report.py` | Where the wiki is thin: stub concepts, untagged sources, missing usage |

### Domain analyzers (zero LLM)

| Script | Role |
|---|---|
| `tools/method_matrix.py` | Sources × design × N × methods × intervention |
| `tools/cohort_tracker.py` | Aggregated patient profiles (chronicity, severity, lesion side/type) by intervention |
| `tools/dti_aggregator.py` | FA / MD / AD / RD per brain tract across sources |
| `tools/effect_size_aggregator.py` | ΔFM / ΔARAT / BBT / NHPT / MEP / Cohen's d / p-values |
| `tools/replication_tracker.py` | Declared chains + single-study claims + replication candidates |
| `tools/audit_page.py` | `git blame` mapped to `wiki/log.md` ingest entries |

### Discovery & domain

| Script | Role |
|---|---|
| `tools/watch_pubmed.py` | Periodic PubMed + bioRxiv check on saved queries (cached) |
| `tools/brain_atlas_anchor.py` | Mentions of brain regions / white-matter tracts across sources |

## Maintenance Workflow

Run after every batch of ingestions to keep the wiki citation-rigorous and
to surface where it's thin.

### 1 — Refresh the citation network

```bash
python tools/update_cited_by.py
python tools/parse_references.py --curate --all wiki/sources/
```

`update_cited_by.py` rebuilds the reverse-citation index from each source's
`cites:` frontmatter. `parse_references.py --curate` validates each DOI
against Crossref and recovers broken / missing DOIs via free-text search.

### 2 — Health checks (free, fast)

```bash
python tools/health.py
python tools/coverage_report.py --save
```

`health.py` is upstream's structural integrity check. `coverage_report.py`
flags concepts mentioned 3+ times that are still stubs and sources missing
either `methods:` or `intervention_family:`.

### 3 — Targeted analyses (per current focus)

```bash
python tools/method_matrix.py --intervention BCI --save
python tools/cohort_tracker.py --intervention BCI --save
python tools/dti_aggregator.py --save
python tools/effect_size_aggregator.py --outcome FM --save
python tools/replication_tracker.py --save
python tools/brain_atlas_anchor.py --save
```

Each `--save` writes to `wiki/syntheses/<slug>.md`. Without `--save`, the
report goes to stdout — useful for quick exploration.

### 4 — Discovery

```bash
python tools/watch_pubmed.py --init               # first time only
python tools/watch_pubmed.py --save               # weekly
python tools/suggest_readings.py MotorImagery --enrich
```

### 5 — Output (when writing)

```bash
python tools/bibtex_export.py > wiki.bib                          # master
python tools/bibtex_export.py --per-concept --output-dir bib/      # per concept
python tools/bibtex_export.py --per-intervention --output-dir bib/ # per intervention
python tools/bibtex_export.py --chapters chapters.yaml --output-dir bib/  # per manuscript chapter
```

The `--chapters` mode reads a YAML mapping (chapter name → list of wiki pages)
and emits one `.bib` per chapter, gathering only the sources actually
wikilinked from those pages.

### 6 — Audit a specific claim

```bash
python tools/audit_page.py wiki/concepts/MotorImagery.md --section "Empirical Evidence"
```

Returns a `git blame`-by-section view with each line mapped to its commit
and to the matching `wiki/log.md` ingest entry — useful when a thesis
reviewer asks *"where does this claim come from?"*.

## What You Get

**Persistent wiki** — structured markdown pages that accumulate across
sessions. Unlike chat, nothing is lost.

**Source pages — IMRAD by default** — every empirical paper ingested
produces a structured source page (Introduction · Methods · Results ·
Discussion · Reporting Standard Alignment · Extraction Checklist).
Specialized templates for systematic reviews (PRISMA-aware), narrative
reviews (thematic), scoping reviews (PRISMA-ScR), methodological
papers, and theoretical / framework papers.

**Concept pages — short academic chapters** — Overview · Historical
Genesis · Definitions · Theoretical Foundations · Mechanisms ·
Operationalization · Empirical Evidence · Clinical Relevance ·
Controversies · Seminal References (1500–3500 word target). Built
incrementally as new sources touch them.

**Method, intervention, recommendation, question pages** — measurement
instruments, treatment monographs, evidence-graded recommendations, and
open research questions, all auto-created and cross-referenced.

**Entity pages** — authors, labs, institutions, instrument vendors,
auto-created from each ingest's frontmatter.

**Citation network** — `cites:` extracted from each paper's References
section (regex + Crossref validation + free-text curation). `## Cited By`
maintained automatically. Snowball candidates surfaced per concept.

**Indirect Citation Rule** — claims a paper inherits from prior work
cite the **original** source, with explicit `reported via [[X]]`
provenance. Concept pages aggregate cited claims, not transmitter
citations.

**APA-ready output** — `citation_apa` and `bibtex_key` per source page.
`tools/bibtex_export.py` produces a master `wiki.bib` or per-chapter
files for a manuscript outline.

**Living overview** — `wiki/overview.md` is revised when synthesis
warrants. `tools/coverage_report.py` flags concepts mentioned ≥ 3 times
that are still stubs (priority expansions).

**Contradiction flags** — when a new source contradicts an existing
claim, it's flagged at ingest time with page references on both sides.

**Knowledge graph** — `graph.html` shows every wiki page as a node,
every `[[wikilink]]` as an edge, and inferred relationships as dotted
edges. Louvain community detection clusters related topics.

**Lint and audit** — orphan pages, broken links, uncited claims,
sources without DOI, snowball debt, replication chains, single-study
claims. `tools/audit_page.py` traces each line back to the ingest
that introduced it.

## Use Cases

### Building a thesis bibliography

Convert your PDF library, ingest paper by paper, get auto-organized
concept / method / intervention pages, and a per-chapter BibTeX export
when you start writing.

```
# Conversion + metadata + citations (one-shot, idempotent)
python pdf2md/pdf2md_marker.py "~/PDFs" raw/papers
python pdf2md/pdf2md_fallback.py "~/PDFs" raw/papers
python pdf2md/enrich_frontmatter.py raw/papers
python tools/parse_references.py --curate --all raw/papers

# Ingest in Claude Code (batch)
"Ingest all .md under raw/papers/ in batches of 5, shortest first."

# Periodic maintenance
python tools/update_cited_by.py
python tools/coverage_report.py --save

# When writing — BibTeX organized by manuscript chapter
python tools/bibtex_export.py --chapters chapters.yaml --output-dir bib/
```

By the end of your PhD you have a citation-rigorous wiki with every
paper summarized in IMRAD, every concept extended toward chapter depth,
and a BibTeX file ready for LaTeX or Word.

---

### Writing a literature review

Ingest the relevant sources, then ask the agent for a structured review:

```
review topic: corticospinal integrity as biomarker for motor recovery
```

The agent reads `wiki/index.md`, gathers all sources tagged with the
topic + the relevant `concepts/`, `methods/`, `recommendations/`,
`questions/` pages, and produces:

- Background and key concepts (cited)
- Methods used in the literature (table)
- Main findings (grouped by sub-theme, every claim cited)
- Recommendations (pulled from `recommendations/` pages)
- Open questions (pulled from `questions/` pages)
- Bibliography (APA, generated from each source's `citation_apa`)

You can save the review as `wiki/syntheses/<topic>-review.md`.

---

### Systematic review data extraction

After ingesting your included studies, generate a typed extraction
table from the SR's `cites:`:

```bash
python tools/extract_data.py --from-source cervera-2020 \
  --output cervera-extraction.xlsx
```

The Excel ships with three spec rows (INSTRUCTIONS / TYPE / SCALE) for
27 default columns (design, n per arm, demographics, intervention
parameters, outcomes, effect sizes, RoB, …). Edit the spec rows in
Excel, then fill:

```bash
python tools/extract_data.py cervera-extraction.xlsx --llm
```

Three layers per cell: frontmatter (deterministic) → body regex
(heuristic) → LLM with type/scale validation. Cached in
`tools/.cache/extract_llm.json`. Reports per-cell method
(frontmatter / regex / llm / manual / empty / invalid).

---

### Snowball ingestion

After ingesting key papers, surface DOIs that are cited 2+ times across
your wiki sources but not yet ingested:

```bash
python tools/suggest_readings.py MotorImagery --enrich --top 20
```

You get the candidates with title, authors, journal, year (Crossref
metadata) ranked by frequency. Pick which to download and ingest next.

For theses, the parent thesis page surfaces the snowball list directly
in its `## Notable References` section (☐ for not-yet-in-wiki).

---

### Comparing methodologies across the corpus

The repo ships six analyzers that walk `wiki/sources/` and emit
Markdown reports — zero LLM calls.

```bash
# Sources × design × N × methods × intervention
python tools/method_matrix.py --intervention BCI --save

# Aggregated patient profiles by intervention family
python tools/cohort_tracker.py --intervention TMS --save

# FA / MD / AD / RD per brain tract
python tools/dti_aggregator.py --save

# ΔFM / ΔARAT / Cohen's d / p-values
python tools/effect_size_aggregator.py --outcome FM --save

# Replication chains + single-study claims
python tools/replication_tracker.py --save

# Mentions of brain regions / tracts (M1, CST, callosum, …)
python tools/brain_atlas_anchor.py --save
```

Each report is filed in `wiki/syntheses/<name>.md` and feeds the
**Discussion** section of your manuscript with citation-grounded
synthesis.

## The Graph

Two-pass build:

1. **Deterministic** — parses all `[[wikilinks]]` across wiki pages → edges tagged `EXTRACTED`
2. **Semantic** — agent infers implicit relationships not captured by wikilinks → edges tagged `INFERRED` (with confidence score) or `AMBIGUOUS`

Louvain community detection clusters nodes by topic. SHA256 cache means only changed pages are reprocessed. Output is a self-contained `graph.html` — no server, opens in any browser.

## CLAUDE.md / AGENTS.md

The schema file tells the agent how to maintain the wiki — the two
non-negotiable rules (Citation, Depth), the sub-agent roster, and a
pointer index to the detailed procedure. It's a compact (~3.5 kB)
orchestrator file: heavy procedural detail (16-step ingest, source
organization, PDF pipeline, SR data extraction, output workflows,
standalone tools, frontmatter spec) lives in `docs/` and is loaded on
demand by the relevant sub-agent. Slash commands live in
`.claude/commands/`.

```
CLAUDE.md                          # Orchestrator: rules, roster, pointers
docs/
├── rules/
│   ├── citation.md                # Indirect Citation Rule, provenance
│   └── depth-completeness.md      # IMRAD expectations, self-critique gate
├── workflows/
│   ├── ingest.md                  # 16-step ingest procedure
│   ├── conversion.md              # PDF → Markdown pipeline
│   ├── source-organization.md     # Thematic folder routing
│   ├── data-extraction.md         # SR table extraction
│   ├── suggest-readings.md        # Snowball + OpenAlex forward
│   ├── long-document-ingestion.md # Theses ≥ 100 pages
│   └── output-workflows.md        # Query / Review / Lint / Health / Graph
├── templates/
│   ├── source-academic-paper.md
│   ├── source-systematic-review.md
│   ├── source-narrative-review.md
│   ├── source-scoping-review.md
│   ├── source-methodological-paper.md
│   ├── source-theoretical-paper.md
│   ├── source-thesis.md
│   ├── concept.md  method.md  intervention.md
│   ├── recommendation.md  question.md  entity.md  overview.md
│   └── diary.md  meeting.md
├── conventions/
│   ├── naming.md                  # Slug + domain quick-ref
│   ├── frontmatter.md             # Canonical YAML shape per page type
│   └── index-log.md               # wiki/index.md, wiki/log.md, overview format
└── tools.md                        # Concept consolidation, replication, audit
```

This separation keeps `CLAUDE.md` lean enough to fit comfortably in
context every session while specialist sub-agents pull only the
detailed procedure they need.

| Agent | Schema file |
|---|---|
| Claude Code | `CLAUDE.md` + `.claude/{agents,commands}/` |
| Codex / OpenCode | `AGENTS.md` |
| Gemini CLI | `GEMINI.md` |

## What Makes This Different from RAG

| RAG | LLM Wiki Agent (Academic Edition) |
|---|---|
| Re-derives knowledge every query | Compiles once, keeps current |
| Raw chunks as retrieval unit | Structured wiki pages |
| No cross-references | Cross-references pre-built |
| Contradictions surface at query time (maybe) | Flagged at ingest time |
| No accumulation | Every source makes the wiki richer |
| Citations are guesses or absent | Every claim cites `[[source]] (p. N)`, APA-ready |
| Cites the retriever's chunk | Indirect Citation Rule: cite the original paper, not the transmitter |
| No bibliography output | `citation_apa` + `bibtex_key` per source, `## Bibliography (APA)` in literature reviews |

## Obsidian Integration

The wiki is designed to be browsed seamlessly in [Obsidian](https://obsidian.md). Since the agent maintains consistent `[[wikilinks]]`, you get a naturally growing knowledge graph in your vault.

### Vault Symlink Pattern
If you want to keep the LLM Wiki Agent repository separate from your main personal vault, use symlinks:
1. Keep your working agent repository at e.g., `~/llm-wiki-agent`
2. Create a symlink from your main Obsidian vault:
   ```bash
   ln -sfn ~/llm-wiki-agent/wiki ~/your-obsidian-vault/wiki
   ```
3. Use the [Obsidian Web Clipper](https://obsidian.md/clipper) or write directly to `raw/` in the agent repo to queue items for ingestion.

> **Note:** If you ever move your local repo directory, remember to update the symlink, otherwise the `wiki/` directory will appear missing in Obsidian.

### Recommended .obsidian Config
- **Graph View:** Filter out `index.md` and `log.md` (e.g. `-file:index.md -file:log.md`) to avoid them becoming gravity wells in your Obsidian graph.
- **Dataview:** Use the community plugin [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) to query the YAML frontmatter the agent automatically injects (e.g., `type: source`, `tags: [diary]`).

## Multi-Format Ingest

For PDF papers and theses, use the dedicated **Academic Pipeline**
(above) — Marker + pymupdf4llm fallback gives higher fidelity than
generic conversion, and the Crossref enrichment step populates
bibliographic metadata automatically.

For occasional non-PDF sources (lab notes, conference transcripts,
slides), markitdown handles `.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`,
`.csv`, `.json`, `.xml`, `.rst`, `.rtf`, `.epub`, `.ipynb`. Drop the file
in `raw/notes/` and ingest directly:

```
ingest raw/notes/conference-talk-2024.docx
```

### arXiv preprints

```bash
python tools/pdf2md.py 2401.12345                       # by arXiv ID
python tools/pdf2md.py https://arxiv.org/abs/2401.12345 # by URL
```

Then ingest the resulting `.md` like any other source.

### Batch Directory Conversion (Advanced)

To pre-convert an entire directory (useful for bulk imports):
```bash
python tools/file_to_md.py --input_dir raw/imports/
python tools/file_to_md.py --input_dir raw/imports/ --delete_source  # remove originals
```

### Optional Dependencies

| Package | Install | Used for |
|---|---|---|
| [Marker](https://github.com/VikParuchuri/marker) | `pip install marker-pdf` | **Required** for `pdf2md/pdf2md_marker.py` — high-fidelity academic PDF conversion |
| [PyMuPDF4LLM](https://github.com/pymupdf/RAG) | `pip install pymupdf4llm` | **Required** for `pdf2md/pdf2md_fallback.py` — CPU rescue when Marker fails |
| [Mistral SDK](https://docs.mistral.ai/) | `pip install mistralai` + `MISTRAL_API_KEY` | **Optional** Document AI / OCR tier (`pdf2md/pdf2md_mistral.py`) for scanned PDFs, complex tables, equations. Swappable for Google Cloud Document AI, AWS Textract, Azure AI Document Intelligence — same input/output contract |
| [requests](https://requests.readthedocs.io/) + [PyYAML](https://pyyaml.org/) | `pip install requests pyyaml` | **Required** for `enrich_frontmatter.py`, `parse_references.py`, `suggest_readings.py`, `update_cited_by.py` (Crossref API + frontmatter parsing) |
| [tqdm](https://github.com/tqdm/tqdm) | `pip install tqdm` | Progress bars in the pdf2md pipeline |
| [markitdown](https://github.com/microsoft/markitdown) | `pip install markitdown` | Auto-conversion of non-PDF formats (.docx, .pptx, .xlsx, .html, …) |
| [arxiv2md](https://github.com/ryansingman/arxiv2md) | `pip install arxiv2markdown` | arXiv papers via structured source |

Quick install for the academic pipeline:

```bash
pip install marker-pdf pymupdf4llm requests pyyaml tqdm
```

## Tips

- For PDF libraries, run the dedicated `pdf2md/` pipeline before ingest
  (Marker is much higher fidelity than markitdown for academic PDFs).
- Run `tools/parse_references.py --curate` *after* the conversion pipeline
  but *before* ingestion — the agent then sees a clean `cites:` list and
  can wikilink to existing wiki sources directly.
- Re-run `tools/update_cited_by.py` after each batch of ingestions to
  refresh the reverse citation index.
- For theses, the agent surfaces a **citation snowball list** of
  high-value references at the end of the ingest summary — pick which
  to ingest next.
- Use `tools/suggest_readings.py <concept>` to identify what to read next
  to deepen a concept that feels under-supported.
- Query answers are shown first — the agent then asks if you want to
  file them as `wiki/syntheses/<topic>-review.md` pages.
- The wiki is a git repo — version history for free.
- Standalone Python scripts in `tools/` work without a coding agent
  (Crossref scripts require internet but no API key).

## Tech Stack

NetworkX + Louvain + Claude + vis.js. No server, no database, runs entirely locally. Everything is plain markdown files.

## Related & inspiration

- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) — the upstream this fork specializes for academic research. The "agent maintains a self-organizing wiki from source documents" pattern is theirs; the IMRAD templates, Indirect Citation Rule, PDF pipeline, and SR tooling are this fork's additions.
- [Andrej Karpathy — Software 3.0 (Sequoia AI Ascent, 2025)](https://www.youtube.com/watch?v=LCEmiRjPEtQ) — the framing of LLMs as a new programming layer that reads, synthesizes, and writes natural-language artefacts. This project applies that lens to academic literature: instead of retrieving chunks for one query, an agent compiles a persistent, citation-rigorous knowledge base.
- [Andrej Karpathy — Intro to LLMs](https://www.youtube.com/watch?v=zjkBMFhNj_g) — accessible primer on what LLMs are good at and where they fail, useful background for understanding why this project trusts the agent for synthesis but not for inventing citations.
- [graphify](https://github.com/safishamsi/graphify) — graph-based knowledge extraction skill (inspiration for the graph layer in upstream).
- [Vannevar Bush's Memex (1945)](https://en.wikipedia.org/wiki/Memex) — the original vision this resembles.

## License

MIT License — see [LICENSE](LICENSE) for details.
