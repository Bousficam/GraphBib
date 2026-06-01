# Narrative Review Template

Use for sources where the study design is `narrative-review`. Detection
cues: no Methods section, no formal search strategy, sub-section
headings are **thematic** (not Methods/Results/Discussion), authors
adopt an opinion or perspective stance.

Narrative reviews are NOT IMRAD. They are organized **thematically**.
Their value is the synthesis and the author's expert framing. They
typically cite 50–200+ works.

The Indirect Citation Rule (`docs/rules/citation.md`) applies
**heavily** — every paragraph synthesizes cited works. The agent should
produce a Background section that exhausts the review's intellectual
content, with each claim attributed to the originating paper.

## Frontmatter

```yaml
---
title: "Review Title"
type: source
tags: [narrative-review]
date: YYYY-MM-DD
source_file: raw/<vault>/papers/<slug>.md
authors: [...]
year: 2024
journal: "..."
doi: "..."
source_pdf: "..."

# Review metadata
study_design: "narrative-review"
prisma_compliant: false               # narrative reviews are not PRISMA
n_works_cited:                        # rough count from References section
date_range: "1990–2023"               # approximate span of cited works
domain: []
methods: []                           # methods discussed
interventions: []
intervention_family: ""
expert_perspective: true              # narrative reviews often advocate
                                      # a position; flag this here

# Quality signals
peer_reviewed: true
preprint: false
language: en
citation_apa: ""
bibtex_key: ""
cites: []                             # populated from References
---
```

## Body

Narrative reviews skip IMRAD. The body is organized by **theme**, with
each theme synthesizing the literature. Adapt section names to the
paper's structure.

```markdown
## Summary
2–4 sentence neutral summary including the review's scope, the author's
perspective, and the headline message.

## Background / Topic Framing
- Why this topic, why now, who is the audience.
- Consensus claims the review takes as starting points (each cited per
  Indirect Citation Rule).

## Themes
For each thematic section in the review, create a `### Theme — <name>`
subsection. Capture:
- The author's framing of the theme.
- The cited evidence supporting the framing — each bullet citing the
  ORIGINAL paper Y, with `reported via this review's section <theme>
  (p. ?)` provenance.
- Disagreements / open issues within the theme.

### Theme 1 — <name>
- Author's framing: 1–2 sentences (this review p. ?).
- Evidence: [[paper-a]] (p. ?), reported via this review (p. ?). [[paper-b]]
  (p. ?), reported via this review. …
- Open issues within this theme: …

### Theme 2 — <name>
…

### Theme N — <name>
…

## Author's Synthesis / Position
Narrative reviews often advocate a perspective. Capture the author's
own claims separately:
- Claim 1 — this review's authors at p. ? (no external attribution —
  this is their original framing).
- Claim 2 — this review at p. ?.

These claims are subject to scrutiny: are they supported by the
evidence presented in `## Themes`? Flag tensions if any.

## Open Issues / Controversies
- Disagreement 1 — reported in this review's discussion (p. ?), with
  protagonists [[paper-x]] vs [[paper-y]].
- Disagreement 2 — see [[questions/<slug>]] (route to a question page).

## Future Research Directions
- Open questions raised → routed to `wiki/questions/<slug>.md`.

## Author's Implications / Recommendations
- Recommendation 1 (p. ?) — routed to `wiki/recommendations/<topic>.md`
  with explicit "narrative review, lower evidence weight" annotation.

## Limitations of the Review
Narrative reviews acknowledge their non-systematic nature. Capture:
- No formal search strategy → potential selection bias.
- Author's perspective explicit/implicit.
- Coverage gaps (decades, regions, sub-populations missed).
- Other limitations as acknowledged.

## Reporting Standard Alignment
- **Standard**: none formal. Note that narrative reviews are NOT
  expected to follow PRISMA. SANRA (Scale for the Assessment of
  Narrative Review Articles) can be used to evaluate quality —
  surface SANRA-relevant items if useful (justification, aim, search
  description, referencing, scientific reasoning, presentation of
  evidence).
- **Deviations** are not really applicable; instead, note the
  positioning (e.g. opinion piece, state-of-the-art, perspective).

## Verbatim Quotes
Minimum 3 quotes from distinct themes/sections.

## Cites (in-wiki + snowball candidates)
For narrative reviews the `cites:` list can be huge (50–200+). Surface
the high-frequency citations (cited multiple times throughout the
review) as priority snowball candidates.

## Cited By
*(Auto-populated.)*

## Connections
- [[ConceptName]] — central concept the review revolves around.
- [[methods/...]] / [[interventions/...]] — methods/treatments
  discussed.
- [[AuthorName]] — author's prior body of work; narrative reviews
  often build on the author's own line of research.

## Contradictions / Agreements
- Contradicts [[OtherReview]] / [[OtherPaper]] on …
- Aligns with [[OtherReview]] / [[OtherPaper]] on …

## Extraction Checklist
- [ ] **Background**: 5+ cited claims with `reported via` provenance.
- [ ] **Themes** identified and named (typically 3–8 in a substantive
      review).
- [ ] **Each theme** has cited evidence (≥ 3 sources) AND a clear
      framing statement.
- [ ] **Author's synthesis / position** distinguished from cited
      evidence.
- [ ] **Open issues / controversies** captured and routed to
      `wiki/questions/`.
- [ ] **Limitations** of the narrative format acknowledged.
- [ ] **No false IMRAD pretense**: do not invent Methods/Results
      subsections that the review does not have.
- [ ] **High-frequency citations** flagged as snowball priorities.
- [ ] **Recommendations** routed with "narrative review" evidence
      tag.
- [ ] **Concept pages** enriched: every theme/claim that touches a
      `[[concept]]` page extends it (Indirect Citation Rule strictly).

## How to Cite
**APA**: <citation_apa>

**BibTeX**:
```bibtex
@article{<bibtex_key>,
  author  = {...},
  title   = {...},
  journal = {...},
  year    = {...},
  doi     = {...}
}
```
```
