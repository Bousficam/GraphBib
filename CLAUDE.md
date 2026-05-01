# LLM Wiki Agent — Academic Edition

This wiki is an **academic knowledge base** for research on **stroke motor
rehabilitation via MI-BCI and TMS**, grounded in neural control theory and
white-matter anatomy (DTI). It is maintained entirely by Claude Code: open
this repo in Claude Code and talk to it.

The agent's three jobs, in priority order:

1. **Synthesize concepts** across the literature with traceable links.
2. **Map methodologies and recommendations** so the wiki answers *"how is X
   measured/intervened on?"* and *"what does the literature recommend?"*.
3. **Cite sources rigorously** — every factual claim points to a `[[source]]`
   with a page number, ready for APA reuse.

---

## Slash Commands (Claude Code)

| Command | What to say |
|---|---|
| `/wiki-ingest` | `ingest raw/papers/<file>.md` |
| `/wiki-query` | `query: what does the literature say about MI-BCI for chronic stroke?` |
| `/wiki-review` | `review topic: corticospinal integrity and motor recovery` |
| `/wiki-cite` | `cite: TMS-induced plasticity in M1` (returns 3-5 APA refs) |
| `/wiki-health` | `health` (fast, every session) |
| `/wiki-lint` | `lint the wiki` (expensive, periodic) |
| `/wiki-graph` | `build the knowledge graph` |

Plain English works too — describe what you want and Claude maps it to the
right workflow:

- *"Ingest this thesis: raw/theses/dupont-2023.md"*
- *"What methods are used to assess corticospinal tract integrity?"*
- *"Build a literature review on motor imagery training in chronic stroke"*
- *"Show me the open questions around TMS dose-response"*

Claude Code reads this file automatically and follows the workflows below.

---

## Directory Layout

```
raw/                  # Immutable source documents — never modify these
  papers/             # Journal articles (kebab-case.md, one per article)
  theses/             # PhD/MSc theses (kebab-case.md)
  notes/              # Personal notes, conference talks, lab reports
wiki/                 # Claude owns this layer entirely
  index.md            # Catalog of all pages — updated on every ingest
  log.md              # Append-only chronological record
  overview.md         # Living synthesis across all sources
  sources/            # One summary page per ingested source
  entities/           # People, labs, institutions, instrument vendors
  concepts/           # Theoretical concepts (e.g. MotorImagery, Neuroplasticity)
  methods/            # Methodologies & instruments (e.g. EEG, TMS, DTI, FuglMeyer)
  recommendations/    # Synthesized clinical/research recommendations by topic
  questions/          # Open research questions identified across the literature
  syntheses/          # Saved query answers and literature reviews
graph/                # Auto-generated graph data
tools/                # Standalone Python scripts (health.py, lint.py, etc.)
pdf2md/               # PDF -> Markdown conversion pipeline (marker + fallback + enrich)
```

---

## Citation Rule (Global)

**Every factual claim, finding, recommendation, or quantitative statement in
any wiki page MUST cite at least one `[[source-slug]] (p. N)`.**

- If the page number is unknown, write `(p. ?)` — do not omit the citation.
- Never paraphrase numerical results, p-values, or effect sizes — quote them
  verbatim with page reference.
- If a claim is the agent's synthesis across multiple sources, list all of
  them: `(see [[paper-a]] p. 12, [[paper-b]] p. 4)`.
- **Entity pages**: every biographical, affiliative, or institutional
  statement cites a source with page number, exactly like factual claims
  in source pages.
- **Overview**: every cross-source claim under `## Key Findings (synthesized)`
  cites the relevant sources. Pure scope/meta sentences need no citation.
- **Bibliographic fields rule**: `title`, `authors`, `journal`, `year`, `doi`,
  `source_pdf` MUST be copied verbatim from the source frontmatter. Never
  infer, translate, normalize, or invent values. Leave fields empty if
  missing in the source.
