# Domain Context

> Read me first. I tell the agent what domain this wiki is configured for.
>
> **This is the neutral baseline** (`generic-academic`). To configure
> GraphBib for a specific field, replace my content with one of the
> ready-made examples in `docs/context/examples/` (e.g.
> `stroke-mibci-tms.md`, `clinical-trials-cardiology.md`) or draft your
> own from this template. See `docs/context/README.md` for the full
> adaptation checklist.

---

## Identity

**This GraphBib instance is configured for general academic research.**

The wiki is intentionally domain-neutral: the agent applies the same
IMRAD extraction discipline and citation-network rules regardless of
field, and lets concept / method / intervention vocabulary emerge
from the sources themselves.

---

## Concepts vocabulary

*Not pre-specified.* The agent creates concept pages as new
constructs appear in ingested sources. After ~10 ingests, review
`wiki/concepts/` and add a "consolidation" pass via the
`deduplicator` agent to merge near-duplicates.

If you want some anchor terms to seed consistency, list them here:

- (empty - will grow with ingests)

---

## Methods vocabulary

*Not pre-specified.* As above - let the corpus dictate.

---

## Interventions taxonomy (drives `intervention_family` / `intervention_subfamily`)

Skip the `intervention_family` / `intervention_subfamily` fields in
the source template if your domain isn't interventional (pure
theory, basic science, observational only). The agent will leave
them empty, and `tools/organize_sources.py` will route everything
to `wiki/sources/articles/general/`.

If you do have interventions, declare the families here as a flat
list (and mirror them in `tools/organize_sources.py` →
`FAMILY_FOLDER` if you want thematic routing):

| `intervention_family` | `intervention_subfamily` values |
|---|---|
| `none` | (default - non-interventional) |

---

## Outcome scales (for systematic-review data extraction)

*Not pre-specified.* If your domain has standard scales (e.g. quality
of life inventories, performance benchmarks), list them here, and
mirror the machine-readable form in `tools/data/domain.json`
(`outcome_scales`) so `tools/effect_size_aggregator.py` and the
extractor sub-agent recognize them:

| Scale | What it measures | Typical range |
|---|---|---|
| (none declared) | - | - |

---

## Anatomical / structural anchors

*Not pre-specified.* Skip this section if your domain has no
physical structures to anchor to. If it does (brain regions, organs,
tissues, pathways), declare them in `tools/data/domain.json`
(`regions` / `tracts`) so `tools/brain_atlas_anchor.py` and
`tools/dti_aggregator.py` can anchor sources to them.

---

## Recommendation topics

Topics under which clinical / policy / research recommendations are
aggregated in `wiki/recommendations/`:

- (none declared - will grow with ingests)

---

## Style notes for the agent

- Apply the **Citation Rule** strictly: every factual claim cites
  `[[source]] (p. N)`.
- Apply the **Depth & Completeness Rule**: enumerate exhaustively
  rather than summarizing.
- Be **conservative with conceptual claims**: if a source advances
  a controversial position, attribute it explicitly to that source
  rather than stating it as established fact.
- Quote **numerical results and definitions verbatim**.
- **No domain authorities pre-declared** - the agent treats all
  peer-reviewed sources as equally weighty until the wiki itself
  reveals which authors / labs / journals are most cited.

---

## How the agent reads this file

In neutral mode, the agent uses this file mostly for the **style
notes**. The empty vocabulary sections signal "no expected
taxonomy" - the agent will grow `wiki/concepts/`, `wiki/methods/`,
and `wiki/interventions/` organically from sources, then suggest a
consolidation pass once enough material exists.

When you fill the vocabulary sections for a real domain, the
**machine-readable mirror** lives in `tools/data/domain.json`
(consumed by the analyzer tools) and, for intervention routing, in
`tools/organize_sources.py`. See `docs/context/README.md` for the
full adaptation checklist.
