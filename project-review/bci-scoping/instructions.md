# Extraction instructions — bci-scoping

> Généré le 2026-05-30 depuis BCI Systematic Review Variables1.csv.
> Chaque section = une colonne du template.xlsx (ligne 2 = instruction terse).
> Compléter les sections vides avant de lancer /wiki-extract-table.

---

## Author
Nom du premier auteur (Last name, Initials). Ex : "Ang K.K."

## Year
Année de publication — 4 chiffres.

## DOI
DOI complet. Ex : "10.1109/TNSRE.2015.2419842". Si absent → "Not reported".

## Exclusion criteria
**Ligne 2 :** `Liste of exclusion criteria`

Lister verbatim les critères d'exclusion tels que rapportés dans l'article
(section Methods / Participants). Si non rapportés → "Not reported".

## Time from stroke
**Ligne 2 :** `Acute (< 3 mois) | Subacute (3-6 mois) | Chronic (> 6 mois) | Mixte`

Catégorie de chronicity de la population. Utiliser la classification de l'article
si explicite, sinon déduire depuis les valeurs numériques rapportées.
- Acute : < 3 mois post-AVC
- Subacute : 3–6 mois post-AVC
- Chronic : > 6 mois post-AVC
- Mixte : l'étude inclut plusieurs catégories

## Motor severity
**Ligne 2 :** `Based on FMA or ARAT scale : Mild to moderate | Severe`

Sévérité motrice de la population incluse. Basée sur FMA-UE ou ARAT.
Si les deux sont rapportés, préférer FMA. Catégories : "Mild to moderate" / "Severe".
Si non rapporté → "Not reported".

## Sensory severity ?
**Ligne 2 :** `0 - Not assessed | 1 - Assessed`

