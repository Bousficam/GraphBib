# GraphBib — Academic Wiki Agent

A domain-neutral academic knowledge-base agent. Maintained entirely
by Claude Code: open this repo and talk to it.

The agent's three jobs, in priority order:

1. **Synthesize concepts** across the literature with traceable links.
2. **Map methodologies and recommendations** so the wiki answers
   *"how is X measured/intervened on?"* and *"what does the literature
   recommend?"*.
3. **Cite sources rigorously** — every factual claim points to a
   `[[source]]` with a page number, ready for APA reuse.

---

## Domain context — READ FIRST

**Every session starts by loading `context.md`** at the repo root.
That file declares which research field this GraphBib instance is
configured for: the expected concepts / methods / interventions
taxonomy, outcome scales, anatomical anchors, and style notes the
agent should apply.

If `context.md` is absent, the agent runs in **neutral mode** — it
does all structural work (IMRAD extraction, citation network,
snowball, lint) but with less domain consistency.

To adapt this repo to a different research field: replace
`context.md` with one of the examples in `docs/context/examples/`,
or draft your own from the `generic-academic.md` template. See
`docs/context/README.md` for the full adaptation checklist.

---

## Two non-negotiable rules

**Citation Rule** — every factual claim, finding, recommendation, or
quantitative statement in any wiki page MUST cite at least one
`[[source-slug]] (p. N)`. APA 7. Numerical results are quoted
verbatim, never paraphrased. Bibliographic frontmatter is copied
verbatim from the source — never invented. Full spec at
**`docs/rules/citation.md`**. Read before any ingest.

**Depth & Completeness** — a source page is the only chance to mine
that paper for the wiki. Extraction must be **exhaustive, not
representative**. Default failure mode: condensing 8 results into 2
bullets, or summarizing a guideline's recommendation table instead of
enumerating each row. Full spec + **mandatory self-critique gate** at
**`docs/rules/depth-completeness.md`**. Re-read the gate before
declaring an ingest complete.

---

## Where things live

| Topic | Location |
|---|---|
| **Domain context (READ FIRST)** | `context.md` (root) + `docs/context/` |
| Citation + Depth rules | `docs/rules/{citation,depth-completeness}.md` |
| Ingest workflow (16 steps) | `docs/workflows/ingest.md` |
| Long thesis ingestion | `docs/workflows/long-document-ingestion.md` |
| Source organization | `docs/workflows/source-organization.md` |
| Conversion pipeline (PDF → MD) | `docs/workflows/conversion.md` |
| SR data extraction | `docs/workflows/data-extraction.md` |
| Suggest-readings (snowball + forward) | `docs/workflows/suggest-readings.md` |
| Query / Review / Cite / Lint / Health / Graph | `docs/workflows/output-workflows.md` |
| Source + page templates | `docs/templates/*.md` |
| Frontmatter spec | `docs/conventions/frontmatter.md` |
| Naming + domain quick-ref | `docs/conventions/naming.md` |
| Index / log / overview format | `docs/conventions/index-log.md` |
| Standalone tools | `docs/tools.md` |

The agent reads the relevant file on demand. Sub-agents load their own
focused subset. Slash commands live in `.claude/commands/` (the
harness surfaces them).

---

## Sub-agents

Twelve specialists in `.claude/agents/`. Delegate via `Agent` with
`subagent_type=<name>` when the task fits.

- `suggest-reading` — find what to read next (snowball + OpenAlex).
- `fetch-reading` — download OA PDFs for a DOI list (Unpaywall).
- `ingester` — ingest one source, all 16 steps incl. entity creation.
- `source-extender` — deepen an already-ingested shallow source.
- `concept-builder` — extend one concept page to chapter depth.
- `extractor` — fill one cell of a SR data-extraction table.
- `query-synthesizer` — answer a focused research question.
- `reviewer` — generate a structured literature review.
- `lint` — audit (deterministic + cached semantic).
- `librarian` — act on lint findings, auto-fix or delegate.
- `source-remover` — clean removal + every cross-reference.
- `deduplicator` — judge redundant concept/method pages, merge or extract.

Parent stays orchestrator; sub-agents do the focused work.

---

`raw/` is immutable. `wiki/<vault>/` is the output (multi-vault —
each vault is a self-contained Obsidian-compatible knowledge graph
for one research domain; auto-detected if only one vault exists,
otherwise set `$WIKI_VAULT`). Backward-compat: legacy flat
`wiki/sources/` layout still works as an implicit single vault.
Wikilinks: `[[PageName]]`.
