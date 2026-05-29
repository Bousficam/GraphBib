# Domain Context

> Read me first. I tell the agent what domain this wiki is configured for.
>
> **Replace my content** (or pick an alternative from `docs/context/examples/`)
> to adapt GraphBib to your own research domain.

---

## Identity

**This GraphBib instance is configured for research on
*stroke motor rehabilitation via MI-BCI and TMS*, anchored in neural
control theory and white-matter anatomy (DTI).**

Central question: *how do brain-computer interfaces driven by motor
imagery and non-invasive brain stimulation (TMS, tDCS) restore
upper-limb motor function after stroke, and which patients respond?*

Typical paper structure expected by the agent: IMRAD with quantified
outcomes (Fugl-Meyer / ARAT / box-and-blocks), often a randomized
controlled trial or a meta-analysis of RCTs, sometimes a
neuroimaging biomarker study (DTI of corticospinal tract).

---

## Concepts vocabulary

Expected concept pages — keep these names consistent when they
appear:

- `MotorImagery` — mental simulation of movement
- `MotorRecovery` — return of motor function after lesion
- `Neuroplasticity` — neural reorganization underlying recovery
- `CorticospinalTract` — primary descending motor pathway (anatomy + integrity)
- `M1` — primary motor cortex
- `PremotorCortex`, `SMA` — secondary motor areas
- `NeuralControlTheory` — optimal-feedback / internal-model frameworks
- `WhiteMatterIntegrity` — DTI-derived structural measure
- `Hemiparesis` — clinical motor deficit
- `StrokeChronicity` — acute / subacute / chronic phase distinction

This list isn't exhaustive — the agent creates new concept pages as
new constructs appear in sources. It's a *consistency anchor* so
that repeated mentions land on the same page.

---

## Methods vocabulary

Expected method pages (measurement instruments and acquisition
modalities):

- `EEG` — electroencephalography
- `MI-BCI` — motor-imagery brain-computer interface
- `TMS`, `rTMS` — transcranial magnetic stimulation (single-pulse, repetitive)
- `DTI`, `Tractography` — diffusion imaging + fiber tracking
- `MEP` — motor evoked potential
- `FuglMeyer`, `ARAT`, `BoxAndBlocks` — upper-limb motor outcome scales
- `KVIQ`, `MIQ-RS` — motor-imagery questionnaires
- `MentalChronometry` — imagery vividness via timing
- `FA-MetricExtraction` — DTI scalar map computation

---

## Interventions taxonomy (drives `intervention_family` / `intervention_subfamily`)

Two-tier taxonomy used by `tools/organize_sources.py` and the
source-paper template:

| `intervention_family` | `intervention_subfamily` values |
|---|---|
| `bci` | `mi-bci`, `ao-bci`, `ssvep-bci`, `hybrid` |
| `tms` | `rtms`, `itbs`, `ctbs`, `paired-associative` |
| `tdcs` | `anodal`, `cathodal`, `bihemispheric` |
| `mirror` | `mirror-therapy`, `bilateral-mirror` |
| `robot` | `robot-assisted`, `exoskeleton` |
| `mental-practice` | `imagery-only`, `imagery-with-observation` |
| `physio` | `caimt`, `task-oriented`, `bobath` |
| `combined` | (e.g. `bci-plus-tms`, `tms-plus-physio`) |
| `none` | non-interventional study (cohort, observational) |

---

## Outcome scales (for systematic-review data extraction)

Standard outcome instruments the agent recognizes when filling
extraction tables:

| Scale | What it measures | Typical range |
|---|---|---|
| FM-UE | Fugl-Meyer Upper Extremity motor score | 0–66 |
| ARAT | Action Research Arm Test | 0–57 |
| BBT | Box and Block Test (blocks/min) | 0–~80 |
| NHPT | Nine-Hole Peg Test (seconds) | lower = better |
| MAS | Modified Ashworth Scale (spasticity) | 0–4 |
| MEP amplitude | Cortico-spinal excitability (mV) | continuous |

These also drive `tools/effect_size_aggregator.py` regex matching.

---

## Anatomical anchors

Brain structures referenced in DTI / lesion / imaging papers — used
by `tools/dti_aggregator.py` and `tools/brain_atlas_anchor.py`:

- `CorticospinalTract` (CST, pyramidal tract)
- `InternalCapsule` (PLIC = posterior limb of internal capsule)
- `CorpusCallosum`
- `ArcuateFasciculus`
- `SuperiorLongitudinalFasciculus` (SLF)
- `ThalamicRadiation`
- `Uncinate fasciculus`
- `M1`, `PremotorCortex`, `SMA`, `Cerebellum`

---

## Recommendation topics

Topics under which clinical / research recommendations are
aggregated in `wiki/recommendations/`:

- `mi-bci-stroke-rehab` — MI-BCI deployment in stroke rehabilitation
- `tms-protocols-motor-recovery` — TMS dose-response for motor recovery
- `tdcs-stroke-protocols` — tDCS adjuvant therapy
- `dti-biomarkers-prognosis` — DTI as motor-outcome biomarker
- `imagery-assessment` — KVIQ / MIQ-RS administration

---

## Style notes for the agent

- **Cite both primary and meta-analytic sources** when a finding is
  established. Don't drop the original RCT just because a recent
  meta-analysis covers it.
- **Always distinguish acute / subacute / chronic stroke** when
  reporting outcomes — recovery dynamics differ profoundly.
- **Flag ipsilesional vs contralesional** stimulation targets in
  TMS / tDCS protocols.
- **Quote dose parameters verbatim** for stimulation protocols
  (frequency, intensity, sessions, train duration) — never paraphrase.
- **DTI metrics**: FA / MD / AD / RD reported with the tract they
  qualify; never report a bare FA value without the ROI / tract name.

---

## How the agent reads this file

The agent loads `context.md` at the start of every ingest / synthesis
session. The taxonomies above drive:

- Closed-enum fields in `docs/templates/source-academic-paper.md`
  (`intervention_family`, `intervention_subfamily`)
- Routing in `tools/organize_sources.py`
  (`FAMILY_FOLDER`, `IMAGING_METHODS`)
- Regex matchers in `tools/dti_aggregator.py` and
  `tools/effect_size_aggregator.py`
- Examples in sub-agent prompts (`.claude/agents/*.md`)
- Concept-name suggestions in `docs/conventions/naming.md`

If you change this file, also review whether the **code-level**
routing in `tools/organize_sources.py` needs an update — that file
is the only hardcoded mirror of this taxonomy in Python source.
See `docs/context/README.md` for the full adaptation checklist.
