# LLM Wiki Agent — Academic Edition

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A coding agent skill, specialized for academic research.** Drop a PDF library into `raw/` and tell the agent to ingest it — the wiki builds itself: source summaries with verbatim citations, concept pages structured as short academic chapters, methodology pages, recommendations grouped by evidence strength, open research questions, and a citation network that connects every paper to what it cites and what cites it.

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

All agents understand natural language and shorthand triggers:

```
ingest raw/papers/my-paper.md              # ingest a markdown source
ingest report.pdf                          # auto-converts to .md, then ingests
ingest slides.pptx notes.docx              # batch, mixed formats
query: what are the main themes?           # synthesize answer from wiki pages
lint                                       # find orphans, contradictions, gaps
build graph                                # build graph.html from all wikilinks
```

Plain English works too:
```
"Ingest this paper: raw/papers/llama2.md"
"What does the wiki say about attention mechanisms?"
"Check for contradictions across sources"
"Build the knowledge graph and tell me the most connected nodes"
```

**Claude Code** also provides `/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/wiki-graph` as slash commands (via `.claude/commands/`). These are Claude Code-specific — other agents use the natural language triggers above, which work identically.

Works with markdown, PDF, DOCX, PPTX, XLSX, HTML, TXT, CSV, JSON, XML, RST, EPUB, and more. Non-markdown files are auto-converted via [markitdown](https://github.com/microsoft/markitdown) at ingest time — no separate step needed.

For PDF-heavy academic libraries, this fork ships a dedicated pipeline (next section).

## Academic Pipeline

End-to-end flow for converting a PDF library into a citation-rigorous wiki.
Each step is idempotent and can be re-run safely.

```
PDF library
   │
   ▼  pdf2md/pdf2md_marker.py     ← high-fidelity Marker conversion
   │  pdf2md/pdf2md_fallback.py   ← pymupdf4llm rescue for PDFs Marker can't handle
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

**Persistent wiki** — structured markdown pages that accumulate across sessions. Unlike chat, nothing is lost.

**Entity pages** — auto-created for every person, company, or project mentioned across sources. Updated each time a new source references them.

**Concept pages** — auto-created for every key idea or framework. Cross-referenced to every source that discusses them.

**Living overview** — `wiki/overview.md` is revised on every ingest to reflect the current synthesis across everything you've read.

**Contradiction flags** — when a new source contradicts an existing claim, it's flagged at ingest time, not buried until query time.

**Knowledge graph** — `graph.html` shows every wiki page as a node, every `[[wikilink]]` as an edge, and Claude-inferred implicit relationships as dotted edges. Community detection clusters related topics.

**Lint reports** — orphan pages, broken links, missing entity pages, data gaps with suggested sources to fill them.

## Use Cases

### Research

Going deep on a topic over weeks — reading papers, articles, reports.

```
/wiki-ingest raw/papers/attention-is-all-you-need.md
/wiki-ingest raw/papers/llama2.md
/wiki-ingest raw/papers/rag-survey.md

# Wiki builds entity pages (Meta AI, Google Brain) and
# concept pages (Attention, RLHF, Context Window) automatically.

/wiki-query "What are the main approaches to reducing hallucination?"
/wiki-query "How has context window size evolved across models?"

/wiki-lint
# → "No sources on mixture-of-experts — consider the Mixtral paper"
```

By the end you have a structured, interlinked reference — not a folder of PDFs you'll never reopen.

---

### Reading a Book

File each chapter as you go. Build out pages for characters, themes, arguments.

```
/wiki-ingest raw/book/chapter-01.md
/wiki-ingest raw/book/chapter-02.md

# Wiki creates entity and theme pages automatically.

/wiki-query "How has the protagonist's motivation evolved?"
/wiki-query "What contradictions exist in the author's argument so far?"

/wiki-graph   # → graph.html shows every character/theme and how they connect
```

Think fan wikis like Tolkien Gateway — built as you read, with the agent doing all the cross-referencing.

---

### Personal Knowledge Base

Track goals, health, habits, self-improvement — file journal entries, articles, podcast notes.

```
/wiki-ingest raw/journal/2026-01-week1.md
/wiki-ingest raw/articles/huberman-sleep-protocol.md
/wiki-ingest raw/articles/atomic-habits-summary.md

/wiki-query "What patterns show up in my journal entries about energy?"
/wiki-query "What habits have I tried and what was the outcome?"
```

The wiki builds a structured picture over time. Concepts like "Sleep", "Exercise", "Deep Work" accumulate evidence from every source filed.

---

### Business / Team Intelligence

Feed in meeting transcripts, project docs, customer calls.

```
/wiki-ingest raw/meetings/q1-planning-transcript.md
/wiki-ingest raw/docs/product-roadmap-2026.md
/wiki-ingest raw/calls/customer-interview-acme.md

/wiki-query "What feature requests have come up most across customer calls?"
/wiki-query "What decisions were made in Q1 and what was the rationale?"

/wiki-lint
# → "Project X mentioned in 5 pages but no dedicated page"
# → "Roadmap contradicts customer interview on priority of feature Y"
```

The wiki stays current because the agent does the maintenance no one wants to do.

---

### Competitive Analysis

Track a company, market, or technology over time.

```
/wiki-ingest raw/competitors/openai-announcements.md
/wiki-ingest raw/market/ai-funding-report-q1.md

/wiki-query "How do OpenAI and Anthropic differ on safety approach?"
/wiki-query "Which companies announced multimodal models in the last 6 months?"
/wiki-query "Competitive landscape summary as of today"
# → agent shows the answer, then asks if you want to save it as a synthesis page
```

## The Graph

Two-pass build:

1. **Deterministic** — parses all `[[wikilinks]]` across wiki pages → edges tagged `EXTRACTED`
2. **Semantic** — agent infers implicit relationships not captured by wikilinks → edges tagged `INFERRED` (with confidence score) or `AMBIGUOUS`

Louvain community detection clusters nodes by topic. SHA256 cache means only changed pages are reprocessed. Output is a self-contained `graph.html` — no server, opens in any browser.

## CLAUDE.md / AGENTS.md

The schema file tells the agent how to maintain the wiki — page formats, ingest/query/lint/graph workflows, naming conventions. This is the key config file. Edit it to customize behavior for your domain.

| Agent | Schema file |
|---|---|
| Claude Code | `CLAUDE.md` |
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

Drop any supported file directly into `ingest` — no separate conversion step needed:

```bash
# These all work — auto-converted at ingest time
ingest report.pdf
ingest meeting-notes.docx
ingest slides.pptx
ingest data.xlsx
ingest page.html
ingest raw/mixed-folder/          # recursively finds all supported files
```

**Supported formats:**
`.md` `.pdf` `.docx` `.pptx` `.xlsx` `.xls` `.html` `.htm` `.txt` `.csv` `.json` `.xml` `.rst` `.rtf` `.epub` `.ipynb` `.yaml` `.yml` `.tsv` `.wav` `.mp3`

Non-markdown files are auto-converted via [markitdown](https://github.com/microsoft/markitdown). Use `--no-convert` to skip auto-conversion and process only `.md` files.

### arXiv Papers (Advanced)

For arXiv papers, use `tools/pdf2md.py` for higher-fidelity conversion:

```bash
python tools/pdf2md.py 2401.12345                      # by arXiv ID
python tools/pdf2md.py https://arxiv.org/abs/2401.12345 # by URL
python tools/pdf2md.py paper.pdf --backend marker       # complex multi-column PDFs
```

Then ingest the resulting `.md`:
```
ingest raw/papers/my-paper.md
```

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

## Related

- [graphify](https://github.com/safishamsi/graphify) — graph-based knowledge extraction skill (inspiration for the graph layer)
- [Vannevar Bush's Memex (1945)](https://en.wikipedia.org/wiki/Memex) — the original vision this resembles

## License

MIT License — see [LICENSE](LICENSE) for details.
