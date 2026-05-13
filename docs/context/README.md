# Domain Context System

GraphBib is a **domain-neutral academic wiki agent** with a single
configuration file — `context.md` at the repo root — that tells the
agent what field this instance covers, what vocabulary to expect,
and how to taxonomize sources.

## Why a context file

The core of GraphBib (PDF/EPUB conversion, IMRAD source extraction,
citation network, snowball discovery, dedupe pre-filter, lint) is
field-agnostic. But the agent does better work when it knows:

1. What **concepts** are likely to recur (so repeated mentions land
   on the same page rather than spawning near-duplicates)
2. What **outcome scales** to recognize verbatim (so extraction
   tables are populated correctly)
3. What **intervention families** to use for source routing
4. What **style** the agent should adopt (which authorities to cite,
   what distinctions matter, what to flag)

`context.md` captures all of this in one place. Without it, the
agent still works — it'll just create vocabulary on the fly with
less consistency.

## How to adapt to your domain

### Option A — pick an example

```bash
cp docs/context/examples/<your-domain>.md context.md
```

Available examples in this repo:

| File | Domain | Use if your wiki covers… |
|---|---|---|
| `stroke-mibci-tms.md` | Stroke motor rehabilitation via MI-BCI + TMS | Default fork content (the de-facto GraphBib config) |
| `generic-academic.md` | Domain-agnostic baseline | You want minimum vocabulary bias; you'll let the agent grow the taxonomy from your sources |
| `clinical-trials-cardiology.md` | Cardiovascular clinical trials | Drug RCTs, hard endpoints, regulatory submissions |

### Option B — start from a template, customize

Open `docs/context/examples/generic-academic.md`, save it as
`context.md` at the repo root, then fill in:

1. **Identity** — 2–3 sentences about your field and its central
   question
2. **Concepts vocabulary** — 10–20 recurring constructs in your
   domain (CamelCase page names)
3. **Methods vocabulary** — measurement instruments + acquisition
   modalities
4. **Interventions taxonomy** — `intervention_family` /
   `intervention_subfamily` enum if applicable (skip if your domain
   isn't interventional, e.g. pure theory or basic science)
5. **Outcome scales** — quantitative measures for SR extraction (if
   relevant)
6. **Anatomical / structural anchors** — for fields where physical
   structure matters (anatomy, materials, geography…)
7. **Recommendation topics** — kebab-case slugs under which the
   agent will aggregate recommendations
8. **Style notes** — domain-specific conventions: which authorities
   to cite, what distinctions to flag, what to quote verbatim

### Option C — agent-assisted bootstrap

Open a fresh session and ask:

> *"Initialize a context.md for a wiki on **X**. Ask me 5
> clarifying questions about the field, then draft the taxonomy."*

The agent walks you through the schema. Save its output as
`context.md`.

## Adaptation checklist beyond context.md

Some domain bias still lives in **code** that needs separate
patching. If you're moving to a non-stroke domain, audit:

| File | Why | What to edit |
|---|---|---|
| `tools/organize_sources.py` | `FAMILY_FOLDER` and `IMAGING_METHODS` are hardcoded Python dicts | Match the enums to your `context.md` interventions taxonomy |
| `tools/dti_aggregator.py` | Stroke / DTI-specific anatomical regex | Delete if irrelevant, or rewrite for your structures |
| `tools/effect_size_aggregator.py` | Stroke motor outcome regex (FM, ARAT, BBT, NHPT, MAS, MEP) | Rewrite with your outcome scales |
| `tools/brain_atlas_anchor.py` | Anchors to M1, CST, etc. | Delete or repurpose |
| `tools/cohort_tracker.py` | Likely tracks stroke chronicity / lesion / age | Audit for your cohort variables |
| `.claude/agents/*.md` | System prompts contain stroke examples | Search for stroke/MI-BCI/TMS and replace with your domain examples |

Tools `dti_aggregator.py`, `effect_size_aggregator.py`,
`brain_atlas_anchor.py`, `cohort_tracker.py` won't *break* if you
leave them as-is — they just won't match anything in your corpus
and become inert. Safe to delete from `tools/` if you prefer a clean
folder.

## What the agent does with context.md

Every sub-agent (`ingester`, `concept-builder`, `query-synthesizer`,
`reviewer`, `suggest-reading`, `extractor`, etc.) reads `context.md`
at the start of its run. The orchestrator (Claude Code reading
`CLAUDE.md`) is told to load it before any wiki operation.

Concretely the context biases:
- **Ingest** — what concept / method pages to look for vs create;
  what intervention_family value to assign
- **Concept building** — what theoretical framing to use; which
  authorities are canonical
- **Query / Review** — what counts as "the literature" on a topic
- **Snowball** — which DOI prefixes / journals to weight up
- **Extraction** — which outcome scales to recognize in tables

If `context.md` is absent, the agent runs in *neutral mode*: it'll
do all the structural work (IMRAD extraction, citation network,
snowball, lint) but with less domain consistency.
