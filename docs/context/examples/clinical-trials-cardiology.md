# Domain Context - Cardiovascular clinical trials

> Example of a different-domain `context.md`. Copy to repo root if
> your wiki covers heart-failure / ischemia / arrhythmia drug trials.

---

## Identity

**This GraphBib instance is configured for research on
*cardiovascular pharmacological trials* - drug therapies for heart
failure, ischemic heart disease, arrhythmias, and hypertension.**

Central question: *which drug regimens reduce hard cardiovascular
endpoints (MACE, CV death, hospitalization) in which patient
phenotypes, and what is the regulatory / guideline status?*

Typical paper structure expected: phase II/III RCT with CONSORT
flow diagram, intention-to-treat primary analysis, predefined
secondary endpoints, sometimes a Cochrane / ESC / AHA guideline
update.

---

## Concepts vocabulary

- `HeartFailure`, `HFrEF`, `HFpEF` - reduced / preserved ejection fraction
- `IschemicHeartDisease`, `CoronaryArteryDisease`
- `AtrialFibrillation`, `VentricularArrhythmia`
- `MACE` - major adverse cardiovascular event composite
- `LeftVentricularRemodeling`
- `Neurohormonal` (RAAS, sympathetic activation)
- `EndothelialDysfunction`
- `Inflammation` (CRP, IL-6, SGLT2 anti-inflammatory effect)
- `RegulatoryEndpoint` - FDA / EMA accepted outcomes

---

## Methods vocabulary

- `RCT`, `MetaAnalysis`, `NetworkMetaAnalysis`
- `Echocardiography`, `CardiacMRI`, `CTA`
- `EjectionFraction`, `NTproBNP`, `Troponin`
- `KaplanMeier`, `CoxRegression`, `HazardRatio`
- `IntentionToTreat`, `PerProtocol`

---

## Interventions taxonomy

| `intervention_family` | `intervention_subfamily` values |
|---|---|
| `raas-inhibition` | `acei`, `arb`, `arni`, `mra` |
| `beta-blocker` | `bisoprolol`, `carvedilol`, `metoprolol-succinate`, `nebivolol` |
| `sglt2-inhibitor` | `dapagliflozin`, `empagliflozin`, `canagliflozin` |
| `anticoagulant` | `vka`, `doac-factor-xa`, `doac-direct-thrombin` |
| `antiplatelet` | `aspirin`, `p2y12-inhibitor`, `dual-therapy` |
| `statin` | `low-intensity`, `moderate-intensity`, `high-intensity` |
| `device` | `icd`, `crt`, `lvad`, `ablation` |
| `revascularization` | `pci`, `cabg`, `tavi` |
| `lifestyle` | `cardiac-rehab`, `diet`, `exercise-training` |
| `combined` | (e.g. `arni-plus-sglt2`) |
| `none` | observational / registry study |

---

## Outcome scales

| Scale | What it measures | Typical range |
|---|---|---|
| LVEF | Left ventricular ejection fraction (%) | 0-80 |
| NYHA | Functional class (heart failure severity) | I-IV |
| KCCQ | Kansas City Cardiomyopathy Questionnaire | 0-100 |
| 6MWT | Six-minute walk distance (m) | 0-~700 |
| NT-proBNP | Natriuretic peptide (pg/mL) | continuous, log-normal |
| MACE | Composite endpoint (death/MI/stroke/HF hosp) | rate / hazard ratio |

---

## Anatomical / structural anchors

- `LeftVentricle`, `RightVentricle`
- `LeftAtrium`, `RightAtrium`
- `MitralValve`, `AorticValve`, `TricuspidValve`
- `CoronaryArteries` (LAD, LCx, RCA)
- `ConductionSystem` (SA node, AV node, His-Purkinje)

---

## Recommendation topics

- `hfref-pharmacotherapy` - guideline-directed HFrEF medical therapy
- `hfpef-management` - emerging HFpEF interventions
- `af-anticoagulation` - DOAC vs VKA decision rules
- `acs-revascularization` - PCI vs CABG vs medical therapy
- `secondary-prevention` - post-MI lipid / BP / antiplatelet stack
- `device-therapy-indications` - ICD / CRT eligibility

---

## Style notes for the agent

- **Always report effect size with 95% CI** - never a bare p-value.
- **Distinguish primary vs secondary endpoints**; do not promote a
  secondary finding to the level of an established benefit.
- **Flag regulatory status**: FDA-approved / EMA-approved /
  off-label / guideline-recommended (Class I/II/III).
- **Note guideline lineage**: AHA/ACC vs ESC may differ; cite both
  when they diverge.
- **Cite Cochrane reviews and network meta-analyses** when
  available - they often supersede individual RCTs for synthesis.
- **Phenotype the patient population precisely**: HFrEF vs HFpEF,
  ischemic vs non-ischemic, sinus vs AF - outcomes can flip.
- **Quote sample size, follow-up duration, and event rate
  verbatim** - these drive whether a result is clinically
  meaningful.

---

## How the agent reads this file

See `docs/context/README.md`. The taxonomies above will drive
`docs/templates/source-academic-paper.md` enums, the
`tools/organize_sources.py` routing (after you also update
`FAMILY_FOLDER` to match), and the extraction outcome regex.