- **Default citation style**: APA 7th edition. Generated `citation_apa` and
  `bibtex_key` fields are stored in each source page's frontmatter and
  rendered in the `## How to Cite` section.

---

## Page Format (Canonical Frontmatter)

Every wiki page starts with this frontmatter:

```yaml
---
title: "Page Title"
type: source | entity | concept | method | recommendation | question | synthesis
tags: []
sources: []          # list of source slugs that inform this page
last_updated: YYYY-MM-DD
---
```

Use `[[PageName]]` wikilinks to link to other wiki pages. Sub-typed pages
(source, method, etc.) extend this base with type-specific fields, defined
below.

---

## Ingest Workflow

Triggered by: *"ingest <file>"* or `/wiki-ingest`.

**Supported formats** — Markdown (`.md`) ingested directly. Non-markdown files
auto-converted to Markdown beforehand:
- **PDFs (papers, theses)** -> use `pdf2md/pdf2md_marker.py` (marker-pdf,
  with `pdf2md/pdf2md_fallback.py` for PDFs marker can't handle), then
  `pdf2md/enrich_frontmatter.py` to populate bibliographic metadata via
  Crossref.
- **Other formats** (`.docx`, `.pptx`, `.xlsx`, `.html`, `.txt`, ...) -> markitdown.

Steps (in order):

1. **Read the source** fully via the Read tool (auto-convert if non-markdown).
2. **Read context**: `wiki/index.md`, `wiki/overview.md`, plus any obviously
   related concept/method pages already in the wiki.
3. **Choose the source template** based on path and type:
   - `raw/papers/*` -> Academic Paper Template
   - `raw/theses/*` -> Thesis Template
   - `raw/notes/*`  -> Generic Source Template (or Diary/Meeting if applicable)
4. **Generate `citation_apa` and `bibtex_key`** from the frontmatter
   (`authors`, `year`, `title`, `journal` or `university`, `doi`). Use APA 7.
5. **Write `wiki/sources/<slug>.md`** using the chosen template. Apply the
   Citation Rule strictly.
6. **Update entity pages** for each author and institution.
7. **Update concept pages** for each key concept discussed; for each, link
   operationalizations to the relevant `[[methods/...]]` pages.
8. **Update method pages**: for each method listed in the source's
   `methods:` frontmatter, ensure `wiki/methods/<MethodName>.md` exists,
   and add this source under its `## Used In This Wiki` section.
9. **Update recommendation pages**: if the source proposes recommendations,
   route them to the relevant `wiki/recommendations/<topic>.md` (create if
   needed) under the appropriate evidence-strength section.
10. **Update question pages**: if the source identifies an open question or
    explicit gap, append to `wiki/questions/<slug>.md` (create if needed).
11. **Flag contradictions** with existing wiki content explicitly, with page
    numbers on both sides.
12. **Update `wiki/index.md`** — add entries under all touched sections.
13. **Update `wiki/overview.md`** if the synthesis warrants revision.
14. **Append to `wiki/log.md`**: `## [YYYY-MM-DD] ingest | <Title>`.
15. **Post-ingest validation** — check broken `[[wikilinks]]`, verify all new
    pages are in `index.md`, print a change summary including counts:
    *N concepts updated, M methods touched, K recommendations refined*.

### For theses specifically — citation snowball

Theses are dense citation hubs. After ingesting a thesis:

- **Surface high-value references** in the `## Notable References` section
  of the source page (10-30 references the thesis builds on heavily).
- **Suggest snowball ingestion**: at the end of the post-ingest summary,
  list the references *not yet in the wiki* and ask the user whether to
  ingest them next. Do not auto-ingest.

---

## Source Templates

### Academic Paper Template (default for `raw/papers/*`)

````markdown
---
title: "Paper Title"
type: source
tags: [paper]
date: YYYY-MM-DD            # ingest date
source_file: raw/papers/<slug>.md
authors: ["First Last", "First Last"]
year: 2024
journal: "Journal Name"
doi: "10.xxxx/xxxxx"
source_pdf: "/abs/path/to/original.pdf"

# Study metadata
study_design: ""            # RCT | cohort | cross-sectional | review |
                            # meta-analysis | case-series | case-report |
                            # simulation | computational | theoretical
sample_size:                # integer N (or empty)
population: ""              # e.g. "chronic stroke patients (>6 months post-onset)"
domain: []                  # e.g. [stroke, motor-rehab, MI-BCI]
methods: []                 # e.g. [EEG, MI-BCI, FuglMeyer, ARAT, TMS, DTI]

# Quality signals
peer_reviewed: true
preprint: false
language: en
replication_of: ""          # DOI of the replicated paper, if applicable

# Citation (auto-generated, copyable)
citation_apa: ""
bibtex_key: ""              # e.g. cervera2020
---

## Summary
2-4 sentence neutral summary. **Every claim cites a page**.

## Research Question
Single sentence — the question the paper explicitly addresses.

## Methods
- **Design**: <study_design>
- **Participants**: N=<sample_size>, profile (p. ?)
- **Procedure**: brief steps
- **Measures**: variables -> instruments -> [[methods/MethodName]]
- **Analysis**: statistical approach

## Key Findings
- Finding 1, with effect size and statistic if reported (p. ?)
- Finding 2 (p. ?)

## Recommendations / Implications
- Recommendation 1 (p. ?) — target: [clinician | researcher | policy]
- Implication for theory of [[ConceptName]] (p. ?)

## Limitations
- Limitation 1 — as acknowledged by the authors (p. ?)
- Limitation 2 (p. ?)

## Verbatim Quotes
> "Quote here verbatim" — p. N

## Connections
- [[AuthorName]] — author
- [[ConceptName]] — central concept; how this paper uses it
- [[methods/MethodName]] — operationalization used
- [[OtherPaper]] — builds on / contradicts / extends

## Contradictions / Agreements
- Contradicts [[OtherPaper]] on: claim X (this p. ?, other p. ?)
- Confirms [[OtherPaper]] on: claim Y (this p. ?, other p. ?)

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
````

### Thesis Template (default for `raw/theses/*`)

Theses have richer metadata, multiple chapters, and serve as citation
snowball sources.

````markdown
---
title: "Thesis Title"
type: source
tags: [thesis, paper]
date: YYYY-MM-DD            # ingest date
source_file: raw/theses/<slug>.md
authors: ["First Last"]
year: 2024
degree: "PhD"               # PhD | MSc | MD | HDR | habilitation
university: "University Name"
department: ""
advisors: ["First Last"]
defense_date: YYYY-MM-DD
journal: ""                 # empty for theses
doi: ""                     # if archived (HAL, ProQuest, theses.fr)
source_pdf: "/abs/path/to/original.pdf"

# Study metadata (often multi-method across chapters)
study_design: "thesis"
sample_size:                # total N across studies, or empty
population: ""
domain: []
methods: []                 # union of methods across chapters

# Quality signals
peer_reviewed: false        # committee-reviewed, not peer-reviewed
preprint: false
language: en
chapters: 0                 # integer

# Citation
citation_apa: ""
bibtex_key: ""
---

## Abstract
Verbatim abstract from the thesis frontmatter.

## Research Questions
- RQ1: ... (p. ?)
- RQ2: ... (p. ?)

## Hypotheses
- H1: ... (p. ?)

## Theoretical Framework
- Anchored in [[ConceptName]] — how the thesis builds on it (p. ?)
- Contributes to [[FrameworkName]]

## Chapters Summary

### Chapter X — <title> (p. NN-NN)
- **Design**: ...
- **Methods**: -> [[methods/...]]
- **Key findings**: ... (p. ?)

## Cross-Chapter Synthesis
The thesis's overall argument, integrating chapters (p. ?).

## Recommendations / Implications
- For clinical practice: ... (p. ?)
- For future research: ... (p. ?)

## Limitations
- ... (p. ?)

## Notable References (citation snowball)
High-value references this thesis builds on. Format:
- *Author, A. (Year).* Title. *Journal*, V(I), pp. — relevance
- ☐ not yet in wiki
- ✓ [[already-ingested-slug]]

After ingest, surface the ☐ items and ask the user about snowball ingestion.

## Verbatim Quotes
> "..." — p. N

## Connections
- [[AdvisorName]] — advisor
- [[ConceptName]] — central concept
- [[methods/MethodName]] — used technique

## Contradictions / Agreements
- ...

## How to Cite
**APA**: <citation_apa>

**BibTeX**:
```bibtex
@phdthesis{<bibtex_key>,
  author       = {...},
  title        = {...},
  school       = {...},
  year         = {...},
  type         = {PhD thesis},
  doi          = {...}
}
```
````

### Generic Source Template (for `raw/notes/*`, fallback)

Use the same shape as Academic Paper, omitting fields that don't apply
(no `study_design`, no `peer_reviewed`, no `journal`).

### Diary / Meeting Templates

Kept available for non-academic notes mixed into `raw/notes/`. See the
**Domain-Specific Templates** section at the end of this file.

---

## Concept Page Format

Concept pages are the **synthesis layer** — where the wiki builds beyond
individual sources. Each concept page is structured as a **short academic
book chapter**, not a wiki stub: narrative prose grounded in citations,
self-contained enough that a reader can learn the topic from the page
alone.

**Target depth**: 1,500–3,500 words per concept (3–7 pages of prose). Use
prose paragraphs for narrative sections (Overview, Historical Genesis,
Theoretical Foundations, Mechanisms, Clinical Relevance) and bulleted
lists only for inventories (Operationalization, Seminal Papers, Related
Concepts). The Citation Rule applies throughout — every factual claim
points to a `[[source]] (p. N)`.

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

### How concept pages grow over time

A concept page is **incrementally enriched** at each ingest (step 7 of the
ingest workflow). When a new source touches the concept:

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

### Stub-vs-chapter rule

A new concept page may be created as a stub (Overview + Definitions only)
when it first appears in an ingest, but the agent should flag it in the
post-ingest summary as *"stub — needs expansion"*. After 3+ sources have
touched the concept, the page should be expanded toward chapter depth.

---

## Method Page Format

A method page documents an instrument, scale, technique, or analysis
pipeline. One page per method, in `wiki/methods/<MethodName>.md`.

```markdown
---
title: "EEG (Electroencephalography)"
type: method
aka: ["electroencephalography"]
category: "neurophysiology"     # imaging | neurophysiology | behavioral |
                                # subjective-scale | stimulation | analysis
measures: ["cortical activity", "alertness", "ERD/ERS"]
strengths: ["high temporal resolution", "non-invasive", "low cost"]
limitations: ["low spatial resolution", "muscle/eye artifacts"]
domain: [neurophysiology, BCI]
tags: []
sources: []                     # auto-populated
last_updated: YYYY-MM-DD
---

## Definition
1-2 sentences with citation:
*"EEG records ..."* ([[paper-x]] p. ?).

## When to Use It
- Use case 1 — established in [[paper-a]] (p. ?), [[paper-b]] (p. ?).
- Use case 2 — emerging, see [[paper-c]] (p. ?).

## Best Practices
Synthesized recommendations across the wiki's sources:
- Practice 1 — consensus across [[paper-a]], [[paper-b]] (p. ? each).
- Practice 2 — [[paper-c]] recommends ... (p. ?), but [[paper-d]] disagrees (p. ?).

## Common Pitfalls
- Pitfall 1 — flagged by [[paper-x]] (p. ?).

## Variants / Sub-Methods
- Variant A -> [[methods/EEG-ERD]]
- Variant B -> [[methods/EEG-SSVEP]]

## Used In This Wiki
*(Auto-populated: [[source-slug]] entries that report using this method.)*
```

---

## Recommendation Page Format

One page per topic, grouped by **strength of evidence**. Drop into
`wiki/recommendations/<topic-slug>.md`.

```markdown
---
title: "Recommendations: <Topic>"
type: recommendation
domain: [stroke, MI-BCI]
tags: []
sources: []                     # auto-populated
last_updated: YYYY-MM-DD
---

## Strong Evidence (>=3 sources, replicated, including >=1 RCT or meta-analysis)
- Recommendation 1 — sources: [[paper-a]] (p. ?), [[paper-b]] (p. ?),
  [[cervera-2020]] meta-analysis (p. ?).
- ...

## Moderate Evidence (1-2 RCTs or several non-randomized studies)
- Recommendation 2 — source: [[paper-d]] (p. ?). Not yet replicated.
- ...

## Conflicting Evidence
- Position A: [[paper-e]] (p. ?) recommends X.
- Position B: [[paper-f]] (p. ?) recommends not-X.
- Open question -> see [[questions/<slug>]].

## Practical Notes
Actionable details (dose, duration, timing post-stroke, contraindications).

## Related Recommendations
- [[recommendations/<other-topic>]]
```

---

## Question Page Format

Captures gaps and open research questions identified across the literature.
One page per question, in `wiki/questions/<slug>.md`.

```markdown
---
title: "Open Question: <one-line question>"
type: question
status: "open"                  # open | partially-answered | resolved
raised_by: [[source-slug]]      # source(s) that explicitly raise it
domain: [stroke, MI-BCI]
tags: []
last_updated: YYYY-MM-DD
---

## The Gap
1-3 sentences stating what is unknown.

## Why It Matters
Clinical, theoretical, or methodological stakes.

## What's Known
- [[paper-a]] (p. ?) shows ...
- [[paper-b]] (p. ?) suggests ...

## What's Missing
- Specific evidence type missing (e.g., long-term follow-up RCT).
- Specific population missing (e.g., subacute stroke).

## Suggested Studies
- Design 1 that would close the gap.
- Design 2.

## Connections
- Concerns [[ConceptName]].
- Would test [[FrameworkName]].
- Methodology candidate: [[methods/...]].
```

---

## Entity Page Format

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

---

## Query Workflow

Triggered by: *"query: <question>"* or `/wiki-query`.

Steps:
1. Read `wiki/index.md` to identify candidate pages.
2. Read those pages with the Read tool.
3. Synthesize an answer with **inline citations as `[[source-slug]] (p. N)`** —
   the Citation Rule applies to query answers too.
4. End the answer with an APA bibliography (one entry per cited source,
   pulled from each source page's `citation_apa` field).
5. Ask the user whether to file the answer as `wiki/syntheses/<slug>.md`.

---

## Review Workflow

Triggered by: *"review topic: <topic>"* or `/wiki-review`.

This is the wiki's headline output: a structured literature review on a
topic, citation-ready.

Steps:
1. Read `wiki/index.md` and identify all sources tagged with the topic
   (search `tags`, `domain`, and `[[wikilinks]]`).
2. Read those source pages, plus relevant `concepts/`, `methods/`,
   `recommendations/`, and `questions/` pages.
3. Produce a structured review with this layout:

   ```markdown
   # <Topic> — Literature Review (YYYY-MM-DD)

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

4. Apply the Citation Rule — *no claim without a source*.
5. Ask the user whether to file as `wiki/syntheses/<topic>-review.md`.

---

## Cite Workflow

Triggered by: *"cite: <topic>"* or `/wiki-cite`.

Returns 3-5 APA-formatted citations from the wiki most relevant to the
topic, with one-sentence relevance rationale per citation. No body, just
references — useful when drafting a paragraph and needing cite-ready refs.

---

## Lint Workflow

Triggered by: *"lint the wiki"* or `/wiki-lint`.

Use Grep and Read tools to check for:

**Structural / wiki-wide**
- **Orphan pages** — wiki pages with no inbound `[[links]]`.
- **Broken links** — `[[wikilinks]]` pointing to pages that don't exist.
- **Missing entity pages** — entities mentioned in 3+ pages but lacking
  their own page.
- **Stale summaries** — pages older than the most recent source they cite.

**Academic-specific**
- **Missing DOI** — sources without `doi` (excluding theses, where DOI
  may legitimately be empty if not archived).
- **Missing `citation_apa`** — sources where this field is empty.
- **Uncited claims** — bullets in `## Key Findings`, `## Recommendations`,
  `## Summary` that don't contain `(p. ` — likely uncited.
- **Missing `study_design`** in source frontmatter.
- **Conflicting concept definitions** — same concept defined incompatibly
  across pages (use LLM semantic check).
- **Snowball debt** — references in any thesis's `## Notable References`
  marked ☐ for >30 days.
- **Data gaps** — surface as candidate `[[questions/...]]` pages.

Output a lint report and ask whether to save to `wiki/lint-report.md`.

---

## Health Workflow

Triggered by: *"health"* or `/wiki-health`.

Run: `python tools/health.py` (or `python tools/health.py --json`).

Fast structural integrity checks — **zero LLM calls**, safe every session:
- **Empty / stub files** — pages with no content beyond frontmatter.
- **Index sync** — `wiki/index.md` entries vs actual files on disk.
- **Log coverage** — source pages missing a corresponding `ingest` entry
  in `wiki/log.md`.

Output a health report. Use `--save` to write to `wiki/health-report.md`.

### Health vs Lint Boundary

| Dimension | `health` | `lint` |
|---|---|---|
| **Scope** | Structural integrity | Content quality (incl. citation hygiene) |
| **LLM calls** | Zero | Yes |
| **Cost** | Free | Tokens |
| **Frequency** | Every session | Every 10-15 ingests |
| **Tool** | `tools/health.py` | `tools/lint.py` |
| **Run order** | First | After health passes |

> Run `health` first — linting an empty file wastes tokens.

---

## Graph Workflow

Triggered by: *"build the knowledge graph"* or `/wiki-graph`.

Run `tools/build_graph.py`:
- Pass 1: parse all `[[wikilinks]]` -> deterministic `EXTRACTED` edges.
- Pass 2: infer implicit relationships -> `INFERRED` edges with confidence.
- Run Louvain community detection.
- Output `graph/graph.json` + `graph/graph.html`.

If Python/dependencies aren't set up, generate the graph data manually:
1. Use Grep to find all `[[wikilinks]]`.
2. Build a node/edge list, write `graph/graph.json`.
3. Write `graph/graph.html` from the vis.js template.

---

## Naming Conventions

- **Source slugs (papers)**: `kebab-case`
  (e.g. `cervera-2020-mi-bci-meta-analysis.md`).
- **Thesis slugs**: `lastname-year-shorttitle`
  (e.g. `dupont-2023-mi-bci-stroke.md`).
- **Entity pages**: `TitleCase.md`
  (e.g. `MaryamMaarek.md`, `INSERM-U1216.md`).
- **Concept pages**: `TitleCase.md`
  (e.g. `MotorImagery.md`, `Neuroplasticity.md`, `CorticospinalTract.md`).
- **Method pages**: `TitleCase.md`
  (e.g. `EEG.md`, `TMS.md`, `DTI.md`, `FuglMeyer.md`, `MI-BCI.md`).
- **Recommendation pages**: `kebab-case.md`
  (e.g. `mi-bci-stroke-rehab.md`).
- **Question pages**: `kebab-case.md`
  (e.g. `tms-dose-response-chronic-stroke.md`).
- **Synthesis pages**: `kebab-case.md` (often `<topic>-review.md`).

### Domain quick reference (stroke / MI-BCI / TMS / DTI)

Likely entries you'll create — keep names consistent:

- **Concepts**: `MotorImagery`, `MotorRecovery`, `Neuroplasticity`,
  `CorticospinalTract`, `M1`, `PremotorCortex`, `SMA`, `NeuralControlTheory`,
  `WhiteMatterIntegrity`, `Hemiparesis`, `StrokeChronicity`.
- **Methods**: `EEG`, `MI-BCI`, `TMS`, `rTMS`, `DTI`, `Tractography`, `MEP`,
  `FuglMeyer`, `ARAT`, `BoxAndBlocks`, `KVIQ`, `MIQ-RS`, `MentalChronometry`,
  `FA-MetricExtraction`.
- **Recommendation topics**: `mi-bci-stroke-rehab`,
  `tms-protocols-motor-recovery`, `dti-biomarkers-prognosis`.

---

## Index Format

```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — living synthesis

## Sources — Papers
- [Paper Title](sources/<slug>.md) — one-line summary (Year, Journal)

## Sources — Theses
- [Thesis Title](sources/<slug>.md) — one-line summary (Year, University)

## Concepts
- [Concept Name](concepts/<Name>.md) — one-line definition

## Methods
- [Method Name](methods/<Name>.md) — what it measures

## Recommendations
- [Topic](recommendations/<topic>.md) — one-line scope

## Questions
- [Question](questions/<slug>.md) — status

## Entities
- [Entity Name](entities/<Name>.md) — one-line description

## Syntheses
- [Title](syntheses/<slug>.md) — what question it answers
```

## Overview Page Format

`wiki/overview.md` is a living synthesis across all sources. Refreshed at
step 13 of the ingest workflow when synthesis warrants revision. The
Citation Rule applies under `## Key Findings (synthesized)`.

```markdown
---
title: "Wiki Overview"
type: synthesis
last_updated: YYYY-MM-DD
sources: []                 # auto-populated: all sources synthesized here
---

## Scope
1-3 sentences: what this wiki covers (no citation needed — meta).

## Key Findings (synthesized)
Cross-source claims, **each with citations**:
- Finding 1 (see [[paper-a]] p. ?, [[paper-b]] p. ?, [[cervera-2020]]
  meta-analysis p. ?)
- Finding 2 (see [[thesis-x]] ch. 4 p. ?, [[paper-c]] p. ?)

## Major Concepts
Linked, not redefined here:
- [[MotorImagery]], [[CorticospinalTract]], [[Neuroplasticity]],
  [[NeuralControlTheory]]

## Major Methods
- [[methods/MI-BCI]], [[methods/TMS]], [[methods/DTI]],
  [[methods/FuglMeyer]]

## Active Debates
Linked to question pages:
- Debate 1 → [[questions/<slug>]]
- Debate 2 → [[questions/<slug>]]

## Recent Updates
Append-only mini-log of synthesis-affecting ingests:
- YYYY-MM-DD : ingested [[new-paper]] — refined Finding X
- YYYY-MM-DD : ingested [[new-thesis]] — added Debate 2
```

## Log Format

Each entry starts with `## [YYYY-MM-DD] <operation> | <title>` so it's
grep-parseable:

```
grep "^## \[" wiki/log.md | tail -10
```

Operations: `ingest`, `query`, `review`, `cite`, `health`, `lint`, `graph`.

---

## Domain-Specific Templates (non-academic)

Kept available for diary entries or meeting notes mixed into `raw/notes/`.

### Diary / Journal Template

```markdown
---
title: "YYYY-MM-DD Diary"
type: source
tags: [diary]
date: YYYY-MM-DD
---
## Event Summary
## Key Decisions
## Energy & Mood
## Connections
## Shifts & Contradictions
```

### Meeting Notes Template

```markdown
---
title: "Meeting Title"
type: source
tags: [meeting]
date: YYYY-MM-DD
---
## Goal
## Key Discussions
## Decisions Made
## Action Items
```
