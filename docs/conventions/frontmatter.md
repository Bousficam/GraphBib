# Canonical Frontmatter

Every wiki page starts with YAML frontmatter. The base shape is:

```yaml
---
title: "Page Title"
type: source | entity | concept | method | intervention | recommendation | question | synthesis
tags: []
sources: []          # source slugs that inform this page
last_updated: YYYY-MM-DD
---
```

Wikilinks use `[[PageName]]` syntax in body text.

## Type-specific extensions

Each page `type` adds fields on top of the base. The full shape lives
in the corresponding template under `docs/templates/`:

| `type` | Template | Notable extra fields |
|---|---|---|
| `source` | `source-academic-paper.md`, `source-systematic-review.md`, `source-narrative-review.md`, `source-scoping-review.md`, `source-methodological-paper.md`, `source-theoretical-paper.md`, `source-thesis.md`, `source-book.md` | `authors`, `editors`, `journal` *or* `publisher`, `year`, `doi` *or* `isbn`, `study_design`, `n`, `population`, `cites`, `replication_of` |
| `concept` | `concept.md` | `aliases`, `parent_concept`, `domain` |
| `method` | `method.md` | `measures`, `apparatus`, `software` |
| `intervention` | `intervention.md` | `target_outcome`, `dosage`, `population` |
| `recommendation` | `recommendation.md` | `scope`, `strength`, `population` |
| `question` | `question.md` | `status`, `priority` |
| `entity` | `entity.md` | `kind` (person, lab, instrument, dataset) |
| `synthesis` | `overview.md` | `query`, `generated_by` |

## Verbatim rule

Bibliographic frontmatter on source pages (`title`, `authors`,
`journal`, `year`, `doi`, `volume`, `issue`, `pages`) is copied
**verbatim** from the source PDF — never inferred, never reformatted.
This is non-negotiable; see `docs/rules/citation.md`.
