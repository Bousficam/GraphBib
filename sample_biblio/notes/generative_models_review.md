---
title: "Revue — Modèles génératifs pour la synthèse d'images"
authors: ["Notes personnelles"]
year: 2024
keywords: [GAN, diffusion model, VAE, generative model, image synthesis]
tags: [survey, generative]
---

## Panorama des approches génératives

### GANs (Generative Adversarial Networks)

Introduits par Goodfellow et al. (2014), les GANs entraînent deux réseaux en opposition :
- **Générateur G** : produit des images fausses à partir de bruit latent
- **Discriminateur D** : distingue vrai/faux

Problèmes connus : instabilité d'entraînement, mode collapse.

### VAEs (Variational Autoencoders)

Encodent l'entrée dans un espace latent gaussien. Génération douce mais images floues.

### Modèles de diffusion

Approche actuelle state-of-the-art. Apprend à débruiter progressivement.
- **DDPM** : débruitage discret en T étapes
- **Stable Diffusion** : diffusion dans l'espace latent (latent diffusion)
- Conditionnement texte-image via CLIP

## Comparaison

| Modèle | Qualité | Diversité | Contrôle | Vitesse |
|--------|---------|-----------|----------|---------|
| GAN    | ★★★★   | ★★★       | ★★★★    | ★★★★★  |
| VAE    | ★★★     | ★★★★     | ★★       | ★★★★★  |
| Diff.  | ★★★★★  | ★★★★★    | ★★★★★   | ★★      |

## Références
- [[goodfellow2014gan]]
- [[rombach2022latent_diffusion]]
