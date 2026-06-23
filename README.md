# LLM Wiki Agent - Academic Edition

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A coding agent skill, specialized for academic research.** Drop a PDF library into `raw/` and tell the agent to ingest it - the wiki builds itself: source summaries with verbatim citations, concept pages structured as short academic chapters, methodology pages, recommendations grouped by evidence strength, open research questions, and a citation network that connects every paper to what it cites and what cites it.

This is a fork of [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) specialized for academic research workflows. The upstream supplies the core "agent maintains a wiki from source documents" pattern; this fork adds the IMRAD source templates, the Indirect Citation Rule, the PDF→Markdown pipeline (Marker + pymupdf4llm + Crossref), and the systematic-review tooling. Spiritually inspired by Andrej Karpathy's vision of LLMs as a new computing layer ("[Software 3.0](https://www.youtube.com/watch?v=LCEmiRjPEtQ)") - the agent doesn't just retrieve, it reads, structures, and writes back into a persistent knowledge graph.

> Most knowledge tools make you search your own notes. This one reads everything you've collected and writes a structured wiki that compounds over time - cross-references already built, contradictions already flagged, synthesis already done. **In this fork, every factual claim cites a source page with a page number, every paper's bibliography is parsed and validated against Crossref, and snowball candidates are surfaced automatically.**

