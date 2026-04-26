---
title: "Vue d'ensemble — Architecture Transformer"
authors: ["Notes personnelles"]
year: 2024
keywords: [transformer, attention, NLP, computer vision, multimodal]
tags: [survey, architecture]
---

## Introduction

L'architecture **Transformer** (Vaswani et al., 2017) est devenue le paradigme dominant
en deep learning, d'abord en NLP puis en vision par ordinateur.

## Mécanisme d'attention

Le mécanisme de self-attention calcule une pondération entre chaque paire de tokens :

```
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

L'attention multi-têtes parallélise ce calcul sur plusieurs sous-espaces.

## Évolution de l'architecture

- **Encoder-Decoder** : traduction, résumé automatique (BERT encoder / GPT decoder)
- **Encoder seul** : classification, NER (BERT, RoBERTa, DeBERTa)
- **Decoder seul** : génération de texte (GPT-2, GPT-3, LLaMA)
- **Vision** : ViT patch embeddings, Swin Transformer (fenêtres locales)

## Points clés pour le fine-tuning

1. Learning rate warmup indispensable (cosine schedule)
2. Layer normalization pré-activations (Pre-LN) plus stable
3. Dropout 0.1 sur les couches d'attention
4. Adam optimizer avec weight decay (AdamW)

## Références
- [[vaswani2017attention]]
- [[devlin2018bert]]
- [[dosovitskiy2020vit]]
