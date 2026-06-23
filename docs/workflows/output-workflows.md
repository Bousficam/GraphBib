# Output Workflows (Query / Review / Cite / Lint / Health / Graph)

Lightweight workflows the agent runs against an already-populated wiki.
For richer execution, each has a dedicated specialist sub-agent.

## Query Workflow

Triggered by: *"query: <question>"* or `/wiki-query`. Sub-agent:
`query-synthesizer`.

1. Read `wiki/index.md` to identify candidate pages.
2. Read those pages with the Read tool.
3. Synthesize an answer with **inline citations as
   `[[source-slug]] (p. N)`** - the Citation Rule applies to query
   answers too.
4. End the answer with an APA bibliography (one entry per cited source,
   pulled from each source page's `citation_apa` field).
5. Ask the user whether to file the answer as
   `wiki/syntheses/<slug>.md`.

## Review Workflow

Triggered by: *"review topic: <topic>"* or `/wiki-review`. Sub-agent:
`reviewer`.

The wiki's headline output: a structured literature review on a topic,
citation-ready.

1. Read `wiki/index.md` and identify all sources tagged with the topic
   (search `tags`, `domain`, and `[[wikilinks]]`).
2. Read those source pages, plus relevant `concepts/`, `methods/`,
   `recommendations/`, `questions/` pages.
3. Produce a structured review with this layout:

   ```markdown
   # <Topic> - Literature Review (YYYY-MM-DD)

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

4. Apply the Citation Rule - *no claim without a source*.
5. Ask the user whether to file as
   `wiki/syntheses/<topic>-review.md`.

## Cite Workflow

Triggered by: *"cite: <topic>"* or `/wiki-cite`.

Returns 3-5 APA-formatted citations from the wiki most relevant to the
topic, with one-sentence relevance rationale per citation. No body,
just references - useful when drafting a paragraph and needing
cite-ready refs.

## Lint Workflow

Triggered by: *"lint the wiki"* or `/wiki-lint`. Sub-agent: `lint`
(deterministic Tier 1 + cached semantic Tier 2). For end-to-end
*"lint then fix"*, use `/wiki-maintain` (delegates to `librarian`).

Use Grep and Read tools to check for:

**Structural / wiki-wide**
- **Orphan pages** - wiki pages with no inbound `[[links]]`.
- **Broken links** - `[[wikilinks]]` pointing to pages that don't
  exist.
- **Missing entity pages** - entities mentioned in 3+ pages but
  lacking their own page.
- **Stale summaries** - pages older than the most recent source they
  cite.

**Academic-specific**
- **Missing DOI** - sources without `doi` (excluding theses, where
  DOI may legitimately be empty if not archived).
- **Missing `citation_apa`** - sources where this field is empty.
- **Uncited claims** - bullets in `## Key Findings`,
  `## Recommendations`, `## Summary` that don't contain `(p. ` - 
  likely uncited.
- **Missing `study_design`** in source frontmatter.
- **Conflicting concept definitions** - same concept defined
  incompatibly across pages (use LLM semantic check).
- **Snowball debt** - references in any thesis's
  `## Notable References` marked ☐ for >30 days.
- **Data gaps** - surface as candidate `[[questions/...]]` pages.

Output a lint report and ask whether to save to `wiki/lint-report.md`.

## Health Workflow

Triggered by: *"health"* or `/wiki-health`.

Run: `python tools/health.py` (or `python tools/health.py --json`).

Fast structural integrity checks - **zero LLM calls**, safe every
session:

- **Empty / stub files** - pages with no content beyond frontmatter.
- **Index sync** - `wiki/index.md` entries vs actual files on disk.
- **Log coverage** - source pages missing a corresponding `ingest`
  entry in `wiki/log.md`.

Output a health report. Use `--save` to write to
`wiki/health-report.md`.

### Health vs Lint Boundary

| Dimension | `health` | `lint` |
|---|---|---|
| **Scope** | Structural integrity | Content quality (incl. citation hygiene) |
| **LLM calls** | Zero | Yes |
| **Cost** | Free | Tokens |
| **Frequency** | Every session | Every 10-15 ingests |
| **Tool** | `tools/health.py` | `tools/lint.py` |
| **Run order** | First | After health passes |

> Run `health` first - linting an empty file wastes tokens.

## Graph Workflow

Triggered by: *"build the knowledge graph"* or `/wiki-graph`.

Run `tools/build_graph.py`:

- Pass 1: parse all `[[wikilinks]]` → deterministic `EXTRACTED` edges.
- Pass 2: infer implicit relationships → `INFERRED` edges with
  confidence.
- Run Louvain community detection.
- Output `graph/graph.json` + `graph/graph.html`.

If Python/dependencies aren't set up, generate the graph data
manually:

1. Use Grep to find all `[[wikilinks]]`.
2. Build a node/edge list, write `graph/graph.json`.
3. Write `graph/graph.html` from the vis.js template.
