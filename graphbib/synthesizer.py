"""
Automatic extractive summarisation per cluster.
Uses TF-IDF to score sentences from document abstracts and picks
the most representative ones as the cluster description.
"""
from __future__ import annotations

import re
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import Document

_MIN_SENTENCE_LEN = 40
_MAX_SUMMARY_CHARS = 600


class AutoSynthesizer:
    """TF-IDF extractive synthesizer for a group of documents."""

    def synthesize(
        self,
        docs: List[Document],
        seed_keywords: List[str],
        n_sentences: int = 2,
    ) -> str:
        """Return a short extractive summary for the given documents."""
        sentences = self._collect_sentences(docs)

        if not sentences:
            return self._fallback(docs, seed_keywords)

        try:
            vec = TfidfVectorizer(
                max_features=500,
                stop_words="english",
                ngram_range=(1, 2),
            )
            X = vec.fit_transform(sentences)
            # Score = sum of TF-IDF weights — higher means more characteristic
            scores = X.sum(axis=1).A1
            top_idx = sorted(np.argsort(scores)[::-1][:n_sentences])
            summary = " ".join(sentences[i] for i in top_idx)
            return summary[:_MAX_SUMMARY_CHARS].strip()
        except Exception:
            return self._fallback(docs, seed_keywords)

    # ------------------------------------------------------------------
    @staticmethod
    def _collect_sentences(docs: List[Document]) -> List[str]:
        sentences: List[str] = []
        for doc in docs:
            text = doc.abstract or ""
            for sent in re.split(r"(?<=[.!?])\s+", text):
                sent = sent.strip()
                if len(sent) >= _MIN_SENTENCE_LEN:
                    sentences.append(sent)
        return sentences

    @staticmethod
    def _fallback(docs: List[Document], seed_keywords: List[str]) -> str:
        kw_str = ", ".join(seed_keywords[:5])
        return (
            f"{len(docs)} document(s) — thèmes principaux : {kw_str}."
            if kw_str
            else f"{len(docs)} document(s)."
        )
