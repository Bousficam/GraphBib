# Intervention Page Format

Intervention pages document **treatments** — what is delivered to a
patient or participant. Distinct from `methods/` (which documents
measurement instruments like EEG, KVIQ, MEP). Use this for interventions
tested by multiple studies of the same family (BCI, TMS, mirror therapy,
robot-assisted training, mental practice, etc.).

A page is created or refreshed at ingest step 9b: when ≥ 2 sources in
the wiki use the same `intervention_family`, the agent generates
`wiki/interventions/<intervention-slug>.md`.

```markdown
---
title: "Intervention: MI-BCI"
type: intervention
aka: ["motor imagery brain-computer interface", "EEG-based MI-BCI"]
intervention_family: "BCI"      # BCI | TMS | tDCS | mirror | robot |
                                # mental-practice | physio | combined
target_outcome: ["motor recovery", "corticospinal excitability"]
domain: [stroke, motor-rehab]
variants: ["MI-BCI + FES", "MI-BCI + AO", "closed-loop MI-BCI"]
sources: []                     # auto-populated: studies using this intervention
last_updated: YYYY-MM-DD
---

## Definition
2-3 sentences with citation:
*"Motor-imagery BCI is a closed-loop system that translates EEG correlates
of imagined movement into feedback ..."* ([[paper-x]] p. ?).

## Mechanism of Action (proposed)
Hypothesized active ingredients. Link to relevant [[concepts/...]] pages
(Neuroplasticity, NeuralControlTheory, Hebbian-learning).
- Mechanism A — supported by [[paper-a]] (p. ?), [[paper-b]] (p. ?).
- Mechanism B — proposed but contested ([[paper-c]] p. ?).

## Variants
Sub-types found in the literature:
- Variant A — used by [[paper-x]] (p. ?), [[paper-y]] (p. ?).
  Distinguishing feature: e.g. "FES feedback contingent on motor imagery".
- Variant B — used by [[paper-z]] (p. ?). Distinguishing feature: ...

## Protocol Parameters (synthesized across studies)
Aggregated from RCTs in the wiki:
- **Sessions**: range — typical (e.g. 12-30, typical 20)
- **Session duration**: range — typical (e.g. 30-60 min, typical 45)
- **Total dosage**: range — typical hours of training
- **Co-interventions**: usual concurrent therapies
- **Patient inclusion**: chronicity, baseline severity, lesion criteria

## Identified Studies
Brief table by design.

| Study | Design | N | Population | Outcome (Δ) | Effect |
|---|---|---|---|---|---|
| [[paper-a]] | RCT | 32 | chronic stroke, FM 25-50 | ΔFM = +6.2 (p. ?) | medium |
| [[paper-b]] | open-label | 12 | subacute, FM 20-30 | ΔFM = +4.1 (p. ?) | small |

## Pooled Outcomes (when comparable)
- **ΔFugl-Meyer Upper Extremity** at end-of-treatment: median, range across RCTs.
- **ΔARAT**: ...
- **MEP amplitude change**: ...

## Best Practices (consensus)
- Practice 1 — consensus across [[a]], [[b]], [[c]] (p. ? each).
- Practice 2 — recommended by [[d]] (p. ?), but contested by [[e]] (p. ?).

## Patient Selection
Sub-group analyses if available.
- Who benefits more? (e.g. preserved CST integrity per DTI — [[paper-x]] p. ?)
- Who doesn't? (e.g. severe baseline impairment, complete CST disruption)

## Contraindications & Adverse Events
- Contraindication 1 (p. ?)
- Adverse event incidence reported in [[paper-x]] (p. ?).

## Open Questions
- → [[questions/<slug>]]: dose-response not yet established.
- → [[questions/<slug>]]: long-term retention beyond 6 months unclear.

## Related
- Underlying concepts: [[MotorImagery]], [[Neuroplasticity]].
- Measurement methods: [[methods/EEG]], [[methods/FuglMeyer]], [[methods/MEP]].
- Related interventions: [[interventions/AO-BCI]], [[interventions/rTMS]].
- Recommendations: [[recommendations/mi-bci-stroke-rehab]].

## Used In This Wiki
*(Auto-populated: [[source-slug]] entries that report using this
intervention. Each entry MUST include the per-study protocol variant
detail, not just a bare wikilink.)*
```