The agent core is **domain-neutral** - same IMRAD extraction, same citation network, same snowball discovery regardless of field. A single file at the repo root, **`context.md`**, tells the agent which domain *your* GraphBib instance covers: expected concepts, methods, intervention taxonomy, outcome scales, style notes. The shipped `context.md` configures the agent for **stroke motor rehabilitation via MI-BCI / TMS + DTI** - replace it with one of `docs/context/examples/` (or a custom one) to retarget. See [Adapting to your domain](#adapting-to-your-domain) below.

```
raw/                  # Immutable source documents - never modified
├── <vault-name>/     # Per-vault raw inputs (mirrors wiki/<vault-name>/)
│   ├── papers/       # Journal articles
│   ├── theses/       # PhD/MSc theses (with citation snowball)
│   ├── books/        # Academic books, edited volumes, handbooks (EPUB-friendly)
│   └── notes/        # Lab reports, conference talks, personal notes
└── …                 # Additional raw vaults for other domains
wiki/                 # Multi-vault knowledge graph (one Obsidian vault per research domain)
├── <vault-name>/     # e.g. stroke-rehab/, cardiology/, nlp-research/
│   ├── index.md      # Vault catalog - updated on every ingest
│   ├── log.md        # Append-only chronological record
│   ├── overview.md   # Living synthesis across this vault's sources
│   ├── sources/      # One academic summary per ingested source
│   ├── entities/     # Authors, labs, institutions
│   ├── concepts/     # Theoretical concepts, structured as book chapters
│   ├── methods/      # Methodologies & instruments
│   ├── recommendations/  # Clinical/research recommendations grouped by evidence
│   ├── questions/    # Open research questions identified across the corpus
│   └── syntheses/    # Saved query answers and literature reviews
└── …                 # Additional vault sub-folders for other domains
project-review/       # Self-contained review projects (NOT in Obsidian) - Extractor orchestrator
├── <vault>/          # Per-vault container - independent from wiki/<vault>/
│   └── <name>/       # One folder per systematic / scoping / narrative review
│   ├── contexte.md       # Shared scope - review type, objective, question, outcomes
│   ├── log.md            # Audit trail across both phases
│   ├── background/       # USER-AUTHORED context (input to every sub-agent)
│   │   ├── notes.md      # Domain primer read by screener-tiab/fulltext + extractor
│   │   ├── raw/          # Seminal PDFs / prior reviews (user reference)
│   │   └── markdown/     # Converted MDs (user reference)
│   ├── screening/        # PRISMA 2020 - title/abstract + full-text passes
│   │   ├── criteria.md            # PICO + IN/OUT criteria with mnemonic tags
│   │   ├── identified/            # Raw CSV exports (pubmed.csv, scopus.csv, …)
│   │   ├── dedup.csv              # After dedup (DOI > PMID > fuzzy title)
│   │   ├── tiab-decisions.csv     # Pass 1 - decision + reason + side_use
│   │   ├── fulltext-decisions.csv # Pass 2 - decision + verbatim excerpts + side_use
│   │   ├── 1st-pass/
│   │   │   ├── raw/               # PDFs auto-fetched after T/A inclusion
│   │   │   ├── markdown/          # Converted for full-text reading
│   │   │   └── missing.md         # Paywalled - manual user fetch
│   │   └── reports/
│   │       ├── tiab-report.md
│   │       ├── fulltext-report.md
│   │       └── prisma-flowchart.md  # Auto-generated Mermaid + count table
│   └── extraction/       # Data extraction phase
│       ├── instructions.md   # Per-column extraction spec (agent-authored + reviewed)
│       ├── template.xlsx     # 2-row template (row 1 = headers, row 2 = instructions)
│       ├── articles/         # Source MDs (fed by screening or wiki/sources/)
│       ├── output/
│       │   ├── extraction-detailed.xlsx   # Verbatim + units + source location
│       │   └── extraction-coded.xlsx      # Strict per-instruction, R-ready
│       └── biblio/
│           ├── side/         # OUTPUT - side refs auto-flagged during screening
│           │   ├── intro/        # Cite in introduction / motivation
│           │   ├── discussion/   # Cite in discussion / interpretation
│           │   ├── method/       # Methodological references (scale validation, …)
│           │   ├── reco/         # Clinical / practice recommendations
│           │   └── general/      # Useful side reference, category unclear
│           ├── raw/          # PDF copies of included articles (cp, never mv)
│           └── markdown/     # MD copies from wiki/sources/ (cp, never mv)
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

Open in your agent - no API key or Python setup needed:

```bash
claude      # reads CLAUDE.md + .claude/commands/ (slash commands available)
codex       # reads AGENTS.md
opencode    # reads AGENTS.md
gemini      # reads GEMINI.md
```

## Quick start (60 seconds)

Three steps inside the agent - **init the layout, add a source, ingest**.

### 1. Init - bootstrap the folder structure

```
/wiki-init <vault-name>
```

e.g. `/wiki-init stroke-rehab` or `/wiki-init cardiology`. Each
**vault** is a self-contained Obsidian-compatible knowledge graph
for one research domain - you can have many side-by-side under
`wiki/`. The command creates BOTH sides in lockstep:
`raw/<vault-name>/{papers,theses,books,notes}/` for the raw inputs
and `wiki/<vault-name>/{sources,concepts,methods,interventions,
recommendations,questions,entities,syntheses}/` for the ingested
graph, plus seeds empty `index.md` / `log.md` / `overview.md`
inside the new vault.

When multiple vaults exist, set `$WIKI_VAULT=<name>` to tell the
tools which one to operate on (resolves BOTH `wiki/<vault>/` and
`raw/<vault>/`). Single-vault setups are auto-detected; legacy flat
`wiki/sources/` + `raw/papers/` layouts keep working.

### 2. Add a source - drop a file into the right `raw/` folder

Markdown sources are ready immediately. PDF and EPUB sources need a
one-shot conversion:

```
/wiki-convert ~/path/to/your/PDFs         # PDFs  → raw/<vault>/papers/*.md
/wiki-convert ~/path/to/your/EPUBs        # EPUBs → raw/<vault>/books/*.md
```

The conversion pipeline (Marker → pymupdf4llm fallback → Crossref
enrichment → DOI curation for PDFs; pandoc + OPF metadata for EPUBs)
runs idempotently - already-converted files are skipped.

### 3. Ingest - the agent builds the wiki

```
ingest raw/<vault>/papers/cervera-2020.md
```

In a single pass the agent produces:

- `wiki/sources/cervera-2020.md` - IMRAD-structured summary with verbatim quotes + page numbers
- `wiki/concepts/*.md` - every concept the paper touches (created or extended chapter-style)
- `wiki/methods/*.md` - every method described (FuglMeyer, MEP, EEG, DTI…)
- `wiki/recommendations/*.md` - any clinical / research recommendations, grouped by evidence
- `wiki/questions/*.md` - open research questions surfaced from the discussion
- `wiki/entities/*.md` - authors, labs, institutions
- `index.md` / `log.md` / `overview.md` - all updated
- frontmatter `cites: [DOIs]` populated, ready for `/wiki-snowball` and reverse-citation index

For batch work: `/wiki-batch-ingest raw/<vault>/papers/` (or `raw/<vault>/books/`) processes a whole directory with confirmation between batches.

That's it - the wiki compounds from there. Everything below is depth.

## Adapting to your domain

GraphBib's agent core is field-agnostic. **Domain orientation lives in a single file: `context.md` at the repo root.** It declares:

- The field's identity and central question
- Expected **concepts** vocabulary (so repeated mentions land on the same page rather than spawning near-duplicates)
- Expected **methods** vocabulary (measurement instruments, modalities)
- **Interventions taxonomy** - two-tier `intervention_family` / `intervention_subfamily` enum
- **Outcome scales** for systematic-review extraction
- **Anatomical / structural anchors** (when relevant)
- **Recommendation topics** under which the agent aggregates recommendations
- **Style notes** - domain-specific writing conventions

### Three ways to retarget

```bash
# A. Pick a pre-built example
cp docs/context/examples/clinical-trials-cardiology.md context.md

# B. Start from the neutral baseline and customize
cp docs/context/examples/generic-academic.md context.md
${EDITOR:-vim} context.md

# C. Agent-assisted - open a fresh session and say:
#    "Initialize context.md for a wiki on <X>. Ask me 5 clarifying
#     questions, then draft the taxonomy."
```

The shipped `context.md` configures the agent for **stroke motor rehabilitation via MI-BCI / TMS + DTI** (the de-facto specialization of this fork). Replace it with your own to retarget.

### Beyond context.md - code-level audits

Some domain bias still lives in **Python** that needs separate editing if you're moving to a non-stroke field:

| File | Why | Action |
|---|---|---|
| `tools/organize_sources.py` | `FAMILY_FOLDER` is a hardcoded Python dict mirroring the interventions taxonomy | Edit `FAMILY_FOLDER` to match your `context.md` |
| `tools/dti_aggregator.py`, `tools/effect_size_aggregator.py`, `tools/brain_atlas_anchor.py`, `tools/cohort_tracker.py` | Stroke / motor-rehab specific regex (CST, FuglMeyer, ARAT, etc.) | Leave inert, delete, or rewrite for your domain |
| `.claude/agents/*.md` | Sub-agent system prompts contain stroke examples | Search for `stroke`, `MI-BCI`, `TMS` and adapt |

These tools won't *break* if you leave them - they'll just become inert (regex match nothing). Full adaptation checklist in [`docs/context/README.md`](docs/context/README.md).

## Usage

The agent understands natural language and shorthand triggers:

```
ingest raw/<vault>/papers/cervera-2020.md          # ingest a markdown source
ingest raw/<vault>/papers/                         # batch ingest a directory
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

**Claude Code** ships 14 slash commands wrapping the agent ecosystem:

| Discovery | Conversion | Ingestion | Output | Maintenance |
|---|---|---|---|---|
| `/wiki-snowball` | `/wiki-convert` | `/wiki-init` | `/wiki-query` | `/wiki-status` |
| `/wiki-discover` | | `/wiki-batch-ingest` | `/wiki-review` | `/wiki-maintain` |
| | | `/wiki-deepen` | `/extractor-init` | `/wiki-remove` |
| | | | `/extractor-table` | `/wiki-dedupe` |

`/wiki-discover` chains *suggest → fetch → convert → ingest* end-to-end.
`/wiki-maintain` runs lint then delegates fixes to the librarian
sub-agent. Other agents (Codex, Gemini, etc.) use the natural language
triggers above, which work identically - every slash command has a
plain-English equivalent.

Markdown is the native ingestion format. For PDF-heavy academic
libraries, the next section describes the dedicated pipeline (Marker +
pymupdf4llm fallback + Crossref enrichment + curation).

### Specialist sub-agents

Twelve focused sub-agents live in `.claude/agents/`. Each has its own
context window and a tier-appropriate model - the parent agent stays
orchestrator while specialists do the focused work. Slash commands
above delegate automatically; you can also invoke them directly via
the `Agent` tool.

| Sub-agent | Model | Role |
|---|---|---|
| `suggest-reading` | sonnet | Find what to read next (snowball + OpenAlex forward) |
| `fetch-reading` | haiku | Download OA PDFs for a DOI list (Unpaywall) |
| `ingester` | sonnet | Ingest one source - forces all 16 ingest steps |
| `source-extender` | sonnet | Deepen an already-ingested shallow source |
| `concept-builder` | sonnet *(opus opt-in)* | Extend one concept page to chapter depth - pass "with opus" / "use opus" for theoretically-dense concepts |
| `extractor` | haiku | Fill one cell of a SR data-extraction table |
| `query-synthesizer` | sonnet | Answer a focused research question |
| `reviewer` | sonnet *(opus opt-in)* | Generate a structured literature review - pass `--opus` to `/wiki-review` for high-stakes / contradiction-heavy reviews |
| `lint` | sonnet | Audit (deterministic + cached semantic) |
| `librarian` | sonnet | Act on lint findings - auto-fix / delegate / confirm |
| `source-remover` | sonnet | Cleanly remove a source and every cross-reference |
| `deduplicator` | sonnet | Judge redundant concept/method pages, merge or extract via deterministic pre-filter |

**Opus opt-in** for `reviewer` and `concept-builder`: these are the two synthesis-heavy agents where Opus' long-form coherence and contradiction handling move the needle. By **default both run on Sonnet** (fast, cheap, solid for routine work). Override with `/wiki-review <topic> --opus` or by asking the orchestrator to "build / extend `<Concept>` with opus". Opus ≈ 5× Sonnet pricing - worth it on high-stakes outputs (papers, grants, guidelines), wasteful on routine synthesis.

## Academic Pipeline

End-to-end flow for converting a PDF library into a citation-rigorous wiki.
Each step is idempotent and can be re-run safely.

```
PDF library                                         EPUB library (academic books)
   │                                                   │
   ▼  pdf2md/pdf2md_marker.py     (free, primary)      ▼  pdf2md/epub2md.py
   │  pdf2md/pdf2md_mistral.py    (Document AI, paid)  │     ← pandoc (primary) or markitdown (fallback)
   │  pdf2md/pdf2md_fallback.py   (free, last resort)  │     ← OPF metadata → title, authors, editors,
   │                                                   │       ISBN, publisher, year, language
   │                                                   │
   ▼  Markdown files (raw/<vault>/papers/)                     ▼  Markdown files (raw/<vault>/books/)
   │
   ▼  pdf2md/enrich_frontmatter.py  ← Crossref → title, authors, journal, year, DOI
   │                                  Regex → cites: [DOIs]
   │
   ▼  tools/parse_references.py --curate
   │     ↳ Phase 1 - extract DOIs from References (regex)
   │     ↳ Phase 2 - validate each DOI against Crossref agency endpoint
   │     ↳ Phase 3 - recover broken/missing DOIs via Crossref free-text search
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

### Step 1 - PDF → Markdown

```bash
python pdf2md/pdf2md_marker.py "/path/to/PDFs" raw/<vault>/papers
python pdf2md/pdf2md_fallback.py "/path/to/PDFs" raw/<vault>/papers
```

`pdf2md_marker.py` walks the source directory recursively, runs each PDF
through [marker-pdf](https://github.com/VikParuchuri/marker), mirrors the
folder structure, and writes a frontmatter header (`source_pdf`, `title`,
`backend: marker`). Idempotent - already-converted files are skipped.
Output: `marker.log`, `marker_report.json` summarizing OK / suspicious /
errors.

`pdf2md_fallback.py` reads `marker_report.json` and reprocesses every PDF
that failed or produced a suspiciously short output, this time with
[pymupdf4llm](https://github.com/pymupdf/RAG) (CPU, no ML dependency).
Useful when Marker / Surya hits known MPS bugs on certain PDFs. The
backend used for each `.md` is recorded in its frontmatter.

#### Optional - Document AI tier for hard PDFs

For scanned papers, complex tables, equations, or two-column layouts
that defeat both Marker and pymupdf4llm, the pipeline supports a
middle tier backed by a hosted Document AI / OCR API. The reference
implementation uses **Mistral Document AI**:

```bash
export MISTRAL_API_KEY=...                  # console.mistral.ai
python pdf2md/pdf2md_mistral.py "/path/to/PDFs" raw/<vault>/papers
```

Reads `marker_report.json` and only sends the entries Marker errored
on or flagged as suspicious - typically 10-20 % of a corpus. Paces
itself at ~2 req/s; the experimental plan is free with rate limits.
Output is mirrored to `raw/<vault>/papers/` with `backend: mistral` in the
frontmatter so the source of each markdown is auditable.

The script is a thin adapter (PDF → API → markdown + frontmatter), so
**other Document AI providers plug into the same slot**: Google Cloud
Document AI, AWS Textract, Azure AI Document Intelligence, Adobe PDF
Extract, or Reducto. Copy `pdf2md_mistral.py`, swap the API call, keep
the same input/output contract (`marker_report.json` driver, mirrored
output path, `backend: <provider>` frontmatter), and the rest of the
pipeline is provider-agnostic.

### Step 1b - EPUB → Markdown (academic books)

```bash
python pdf2md/epub2md.py "/path/to/EPUBs"              # default DST: raw/<vault>/books/
python pdf2md/epub2md.py "/path/to/EPUBs" raw/<vault>/books    # explicit DST
python pdf2md/epub2md.py "/path/to/EPUBs" raw/<vault>/books --engine markitdown
```

`epub2md.py` walks the source directory recursively for `*.epub`,
mirrors arborescence to `raw/<vault>/books/`, and converts each book to
Markdown via **pandoc** (primary, install with `apt install pandoc`
or `brew install pandoc`) or **markitdown** (fallback, `pip install
markitdown`). Bibliographic metadata is extracted from the EPUB's
OPF manifest - `title`, `authors`, `editors`, `year`, `publisher`,
`isbn`, `language` - and written to frontmatter alongside `backend:
pandoc-epub` (or `markitdown-epub`). Idempotent. Output:
`epub.log`, `epub_report.json`.

EPUB carries chapter structure natively, so pandoc's output preserves
`# Chapter` headings cleanly - `pdf2md/split_thesis.py` (which is
type-agnostic, despite the name) can then split a long book or
edited handbook into per-chapter pages that ingest separately:

```bash
python pdf2md/split_thesis.py raw/<vault>/books/<slug>.md
```

The chapters become `raw/<vault>/books/<slug>/chXX-<title>.md`, ingest via
`source-academic-paper.md` with the `parent_book` / `book_editors`
frontmatter fields documented in `docs/templates/source-book.md`.

### Step 2 - Enrich Bibliographic Metadata

```bash
python pdf2md/enrich_frontmatter.py raw/<vault>/papers
```

For each `.md`, finds the DOI (regex over the body and the first PDF
page) and queries Crossref for canonical `title`, `authors`, `journal`,
`year`. Same pass also extracts a raw list of cited DOIs from the
References section into `cites: []`.

Outputs `enrich_report.json` with the breakdown: Crossref-resolved /
DOI-only / no-DOI / errors / how many sources got `cites:` populated.

### Step 3 - Validate and Curate Citations

```bash
python tools/parse_references.py --curate --all raw/<vault>/papers
```

Three opt-in phases:
1. **Extract** - regex DOI extraction (offline, fast).
2. **Validate** - Crossref `/works/{doi}/agency` check; drops invalid
   DOIs (typically broken at line breaks during PDF extraction).
3. **Curate** - for entries with no valid DOI, free-text bibliographic
   search recovers the canonical DOI, accepted only when relevance
   score and title overlap pass thresholds.

Frontmatter:
```yaml
cites: [doi1, doi2, ...]              # all validated DOIs (regex + curated)
cites_curated: [doi3]                  # subset recovered via free-text (audit)
cites_unresolved:                      # entries no DOI could be assigned to
  - "Smith J, Brown K. ..."
```

Cache: `tools/.cache/doi_validation.json` - once a DOI is validated,
subsequent runs skip the network call. Estimated cost on a fresh
698-paper corpus: ~13 min; subsequent runs: ~5 min.

### Step 4 - Ingest into the Wiki

```bash
claude
```

Then in the agent:
```
ingest raw/<vault>/papers/cervera-2020.md
ingest raw/<vault>/papers/   # batch - process by length, ascending
```

Or in plain English:
```
"Ingest all PDFs under raw/<vault>/papers/ in batches of 5, shortest first.
 Confirm after each batch."
```

Claude reads `CLAUDE.md` and applies the academic schema:
- **Source pages** with explicit `## Background (from cited literature)`,
  `## Methods`, `## Results (this paper's findings)`, `## Discussion` - 
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

For theses (`raw/<vault>/theses/*`), Claude additionally extracts a
**citation snowball list** of high-value references the thesis builds on.

### Step 5 - Build and Maintain the Citation Network

```bash
python tools/update_cited_by.py
```

Walks `wiki/sources/`, builds the reverse-citation index from each
source's `cites:` frontmatter, and rewrites every source's `## Cited By`
section with `[[wikilinks]]` pointing to the papers that cite it. Run
after each batch of ingestions.

### Step 6 - Surface Complementary Readings

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
| `pdf2md/epub2md.py` | EPUB → Markdown via pandoc (primary) or markitdown (fallback); extracts OPF metadata (title, authors, editors, ISBN, publisher, year) into frontmatter |
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

### 1 - Refresh the citation network

```bash
python tools/update_cited_by.py
python tools/parse_references.py --curate --all wiki/sources/
```

`update_cited_by.py` rebuilds the reverse-citation index from each source's
`cites:` frontmatter. `parse_references.py --curate` validates each DOI
against Crossref and recovers broken / missing DOIs via free-text search.

### 2 - Health checks (free, fast)

```bash
python tools/health.py
python tools/coverage_report.py --save
```

`health.py` is upstream's structural integrity check. `coverage_report.py`
flags concepts mentioned 3+ times that are still stubs and sources missing
either `methods:` or `intervention_family:`.

### 3 - Targeted analyses (per current focus)

```bash
python tools/method_matrix.py --intervention BCI --save
python tools/cohort_tracker.py --intervention BCI --save
python tools/dti_aggregator.py --save
python tools/effect_size_aggregator.py --outcome FM --save
python tools/replication_tracker.py --save
python tools/brain_atlas_anchor.py --save
```

Each `--save` writes to `wiki/syntheses/<slug>.md`. Without `--save`, the
report goes to stdout - useful for quick exploration.

### 4 - Discovery

```bash
python tools/watch_pubmed.py --init               # first time only
python tools/watch_pubmed.py --save               # weekly
python tools/suggest_readings.py MotorImagery --enrich
```

### 5 - Output (when writing)

```bash
python tools/bibtex_export.py > wiki.bib                          # master
python tools/bibtex_export.py --per-concept --output-dir bib/      # per concept
python tools/bibtex_export.py --per-intervention --output-dir bib/ # per intervention
python tools/bibtex_export.py --chapters chapters.yaml --output-dir bib/  # per manuscript chapter
```

The `--chapters` mode reads a YAML mapping (chapter name → list of wiki pages)
and emits one `.bib` per chapter, gathering only the sources actually
wikilinked from those pages.

### 6 - Audit a specific claim

```bash
python tools/audit_page.py wiki/concepts/MotorImagery.md --section "Empirical Evidence"
```

Returns a `git blame`-by-section view with each line mapped to its commit
and to the matching `wiki/log.md` ingest entry - useful when a thesis
reviewer asks *"where does this claim come from?"*.

## What You Get

**Persistent wiki** - structured markdown pages that accumulate across
sessions. Unlike chat, nothing is lost.

**Source pages - IMRAD by default** - every empirical paper ingested
produces a structured source page (Introduction · Methods · Results ·
Discussion · Reporting Standard Alignment · Extraction Checklist).
Specialized templates for systematic reviews (PRISMA-aware), narrative
reviews (thematic), scoping reviews (PRISMA-ScR), methodological
papers, and theoretical / framework papers.

**Concept pages - short academic chapters** - Overview · Historical
Genesis · Definitions · Theoretical Foundations · Mechanisms ·
Operationalization · Empirical Evidence · Clinical Relevance ·
Controversies · Seminal References (1500-3500 word target). Built
incrementally as new sources touch them.

**Method, intervention, recommendation, question pages** - measurement
instruments, treatment monographs, evidence-graded recommendations, and
open research questions, all auto-created and cross-referenced.

**Entity pages** - authors, labs, institutions, instrument vendors,
auto-created from each ingest's frontmatter.

**Citation network** - `cites:` extracted from each paper's References
section (regex + Crossref validation + free-text curation). `## Cited By`
maintained automatically. Snowball candidates surfaced per concept.

**Indirect Citation Rule** - claims a paper inherits from prior work
cite the **original** source, with explicit `reported via [[X]]`
provenance. Concept pages aggregate cited claims, not transmitter
citations.

**APA-ready output** - `citation_apa` and `bibtex_key` per source page.
`tools/bibtex_export.py` produces a master `wiki.bib` or per-chapter
files for a manuscript outline.

**Living overview** - `wiki/overview.md` is revised when synthesis
warrants. `tools/coverage_report.py` flags concepts mentioned ≥ 3 times
that are still stubs (priority expansions).

**Contradiction flags** - when a new source contradicts an existing
claim, it's flagged at ingest time with page references on both sides.

**Knowledge graph** - `graph.html` shows every wiki page as a node,
every `[[wikilink]]` as an edge, and inferred relationships as dotted
edges. Louvain community detection clusters related topics.

**Lint and audit** - orphan pages, broken links, uncited claims,
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
python pdf2md/pdf2md_marker.py "~/PDFs" raw/<vault>/papers
python pdf2md/pdf2md_fallback.py "~/PDFs" raw/<vault>/papers
python pdf2md/enrich_frontmatter.py raw/<vault>/papers
python tools/parse_references.py --curate --all raw/<vault>/papers

# Ingest in Claude Code (batch)
"Ingest all .md under raw/<vault>/papers/ in batches of 5, shortest first."

# Periodic maintenance
python tools/update_cited_by.py
python tools/coverage_report.py --save

# When writing - BibTeX organized by manuscript chapter
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

### Systematic review - screening + extraction

Review projects live under `project-review/<vault>/<name>/` - 
**separate from the Obsidian wiki**, self-contained per review,
organized in two sequential phases. The `<vault>` is independent
from the wiki vault (set via `$PROJECT_VAULT` or as the first path
segment, e.g. `BCINET/mibci`):

```
project-review/BCINET/mibci/
├── contexte.md          # Shared scope (PICO, objective, question, outcomes)
├── screening/           # PRISMA 2020 - pass 1 (T/A) + pass 2 (full text)
│   ├── criteria.md            # PICO + IN/OUT criteria with mnemonic tags
│   ├── identified/            # User drops CSV exports (pubmed.csv, scopus.csv, …)
│   ├── tiab-decisions.csv     # Per-record decisions from pass 1
│   ├── fulltext-decisions.csv # Per-article decisions from pass 2 (with verbatim excerpts)
│   ├── 1st-pass/{raw,markdown}/   # PDFs auto-fetched + converted for pass 2
│   └── reports/{tiab,fulltext,prisma-flowchart}.md  # Auto-generated
└── extraction/          # Phase 2 - data extraction
    ├── instructions.md  # Per-column extraction spec (agent-authored from Phase 1 debrief)
    ├── template.xlsx    # 2-row template (variable name + instruction)
    ├── articles/        # MDs of included articles (copied from screening or wiki)
    └── output/
        ├── extraction-detailed.xlsx   # Verbatim + units + source location
        └── extraction-coded.xlsx      # Strict per-instruction (R-ready)
```

**Five slash commands drive the workflow:**

#### Phase 1 - PRISMA screening (optional)

1. **`/extractor-screen-init <name>`** - interactive build of PICO +
   inclusion / exclusion criteria → `screening/criteria.md`. Each
   criterion gets a mnemonic tag (`wrong-population`, `not-RCT`,
   `non-english`, …) consumed by the screener sub-agents in their
   decision output.

2. **`/extractor-screen-tiab <name>`** - pass 1, title/abstract.
   - Dedupes CSV exports (DOI > PMID > fuzzy title/author/year)
   - Fetches missing abstracts via PubMed → OpenAlex → Crossref cascade
   - Delegates one decision per record to the `screener-tiab`
     sub-agent (haiku - title + abstract only, never reads PDFs)
   - **Reads `background/notes.md`** when present (domain primer
     authored by the user - gives every screener decision the same
     context)
   - Defaults to over-inclusion (`uncertain` → retrieve)
   - **Flags side-useful excludes** (`intro` / `discussion` /
     `method` / `reco` / `general`)
   - Auto-fetches PDFs of included articles via Unpaywall
   - Lists paywalled PDFs in `1st-pass/missing.md` for manual fetch
   - Updates the PRISMA flowchart

3. **`/extractor-screen-fulltext <name>`** - pass 2, full text.
   - Reads each article's MD body via the `screener-fulltext`
     sub-agent (sonnet - Methods + Results mandatory)
   - **Reads `background/notes.md`** when present (same primer as T/A)
   - Every full-text exclusion carries a **verbatim excerpt + source
     location** (audit trail)
   - **Re-evaluates side-use on a more reliable basis** (the body) - 
     with optional justifying excerpt + location per side flag
   - Mandatory user audit gate (sample + all `uncertain` + all
     `side_use` flagged rows)
   - Copies included articles into `extraction/articles/`
   - Copies side-flagged excludes into
     `extraction/biblio/side/<category>/<slug>.md` + appends to the
     per-category `index.md`

#### Phase 2 - data extraction

4. **`/extractor-init <name>`** - interactive bootstrap.
   Creates the full project skeleton (both `screening/` and
   `extraction/`), then walks you through:
   - **contexte.md** (5 structured questions: review type, objective,
     research question, primary outcomes, style notes - plus 0-5
     targeted follow-ups; eligibility criteria section for inclusion/
     exclusion rules used to flag wrongly-included articles)
   - **template** (co-design if blank: default 27-col SR set,
     category subset, or paste custom list)
   - **instructions** (per-column dialog: type-hint / categorical-strict /
     categorical-open / coded / NL - with int vs float and strict vs open
     confirmation)
   - **Step 8d - mandatory instruction review pass**: after saisie,
     scans all columns for 10 issue types (empty, no NR fallback, open/
     closed ambiguity, missing units, inconsistent tokens, etc.), severity
     triage 🔴/🟠/🟡, resolves one by one before finalising

5. **`/extractor-table project-review/<vault>/<name>/`** - runs extraction.
   - **Phase 1b** - article resolution: for each article, locates PDF
     (`extraction/biblio/raw/` or, if the project went through screening,
     `screening/1st-pass/raw/`) and MD via the wiki; copies both (never
     moves). Fuzzy PDF search when the filename doesn't match the slug
     exactly.
   - **Phase 1c** - eligibility check: compares each article's
     characteristics against the review's eligibility criteria in
     `screening/criteria.md` (or `contexte.md` if no screening was run);
     flags potential mismatches before extraction begins; user decides
     `Y / exclure`.
   - **Phase 2-3** - deterministic + LLM extraction; ambiguous cells
     tagged `À PRÉCISER - [verbatim]` without interrupting the batch.
   - **End-of-batch resolution**: ambiguous cells grouped by column;
     agent proposes adapted instruction → `Y` updates `template.xlsx`
     row 2 + `instructions.md` and re-extracts; user can also ignore.
   - **Phase 5** - adaptive refinement proposals (add column / split /
     refine instruction) based on observed patterns.
   - **Output format**: both detailed and coded files carry two header
     rows - row 1 = column names, row 2 = instructions (readable without
     opening the template).

**Template format (2-row)**:
- Row 1 = column headers (variable names)
- Row 2 = per-column instructions, polymorphic:
  - `a | b | c` → categorical strict (`| ...` makes it open)
  - `0=low, 1=high` → ordinal coded (returns the code)
  - `(int)` / `(integer)` → integer, rounds source decimals
  - `(years)` / `(0-100)` / `(mV)` → float with unit
  - Sentence (3+ words) → natural-language extraction rule
  - Empty → implicit, agent asks during Phase 1 debrief

**Detailed output cell format**: `<value> | <source location>`
(e.g. `12.4 ± 3.1 years | Table 1 row "Age"` or `RCT | Methods §"Study design"`).
The source location is precise - `Table N` / `Fig N` / `p.N §"heading"` /
`Section §"subsection"` - so you can audit any cell back to the page.

**Coded output**: same cells with the `| <source>` suffix stripped,
units removed for floats, decimals rounded for ints, categorical
labels canonicalized, strict mismatches blanked, open novel values
kept-but-flagged. Drop straight into R / Python / Excel pivot tables.

**Three layers per cell**: frontmatter (deterministic) → body regex
(heuristic) → LLM via the `extractor` sub-agent (haiku) with
type/closure validation. Cached in `tools/.cache/extract_llm.json`
keyed by (slug, column, instruction-hash) so re-runs on unchanged
instructions are free.

**Backward compatible**: the single-file legacy 4-row template
(INSTRUCTIONS / TYPE / SCALE markers) still works with
`tools/extract_data.py <template>` directly - same flow without the
project folder.

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
Markdown reports - zero LLM calls.

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

1. **Deterministic** - parses all `[[wikilinks]]` across wiki pages → edges tagged `EXTRACTED`
2. **Semantic** - agent infers implicit relationships not captured by wikilinks → edges tagged `INFERRED` (with confidence score) or `AMBIGUOUS`

Louvain community detection clusters nodes by topic. SHA256 cache means only changed pages are reprocessed. Output is a self-contained `graph.html` - no server, opens in any browser.

## CLAUDE.md / AGENTS.md

The schema file tells the agent how to maintain the wiki - the two
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
(above) - Marker + pymupdf4llm fallback gives higher fidelity than
generic conversion, and the Crossref enrichment step populates
bibliographic metadata automatically.

For occasional non-PDF sources (lab notes, conference transcripts,
slides), markitdown handles `.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`,
`.csv`, `.json`, `.xml`, `.rst`, `.rtf`, `.epub`, `.ipynb`. Drop the file
in `raw/<vault>/notes/` and ingest directly:

```
ingest raw/<vault>/notes/conference-talk-2024.docx
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
| [Marker](https://github.com/VikParuchuri/marker) | `pip install marker-pdf` | **Required** for `pdf2md/pdf2md_marker.py` - high-fidelity academic PDF conversion |
| [PyMuPDF4LLM](https://github.com/pymupdf/RAG) | `pip install pymupdf4llm` | **Required** for `pdf2md/pdf2md_fallback.py` - CPU rescue when Marker fails |
| [Mistral SDK](https://docs.mistral.ai/) | `pip install mistralai` + `MISTRAL_API_KEY` | **Optional** Document AI / OCR tier (`pdf2md/pdf2md_mistral.py`) for scanned PDFs, complex tables, equations. Swappable for Google Cloud Document AI, AWS Textract, Azure AI Document Intelligence - same input/output contract |
| [Pandoc](https://pandoc.org/) | `apt install pandoc` / `brew install pandoc` | **Recommended** for `pdf2md/epub2md.py` - preserves chapter headings, footnotes, equations from academic EPUBs; falls back to `markitdown` if absent |
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
  but *before* ingestion - the agent then sees a clean `cites:` list and
  can wikilink to existing wiki sources directly.
- Re-run `tools/update_cited_by.py` after each batch of ingestions to
  refresh the reverse citation index.
- For theses, the agent surfaces a **citation snowball list** of
  high-value references at the end of the ingest summary - pick which
  to ingest next.
- Use `tools/suggest_readings.py <concept>` to identify what to read next
  to deepen a concept that feels under-supported.
- Query answers are shown first - the agent then asks if you want to
  file them as `wiki/syntheses/<topic>-review.md` pages.
- The wiki is a git repo - version history for free.
- Standalone Python scripts in `tools/` work without a coding agent
  (Crossref scripts require internet but no API key).

## Tech Stack

NetworkX + Louvain + Claude + vis.js. No server, no database, runs entirely locally. Everything is plain markdown files.

## Related & inspiration

- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) - the upstream this fork specializes for academic research. The "agent maintains a self-organizing wiki from source documents" pattern is theirs; the IMRAD templates, Indirect Citation Rule, PDF pipeline, and SR tooling are this fork's additions.
- [Andrej Karpathy - Software 3.0 (Sequoia AI Ascent, 2025)](https://www.youtube.com/watch?v=LCEmiRjPEtQ) - the framing of LLMs as a new programming layer that reads, synthesizes, and writes natural-language artefacts. This project applies that lens to academic literature: instead of retrieving chunks for one query, an agent compiles a persistent, citation-rigorous knowledge base.
- [Andrej Karpathy - Intro to LLMs](https://www.youtube.com/watch?v=zjkBMFhNj_g) - accessible primer on what LLMs are good at and where they fail, useful background for understanding why this project trusts the agent for synthesis but not for inventing citations.
- [graphify](https://github.com/safishamsi/graphify) - graph-based knowledge extraction skill (inspiration for the graph layer in upstream).
- [Vannevar Bush's Memex (1945)](https://en.wikipedia.org/wiki/Memex) - the original vision this resembles.

## License

MIT License - see [LICENSE](LICENSE) for details.