L'étude évalue-t-elle la sévérité sensitive ?
- 0 : Non évaluée / non rapportée
- 1 : Évaluée (préciser l'outil dans le détaillé)

## % patients screened
Pourcentage de patients screenés par rapport aux patients inclus (flow CONSORT).
Si non rapporté → "Not reported".

## % Drop-out
Pourcentage d'abandons sur l'ensemble des participants inclus.
Si non rapporté → "Not reported".

## % Illiteracy
**Ligne 2 :** `% patients < 60% overall sessions`

Pourcentage de patients ayant complété moins de 60 % des séances totales
(proxy de l'adhérence). Si non rapporté → "Not reported".

## Population size
**Ligne 2 :** `Number of patients included (in BCI group(s))`

Nombre de patients dans le(s) groupe(s) BCI uniquement (exclure les groupes
contrôle non-BCI). Si design à groupe unique → n total.

## Instructions MI verbatim
**Ligne 2 :** `Comment les instructions sont données ? > Non rapporté > Répété ? --> copy-paste exact citation`

Copy-paste VERBATIM le(s) passage(s) exact(s) de l'article (section Methods)
décrivant le contenu des instructions pour la tâche MI ET la tâche contrôle.
Si non rapporté → "Not reported".

## Instructions delivery (who / how)
**Ligne 2 :** `Therapist verbal real-time | Therapist verbal pre-session | Video | Audio | Written | Not reported`

Qui délivre les instructions et sous quelle forme :
- Therapist verbal real-time : thérapeute présent, guidage oral en cours de trial
- Therapist verbal pre-session : briefing oral avant la session, pas de rappel pendant
- Video : instructions pré-enregistrées en vidéo
- Audio : instructions audio pré-enregistrées
- Written : instructions écrites (feuillet, écran)
- Not reported : modalité de délivrance non précisée

## Instructions timing
**Ligne 2 :** `Before session only | Trial-by-trial | On demand | Not reported`

Quand et à quelle fréquence les instructions sont-elles délivrées :
- Before session only : une fois au début, pas de rappel pendant la session
- Trial-by-trial : rappel ou ajustement verbal à chaque trial
- On demand : uniquement si le patient le demande ou en cas d'erreur
- Not reported

## Instructions standardized
**Ligne 2 :** `Standardized script | Free (therapist discretion) | Not reported`

Les instructions suivent-elles un script standardisé ou sont-elles laissées à
la discrétion du thérapeute ?
- Standardized script : script écrit fourni dans l'article ou en annexe
- Free (therapist discretion) : contenu décrit narrativement, pas de script
- Not reported : aucune information

## Comprehension check
**Ligne 2 :** `Cognitive screening | Verbal check | Practice trials | None reported | Not reported`

Comment la compréhension de la tâche MI est-elle vérifiée avant/pendant l'étude :
- Cognitive screening : test cognitif général (ex : Raven) — vérifie la capacité,
  pas la compréhension spécifique de la MI
- Verbal check : le thérapeute pose des questions de compréhension
- Practice trials : trials d'entraînement sans feedback avant les sessions officielles
- None reported : explicitement aucun check
- Not reported : pas mentionné

## Trial start procedure
**Ligne 2 :** `Therapist keypress | Automatic cue | Patient self-initiated | Not reported`

Comment chaque trial est-il initié :
- Therapist keypress : le thérapeute appuie sur une touche quand le patient est prêt
- Automatic cue : déclenchement automatique selon un timing fixe
- Patient self-initiated : le patient déclenche lui-même
- Not reported

## Nature of the task
**Ligne 2 :** `Hand Grasping | Object Reaching | Hand Opening | Hand Rotating | Finger Taping`

Nature de la tâche MI demandée. Valeurs possibles :
- Hand Grasping
- Object Reaching
- Hand Opening
- Hand Rotating
- Finger Taping
- Other (préciser verbatim)
Plusieurs valeurs séparées par " / " si l'étude teste plusieurs tâches.

## Sensory Modality
**Ligne 2 :** `0: No report | 1: Kinesthetic | 2: Visual | 3: Multimodal`

Modalité sensorielle de la tâche MI instruite.
- 0 : Aucune instruction de modalité rapportée
- 1 : Kinesthésique (imaginer les sensations musculaires / proprioceptives)
- 2 : Visuelle (imaginer le mouvement vu de l'extérieur)
- 3 : Multimodal (les deux modalités instruites)

## Frequency (sustained vs repeated)
**Ligne 2 :** `Non Connu | 1 Sustained | 2 Repeated`

La tâche MI est-elle soutenue (une seule période de MI par trial) ou répétée
(plusieurs répétitions de MI dans un trial) ?
- Non Connu : non précisé dans l'article
- 1 Sustained : MI soutenue sur la durée du trial
- 2 Repeated : MI répétée / cadencée dans le trial

## MI Duration (s)
Durée d'un trial de MI en secondes. Rapporter la valeur numérique.
Si plage (ex : 4–8 s) → rapporter "4–8". Si non rapporté → "Not reported".

## Control Task
**Ligne 2 :** `Rest | Baseline | Unaffected hand MI | Other`

Nature de la tâche contrôle utilisée (deuxième classe pour le classifieur ML).
- Rest : repos
- Baseline : période de baseline passive
- Unaffected hand MI : imagerie du membre non-affecté
- Other : préciser verbatim
Si non rapporté → "Not reported".

## Congruent Reward
**Ligne 2 :** `MI = feedback ? Congruent | Partial | Non-congruent > why`

Le feedback fourni est-il congruent avec la MI demandée ?
- Congruent : le feedback représente fidèlement l'action imaginée
- Partial : le feedback représente partiellement la MI
- Non-congruent : le feedback ne correspond pas à la MI → noter pourquoi
  (ex : feedback visuel d'un robot non-représentatif du mouvement imaginé)
Si non rapporté → "Not reported".

## Feedback Duration
Durée du feedback fourni après classification, en secondes.
Si identique à la durée du trial → le préciser. Si non rapporté → "Not reported".

## Adaptive feedback
**Ligne 2 :** `feedback binary or graded ?`

Le feedback est-il binaire (succès / échec) ou gradué (proportionnel au score
de classification) ? Préciser le type d'adaptation si décrit.
Si non rapporté → "Not reported".

## N of Trials of MI
Nombre de trials MI par session (ou par run si précisé ainsi).
Rapporter la valeur numérique. Si non rapporté → "Not reported".

## Trial Duration (s)
Durée totale d'un trial (préparation + MI + feedback + inter-trial interval)
en secondes. Si non rapporté → "Not reported".

## N of runs
Nombre de runs par session. Rapporter la valeur numérique.
Si non rapporté → "Not reported".

## Run Duration (min)
Durée d'un run en minutes. Rapporter la valeur numérique.
Si non rapporté → "Not reported".

## N of breaks between runs
Nombre de pauses entre les runs dans une session.
Si non rapporté → "Not reported".

## Duration of breaks bw runs (s)
Durée des pauses entre runs en secondes.
Si plage → rapporter "min–max". Si non rapporté → "Not reported".

## Time of debrief
Moment et fréquence du debrief / questionnaire de perception de la MI
(avant session, après session, à intervalles, etc.).
Si non rapporté → "Not reported".

## Session duration (h)
**Ligne 2 :** `When and how often`

Durée totale d'une session en heures (ou minutes si l'article rapporte en
minutes — noter l'unité). Si non rapporté → "Not reported".

## N of Session
Nombre total de sessions BCI dans l'étude.
Rapporter la valeur numérique. Si non rapporté → "Not reported".

## Frequency of sessions per week
Fréquence des sessions exprimée en sessions par semaine.
Si variable → rapporter la plage (ex : "3–5"). Si non rapporté → "Not reported".

## Duration of Study (day)
Durée totale de l'étude en jours (de la première à la dernière session BCI).
Rapporter la valeur numérique. Si non rapporté → "Not reported".
