# Project context — bci-scoping

> Rempli le 2026-05-30. L'agent d'extraction lit ce fichier pour calibrer
> la profondeur d'extraction, désambiguïser les valeurs à extraire,
> valider les numériques, et appliquer les conventions de style.

## Review type

Scoping review — extraction descriptive, moins stricte sur les outcomes
cliniques. L'objectif est de cartographier les pratiques, pas de comparer
des effets entre études.

## Review objective

Identifier et cartographier les différents designs MI-BCI utilisés dans la
rééducation motrice post-AVC, à quatre niveaux d'analyse :

1. **Niveau consigne / trial** — quelle tâche est demandée, comment elle est
   instruite (consigne, répétition, vérification de compréhension), comment le
   trial est organisé, quelle est la tâche contrôle (ML → 2 classes à distinguer).

2. **Niveau session** — combien de MI réalisées, durée d'un run, nombre de runs,
   gestion de la fatigue et des pauses.

3. **Niveau protocole de rééducation** — rythme des séances, durée totale de l'étude.

4. **Niveau population** — critères de sélection des patients AVC, taille
   d'étude, sévérité motrice, chronicity.

L'objectif final est de croiser ces pratiques avec les recommandations de
rééducation motrice post-AVC et les bonnes pratiques BCI chez sujets sains
(Lotte, Roc) pour évaluer comment se font réellement les études MI-BCI post-AVC,
quelle population est vraiment étudiée (sur-sélection ?), et fournir des clés
pour le design d'études futures (state of the art).

## Research question

**Question principale :**
Comment sont designées les MI-BCI dans la rééducation après un AVC ?

**Sous-questions :**
- Quelle population est recrutée (sévérité, chronicity, critères d'exclusion) ?
- Comment sont expliquées les consignes de la tâche MI ?
- Comment s'organise une séance de rééducation (runs, pauses, durée) ?
- Comment sont cliniquement construites les études de MI-BCI en rééducation ?
- Comment les expériences MI-BCI sont-elles construites pour la rééducation
  du membre supérieur ?

## Primary outcomes of interest

n/a — cette review n'extrait pas d'outcomes cliniques comparés entre études.
Les variables d'intérêt sont des variables de design (voir template.xlsx).

## Notes for the extraction agent

**Chronicity tiers (toujours appliquer cette classification) :**
- Acute : < 3 mois post-AVC
- Subacute : 3–6 mois post-AVC
- Chronic : > 6 mois post-AVC
- Mixte : si l'étude inclut plusieurs tiers

**Sévérité motrice :** basée sur FMA (Fugl-Meyer Assessment) ou ARAT.
Catégories : Mild to moderate / Severe. Utiliser la classification de l'article.

**Instructions MI :** pour la colonne `Instructions MI and Control`, citer
VERBATIM le passage exact de l'article décrivant les consignes (copy-paste).
Si non rapporté → "Not reported".

**Modalité sensorielle (coding) :**
- 0 : No report of instructions
- 1 : Kinesthetic
- 2 : Visual
- 3 : Multimodal

**Fréquence MI :**
- Non Connu / 1 Sustained / 2 Repeated

**Tâche contrôle :** noter verbatim si c'est Rest / Baseline / Unaffected hand MI
ou autre. Ne jamais inférer si non rapporté.

**Feedback congruence :**
- Congruent (feedback = MI)
- Partial
- Non-congruent → noter pourquoi si l'article l'explique

**Style général :**
- Citer les paramètres de session verbatim (durée de run, nombre de runs,
  nombre d'essais, durée des pauses) — ne jamais paraphraser.
- Si un paramètre n'est pas rapporté → "Not reported", ne jamais inférer.
- Toutes les durées en unités de l'article (ne pas convertir sauf si demandé
  colonne par colonne dans instructions.md).

## Source list

(À remplir — un slug par ligne, correspondant à `wiki/sources/<slug>.md`.)

- biasiucci-2018-bci-fes-motor-recovery
