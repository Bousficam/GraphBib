# Concept Page Format

Concept pages are the **synthesis layer** — where the wiki builds beyond
individual sources. Each concept page is structured as a **short academic
book chapter**, not a wiki stub: narrative prose grounded in citations,
self-contained enough that a reader can learn the topic from the page
alone.

**Target depth**: 1,500–3,500 words per concept (3–7 pages of prose). Use
prose paragraphs for narrative sections (Overview, Historical Genesis,
Theoretical Foundations, Mechanisms, Clinical Relevance) and bulleted
lists only for inventories (Operationalization, Seminal Papers, Related
Concepts). The Citation Rule (`docs/rules/citation.md`) applies
throughout — every factual claim points to a `[[source]] (p. N)`.

Use this template for `wiki/concepts/<ConceptName>.md`.

```markdown
---
title: "Concept Name"
type: concept
aka: ["alias 1", "alias 2"]
domain: [stroke, motor-control]
tags: []
sources: []                 # auto-populated: sources that mention this concept
last_updated: YYYY-MM-DD
---

## Overview
One paragraph (4–6 sentences) introducing the concept: what it names, why
it matters in this wiki's domain, and how it sits in the broader landscape.
This is the abstract a reader should hit first. Every claim cites a source.

## Historical Genesis
Two or three short paragraphs tracing where the concept came from: the
first formulation, the school of thought, the empirical or theoretical
moment that brought it into use. Identify the seminal author(s) and their
context. Distinguish "first use of the term" from "first instantiation
of the underlying idea" if the literature does (see [[paper-a]] p. ?,
[[paper-b]] p. ?).

## Definitions and Conceptual Boundaries
Open with the consensual modern definition, quoted verbatim:
*"Motor imagery is the mental simulation of a movement without overt
execution"* ([[decety-1996]] p. 88, [[jeannerod-2001]] p. 110).

Then a paragraph mapping the **variants** across schools / sub-fields,
each with citation:
- [[paper-a]] (p. ?) defines it as ... — emphasis on X.
- [[paper-b]] (p. ?) restricts it to ... — excludes Y.
- Disagreement axes: scope | mechanism | measurability | first-vs-third
  person | conscious-vs-implicit.

Close with the **conceptual neighbors** and how the boundary is drawn:
- [[CloseConceptA]] — overlap; boundary discussed in [[paper-z]] (p. ?).
- [[CloseConceptB]] — distinct mechanism per [[paper-w]] (p. ?).

## Theoretical Foundations
Several paragraphs (one per framework) presenting the theoretical
backbones the concept rests on. For each framework: what it proposes,
who proposed it, and what empirical support exists.

- [[NeuralControlTheory]] — origin in [[paper-x]] (p. ?). Predicts that
  the concept manifests as ... Empirical support: [[paper-a]] (p. ?),
  [[paper-b]] (p. ?). Limitations: [[paper-c]] (p. ?).
- Competing framework: [[OtherFramework]] from [[paper-y]] (p. ?).
  Difference with the above: ... Empirical support: ... .

## Mechanisms
Functional, neural, or cognitive mechanisms by which the concept operates.
Use sub-headings per mechanism. Prose paragraphs, citation-dense.

### Mechanism 1 — <name>
Description with citations ([[paper-a]] p. ?, [[paper-b]] p. ?). Where
applicable, link to the brain regions / pathways involved (e.g.
[[CorticospinalTract]], [[M1]], [[PremotorCortex]]).

### Mechanism 2 — <name>
...

## Operationalization & Measurement
How the concept is measured in the literature. Group by modality, link
each instrument to its [[methods/...]] page.

- **Subjective measures**: [[methods/KVIQ]], [[methods/MIQ-RS]] — used
  in [[paper-a]] (p. ?), [[paper-b]] (p. ?).
- **Behavioral**: [[methods/MentalChronometry]] — see [[paper-c]] (p. ?).
- **Neurophysiological**: [[methods/EEG-ERD]], [[methods/fMRI-BOLD]] —
  see [[paper-d]] (p. ?), [[paper-e]] (p. ?).
- **Neuroimaging**: [[methods/DTI]] — see [[paper-f]] (p. ?).

## Empirical Evidence
Summarize what the literature has shown about the concept. Group by
sub-claim, **each with sources**, indicating strength and consistency.

### Sub-claim 1 — <statement>
Supported by [[paper-a]] (p. ?, N=...), [[paper-b]] (p. ?, N=...).
Replicated in [[paper-c]] (p. ?). Effect size: <quote verbatim if
reported>.

### Sub-claim 2 — <statement>
Mixed: [[paper-d]] (p. ?) finds X; [[paper-e]] (p. ?) does not. See
[[questions/<slug>]] for the open debate.

## Clinical / Applied Relevance
One or two paragraphs on why the concept matters in practice. In our
domain, focus on stroke motor rehabilitation: how the concept informs
intervention design, prognosis, or assessment. Link to relevant
[[recommendations/...]] pages.

## Controversies & Open Debates
Each debate gets a short paragraph and links to a [[questions/...]] page.
- Debate 1: ... — see [[questions/<slug>]].
- Debate 2: ... — see [[questions/<slug>]].

## Seminal & Key References (chronological)
A short annotated reading list — not exhaustive, just the spine. One
sentence per entry explaining the contribution.

- 1996 — [[decety-1996]]: first formulation in stroke context (p. ?).
- 2001 — [[jeannerod-2001]]: theoretical consolidation (p. ?).
- 2014 — [[zimmermann-2014]]: extension to BCI training (p. ?).
- 2020 — [[cervera-2020]]: meta-analysis confirming clinical effect (p. ?).

## Related Concepts
- [[CloseConceptA]] — relation: overlap | extension | precondition.
- [[CloseConceptB]] — relation.

## Used In This Wiki
*(Auto-populated: list of [[source-slug]] pages tagged with this concept,
grouped by sub-claim or theme when possible.)*
```

## How concept pages grow over time

A concept page is **incrementally enriched** at each ingest (step 7 of
the Ingest Workflow). When a new source touches the concept:

- If the source provides a *new variant of the definition* → add to
  `## Definitions and Conceptual Boundaries`.
- If it offers *new empirical evidence* → add a sub-claim or refine an
  existing one in `## Empirical Evidence`.
- If it introduces a *new framework* → add to `## Theoretical Foundations`.
- If it raises a *new debate* → add to `## Controversies & Open Debates`
  and create the matching `[[questions/...]]` page.
- If it uses a *new measurement instrument* → add to `## Operationalization`
  and ensure the `[[methods/...]]` page exists.

Update `last_updated` and append the source slug to `sources:`.

## Stub-vs-chapter rule

A new concept page may be created as a stub (Overview + Definitions only)
when it first appears in an ingest, but the agent should flag it in the
post-ingest summary as *"stub — needs expansion"*. After 3+ sources have
touched the concept, the page should be expanded toward chapter depth.
