# Long Document Ingestion (Theses ≥ 100 pages)

A 100–300 page thesis cannot be ingested in a single pass without
losing depth: the agent skims, condenses chapters into bullets, and
the source page is superficial. **Solution: split first, ingest
chapter by chapter, aggregate at thesis level.**

## Step 0 — Split

After the conversion pipeline produces `raw/theses/<slug>.md`, run:

```bash
python pdf2md/split_thesis.py raw/theses/<slug>.md
```

This detects chapter headings (`# Chapter N`, `# N. Title`, named
chapters like Introduction / Methods / Discussion / Conclusion) and
emits one Markdown file per chapter:

```
raw/theses/<slug>.md                            ← parent (untouched)
raw/theses/<slug>/ch01-introduction.md
raw/theses/<slug>/ch02-literature-review.md
raw/theses/<slug>/ch03-methods.md
raw/theses/<slug>/ch04-mi-bci-rct.md
…
raw/theses/<slug>/ch08-general-discussion.md
```

Each chapter file inherits the parent's frontmatter and adds:

- `chapter: <int>`
- `chapter_title: "..."`
- `parent_thesis: <slug>`
- `tags: [..., thesis-chapter]`

If chapter detection fails (no clear headings), edit the parent MD to
add `# Chapter N: Title` markers manually before splitting.

## Step 1 — Ingest the parent

```
ingest raw/theses/<slug>.md
```

Writes `wiki/sources/theses/<slug>/<slug>.md` using the **Thesis
Template** but produces a **lightweight** parent page focused on
thesis-level synthesis. Per-chapter content is intentionally deferred:

- Frontmatter (full bibliographic metadata)
- `## Abstract` (verbatim)
- `## Research Questions`, `## Hypotheses`, `## Theoretical Framework`
- `## Chapters Summary` — one bullet per chapter linking to the
  per-chapter source page (e.g. `[[<slug>-ch04-mi-bci-rct]]`)
- `## Cross-Chapter Synthesis`
- `## Recommendations / Implications` (thesis-level)
- `## Notable References (citation snowball)` — full bibliography
- `## How to Cite`

`## Methods`, `## Results`, `## Background` are **deliberately empty**
on the parent and live on the chapter pages instead.

## Step 2 — Ingest each chapter

```
ingest raw/theses/<slug>/ch01-introduction.md
ingest raw/theses/<slug>/ch02-literature-review.md
…
```

Each chapter is ingested as a regular source. The agent uses the
**Academic Paper Template** (chapters are journal-paper-sized units),
*not* the Thesis Template, with one extra rule:

- The chapter source page's frontmatter must keep `parent_thesis:
  <slug>` and `chapter: N`, and the page should open with a 1-line
  cross-link: *"Chapter N of [[<slug>]]."*
- The Indirect Citation Rule applies normally.
- For an Introduction / Literature Review chapter, the `## Background`
  section will be unusually large (20+ bullets). Apply Knowledge
  Construction from Introductions strictly — every cited claim →
  bullet → routed to the relevant concept pages.
- For empirical chapters, the chapter is treated as one study (own
  Methods, Results, Discussion).

## Step 3 — Aggregate

After all chapters are ingested:

- `tools/update_cited_by.py` rebuilds the citation network across the
  parent and all chapter sub-sources.
- The parent's `## Cross-Chapter Synthesis` may need a manual update
  to integrate findings now that all chapters are in the wiki.

## Why this approach

Benefits: depth preserved (chapter ≈ journal paper), granular
wikilinks (`[[<slug>-ch04-mi-bci-rct]]`), per-chapter `cites:`, the
literature review chapter is fully extracted into concept pages.

## When NOT to split

- Theses < 60 pages: single-pass ingest is fine.
- Cumulative theses (collection of pre-published papers): each paper
  is often already in the wiki as a journal article — the thesis
  itself becomes a thin parent linking to those existing source pages.
