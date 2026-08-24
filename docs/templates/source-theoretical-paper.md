# Theoretical / Conceptual Paper Template

Use for sources where the study design is `theoretical`. Detection
cues: paper has no Methods / Results sections (or trivial ones), is
organized around a model / framework / hypothesis, contains few or no
empirical data of its own, primarily proposes definitions or
predictions.

These papers are common foundations for concept pages - they often
introduce or refine the framework that empirical work later tests.
Their value is **conceptual**, so the source page extracts the model
faithfully and the concept pages they touch are heavily enriched.

## Frontmatter

```yaml
---
title: "Theoretical Paper Title"
type: source
tags: [theoretical]
date: YYYY-MM-DD
source_file: raw/<vault>/papers/<slug>.md
authors: [...]
year: 2024
journal: "..."
doi: "..."
source_pdf: "..."

# Theoretical paper metadata
study_design: "theoretical"
framework_proposed: ""               # name of the framework, if any
                                     # (e.g. "Active Inference",
                                     # "NeuralControlTheory")
domain: []
methods: []                          # measurement methods proposed
                                     # for testing the framework
interventions: []
intervention_family: ""

# Quality signals
peer_reviewed: true
preprint: false
language: en
citation_apa: ""
bibtex_key: ""
cites: []
---
```

## Body

```markdown
## Summary
2-4 sentence summary: what framework / model / hypothesis is proposed
and why it matters for the field.

## Introduction

### Background (from cited literature)
The intellectual lineage the paper builds on. Theoretical papers tend
to have very dense Backgrounds (often 20+ bullets - they trace the
problem they're solving through prior work). Apply Indirect Citation
Rule.

### Problem Statement
What the existing theoretical landscape fails to explain or unify.
1-2 sentences.

### Aim of the Paper
What the framework aims to deliver: a new explanation, a unification
of competing theories, a falsifiable prediction set, etc.

## Theoretical Framework

### Core Claims / Postulates
Each claim verbatim with page reference. The framework's "axioms".
- Postulate 1 - (p. ?)
- Postulate 2 - (p. ?)

### Definitions
Each new term defined by the paper, verbatim:
- *"Term X is …"* (p. ?)
- *"Term Y is …"* (p. ?)

These definitions feed the corresponding `[[concepts/...]]` pages
(`## Definitions and Conceptual Boundaries` section).

### Mechanism / Architecture
1-3 paragraphs explaining how the framework works internally:
- What entities it posits.
- What relationships between them.
- What dynamics / processes / equations.
- Diagram or block-structure description if the paper provides one.

### Predictions / Falsifiable Claims
Empirically testable predictions the framework makes:
- Prediction 1 - testable by … (p. ?)
- Prediction 2 - testable by … (p. ?)

These are the most valuable extraction items: they become the
foundation for `[[questions/<slug>]]` pages and for evaluating future
empirical papers.

## Examples / Illustrations

The paper's worked examples or illustrations of the framework.
- Example 1: applied to phenomenon X (this paper p. ?).
- Example 2: applied to phenomenon Y (p. ?).

## Comparison with Existing Frameworks

Apply Indirect Citation Rule for cited frameworks:
- vs [[FrameworkA]] - origin in [[paper-a]] (p. ?), reported via this
  paper (p. ?). The new framework differs by … and aligns by …
- vs [[FrameworkB]] - origin in [[paper-b]] (p. ?), reported via this
  paper (p. ?). …

## Discussion

### Strengths of the Framework
- As acknowledged by authors.

### Limitations / Scope
- Authors' acknowledged scope (where the framework applies / doesn't).
- Empirical phenomena not yet covered.

### Implications for Empirical Research
- What kinds of experiments would test the framework.
- What kinds of methods would be needed.
- Routed to `wiki/questions/<slug>.md`.

### Implications for Practice
- If applicable: clinical implications routed to
  `wiki/recommendations/<topic>.md` (with caveat that theoretical
  recommendations are evidence-light).

## Future Empirical Tests
List explicitly each open empirical test the framework awaits:
- Test 1 - would distinguish this framework from [[FrameworkA]] →
  routed to `wiki/questions/<slug>.md`.
- Test 2 - …

## Reporting Standard Alignment
Theoretical papers do not align with empirical reporting standards.
Note quality indicators where applicable:
- Formal model? Differential equations? Computational implementation?
- Unifies how many existing observations?
- Generates how many novel falsifiable predictions?

## Verbatim Quotes
Minimum 3 quotes covering definitions, predictions, comparison with
prior frameworks.

## Figures

Written at step 18 of the ingest by `tools/figure_pairs.py --markdown`,
which pairs each extracted image with its caption and recovers the page
across both converter conventions. Left out entirely when the source
ships no `<slug>_images/` directory. Full rule:
`docs/workflows/figures.md`.

### Figure N - <first clause of the caption> (p. N)
![Figure N](<relative path emitted by the tool, never counted by hand>)
*Verbatim caption, copied from the converted markdown, never
paraphrased. `*(caption not recovered in the conversion)*` when the OCR
lost it.*

Page reference: `(p. N)` only when it was recovered from the article
itself; `(PDF p. N - confirm the printed page)` when it came from a
marker file name; `(p. ?)` when neither. Never a plausible number.
No citation on a figure here - this page IS the source.

## Cites (in-wiki + snowball candidates)
**Left empty by the ingest**; filled by `/wiki-snowball <slug>`. Theoretical
papers cite a curated set of foundational works densely.
These are high-priority snowball candidates because they form the
intellectual bedrock of the framework.

## Cited By
*(Auto-populated.)*

## Connections
- [[FrameworkName]] - the framework introduced. **Updated heavily**:
  this paper is THE primary source. Populate the framework's concept
  page (`Theoretical Foundations`, `Mechanisms`).
- [[ConceptName]] - concepts redefined or refined by the paper.
- [[methods/...]] - methods proposed for empirical testing.

## Contradictions / Agreements
- Contradicts [[OtherFramework-paper]] on …
- Subsumes / extends [[OtherFramework-paper]] on …

## Extraction Checklist
- [ ] **Background**: 10+ cited claims tracing the intellectual
      lineage with `reported via` provenance.
- [ ] **Problem statement** captured.
- [ ] **All postulates / core claims** listed verbatim with page refs.
- [ ] **All new definitions** captured verbatim and routed to the
      corresponding `[[concepts/...]]` pages.
- [ ] **Mechanism / architecture** described in prose.
- [ ] **All falsifiable predictions** listed (these are the
      framework's testable content).
- [ ] **Worked examples** captured.
- [ ] **Comparison with prior frameworks** uses Indirect Citation
      Rule properly.
- [ ] **Limitations / scope** acknowledged by authors.
- [ ] **Future empirical tests** routed to `wiki/questions/`.
- [ ] **`wiki/concepts/<FrameworkName>.md` populated** with this
      paper as primary source: Overview, Historical Genesis,
      Theoretical Foundations, Mechanisms, Predictions.
- [ ] **Concept pages for redefined terms** updated under
      `## Variants & Definitional Disagreements`.
- [ ] **Recommendations** (if any, with theoretical caveat).

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
