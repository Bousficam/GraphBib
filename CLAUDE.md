# GraphBib - Academic Wiki Agent

A domain-neutral academic knowledge-base agent. Maintained entirely
by Claude Code: open this repo and talk to it.

The agent's three jobs, in priority order:

1. **Synthesize concepts** across the literature with traceable links.
2. **Map methodologies and recommendations** so the wiki answers
   *"how is X measured/intervened on?"* and *"what does the literature
   recommend?"*.
3. **Cite sources rigorously** - every factual claim points to a
   `[[source]]` with a page number, ready for APA reuse.

---

## Domain context - READ FIRST

**Every session starts by loading `context.md`** at the repo root.
That file declares which research field this GraphBib instance is
configured for: the expected concepts / methods / interventions
taxonomy, outcome scales, anatomical anchors, and style notes the
agent should apply.

If `context.md` is absent, the agent runs in **neutral mode** - it
does all structural work (IMRAD extraction, citation network,
snowball, lint) but with less domain consistency.

The repo ships **neutral by default**: `context.md` is the
`generic-academic` baseline, and the analyzer tools read their
field-specific vocabulary from `tools/data/domain.json` (also shipped
empty). To adapt this repo to a research field: replace `context.md`
with one of the examples in `docs/context/examples/` (or draft your own
from `generic-academic.md`), and fill / copy a pack into
`tools/data/domain.json` (e.g. `tools/data/domain.stroke.example.json`).
See `docs/context/README.md` for the full adaptation checklist and
`docs/tools.md` > "Domain configuration" for the `domain.json` schema.

---

## Non-negotiable rules

**Citation Rule** - every factual claim, finding, recommendation, or
quantitative statement in any wiki page MUST cite at least one
`[[source-slug]] (p. N)`. APA 7. Numerical results are quoted
verbatim, never paraphrased. Bibliographic frontmatter is copied
verbatim from the source - never invented. Full spec at
**`docs/rules/citation.md`**. Read before any ingest.

**Every result is checked against the article** - an ingest ends with
`python tools/verify_ingest.py --source <slug>`. Every numeric claim
written during the session must be cited with a page, resolve to a real
page, and be **present in the ingested article**. A number the article
does not print is either corrected, removed, or explicitly marked as
derived / read-off-a-figure / lost-in-conversion. See step 19 of
`docs/workflows/ingest.md`.

**The DOI is verified against Crossref** - an ingest then runs
`python tools/verify_doi.py --source <slug>`. Not "does the DOI
resolve" but "does Crossref return THIS paper": title, first author,
year, journal. A converter that picked up the DOI of one of the paper's
own references produces a page whose every APA citation is wrong. See
step 20 of `docs/workflows/ingest.md`.

**Two things an ingest never does** - it never reads the reference list
or the abbreviation list of a paper (they carry no claim and eat the
context window), and it never runs a citation snowball. Snowball is a
standalone workflow: `/wiki-snowball`, `docs/workflows/snowball.md`.

**Depth & Completeness** - a source page is the only chance to mine
that paper for the wiki. Extraction must be **exhaustive, not
representative**. Default failure mode: condensing 8 results into 2
bullets, or summarizing a guideline's recommendation table instead of
enumerating each row. Full spec + **mandatory self-critique gate** at
**`docs/rules/depth-completeness.md`**. Re-read the gate before
declaring an ingest complete.

---

## House style

**No em dash or en dash.** Never emit the em dash (U+2014, the
"cadratin") or the en dash (U+2013) in any output - wiki pages,
reports, commit messages, docstrings. Use a spaced hyphen ` - ` in
place of an em dash, and a plain hyphen `-` in place of an en dash
(so ranges stay tight, e.g. `10-20`), or restructure the sentence.
This binds every agent. Auditing agents (`lint`, `librarian`) must
also detect and fix stray dashes: `lint` flags them (deterministic
check `em_dash`), `librarian` fixes them by running
`python tools/strip_em_dash.py`. The only exception is regex source
that must MATCH dashes in the immutable `raw/` corpus - there, write
the dash as a backslash-u escape (`\uXXXX`: em dash is U+2014, en dash
U+2013) rather than a literal dash character.

