# Entity Page Format

People, labs, institutions, instrument vendors. One page per entity, in
`wiki/entities/<EntityName>.md`. The Citation Rule applies — every
biographical or affiliative claim cites a source.

```markdown
---
title: "Entity Name"
type: entity
entity_type: author | institution | lab | tool-vendor | consortium
domain: [stroke, MI-BCI]
tags: []
sources: []                 # auto-populated
last_updated: YYYY-MM-DD
---

## Identity
1-2 lines: who/what, with citation.
*"Maryam Maarek is a postdoctoral researcher at INSERM U1216"*
([[maarek-2024]] p. 1).

## Affiliations
- [[INSERM-U1216]] — postdoc, 2022–present ([[maarek-2024]] p. 1)
- [[OtherLab]] — PhD student, 2018–2021 ([[maarek-2021]] p. iv)

## Contributions to This Wiki
- Concepts developed/refined: [[ConceptName]] (see [[paper-x]] p. ?)
- Methods used or introduced: [[methods/MethodName]]
- Co-authors in this wiki: [[OtherAuthor]], [[ThirdAuthor]]

## Notable Papers in This Wiki
- [[paper-a]] — first author
- [[paper-b]] — co-author
- [[thesis-c]] — supervisor

## Used In This Wiki
*(Auto-populated: list of [[source-slug]] pages citing this entity.)*
```