---

## Where things live

| Topic | Location |
|---|---|
| **Domain context (READ FIRST)** | `context.md` (root) + `docs/context/` |
| Citation + Depth rules | `docs/rules/{citation,depth-completeness}.md` |
| Ingest workflow (20 steps) | `docs/workflows/ingest.md` |
| Long thesis ingestion | `docs/workflows/long-document-ingestion.md` |
| Source organization | `docs/workflows/source-organization.md` |
| Conversion pipeline (PDF → MD) | `docs/workflows/conversion.md` |
| Citation snowball (standalone, NOT part of ingest) | `docs/workflows/snowball.md` |
| Suggest-readings (internal + forward) | `docs/workflows/suggest-readings.md` |
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

Thirteen specialists in `.claude/agents/`. Delegate via `Agent` with
`subagent_type=<name>` when the task fits.

**Wiki side** - knowledge-graph building / maintenance:
- `suggest-reading` - find what to read next (snowball + OpenAlex).
- `fetch-reading` - download OA PDFs for a DOI list (Unpaywall).
- `ingester` - ingest one source, all 20 steps (entity pages OFF by
  default; bibliography and abbreviation lists never read; no snowball;
  ends on two lints - `verify_ingest` for claims, `verify_doi` for the
  DOI).
- `source-extender` - deepen an already-ingested shallow source.
- `source-illustrator` - populate `## Figures` on one source page
  from images already extracted by `pdf2md_marker.py`.
- `concept-builder` - extend one concept page to chapter depth.
- `concept-illustrator` - insert relevant figures into one concept
  page, sourced from its cited sources' `## Figures` sections.
- `query-synthesizer` - answer a focused research question.
- `reviewer` - generate a structured literature review.
- `lint` - audit (deterministic + cached semantic).
- `librarian` - act on lint findings, auto-fix or delegate.
- `source-remover` - clean removal + every cross-reference.
- `deduplicator` - judge redundant concept/method pages, merge or extract.

The extractor/screening agent (PRISMA screening + SR data extraction,
formerly `project-review/` + `screener-tiab` / `screener-fulltext` /
`extractor`) now lives in the sibling repo `../TallyBib/`.

Parent stays orchestrator; sub-agents do the focused work.

---

`raw/<vault>/` is immutable (raw inputs for the vault).
`wiki/<vault>/` is the ingested output. Both are multi-vault - each
vault is a self-contained Obsidian-compatible knowledge graph for
one research domain. They share the SAME vault name (raw is input,
wiki is output of the same domain) and are resolved via the same
`$WIKI_VAULT` env var (auto-detected when a single vault exists).
Backward-compat: legacy flat `wiki/sources/` + `raw/papers/` layouts
still work as an implicit single vault. Wikilinks: `[[PageName]]`.

**Vault selection at session start.** When the repo holds ≥2 vaults
and `$WIKI_VAULT` is unset, the `SessionStart` hook
(`.claude/hooks/session_start_vault.py`) injects a notice listing the
available vaults. Before running any wiki tool or `/wiki-*` command,
ASK the user which vault to use, then persist the choice for the
session by merging `{"env": {"WIKI_VAULT": "<choice>"}}` into
`.claude/settings.local.json` (preserve the existing `permissions`
block). This avoids re-asking on every tool call and is inherited by
sub-agents.

The `project-review/<vault>/<name>/` orchestrator has moved to the
sibling repo `../TallyBib/` and is independent of this wiki - it is
NOT created or read by `/wiki-init`. Sharing a vault name between
`wiki/<vault>/` here and `project-review/<vault>/` in TallyBib is
allowed and useful for the same research domain, but never enforced -
`$WIKI_VAULT` (this repo) and `$PROJECT_VAULT` (TallyBib) are
deliberately separate env vars in separate repos.
