import re
from typing import Dict, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import Document

# Noise tokens that slip through TF-IDF despite stopword filtering
_EXTRA_STOP = {
    "fig", "figure", "table", "et", "al", "doi", "arxiv", "pp", "vol", "no",
    "http", "https", "www", "com", "org", "pdf", "abstract", "introduction",
    "conclusion", "references", "keywords", "ieee", "acm", "springer", "elsevier",
    "section", "chapter", "page", "pages", "results", "method", "methods",
    "approach", "paper", "work", "proposed", "using", "based", "show", "shown",
    "used", "use", "new", "also", "however", "thus", "therefore", "due", "two",
    "one", "three", "first", "second", "third", "may", "can", "via", "per",
}


class KeywordExtractor:
    """
    TF-IDF keyword extraction over a document corpus.

    Injects predefined keywords from document metadata (BibTeX keywords field,
    Markdown YAML frontmatter) before returning, so user-curated terms are never lost.
    """

    def __init__(self, max_keywords: int = 15, max_df: float = 0.85):
        self.max_keywords = max_keywords
        self.max_df = max_df
        self._ensure_nltk()

    # ------------------------------------------------------------------
    def fit_transform(
        self, documents: List[Document]
    ) -> Tuple[List[Document], Dict[str, int]]:
        """
        Assign keywords to every document and return a corpus-level
        frequency dict {keyword: nb_docs_containing_it}.
        """
        texts = [
            self._preprocess(doc.full_text or doc.abstract or doc.title)
            for doc in documents
        ]
        valid = [(i, t) for i, t in enumerate(texts) if len(t.split()) >= 5]

        if valid:
            valid_idx = [i for i, _ in valid]
            valid_texts = [t for _, t in valid]

            min_df = max(1, len(valid_texts) // 20)
            vectorizer = TfidfVectorizer(
                max_features=3000,
                min_df=min_df,
                max_df=self.max_df,
                stop_words=self._stopwords(),
                ngram_range=(1, 2),
                sublinear_tf=True,
            )
            matrix = vectorizer.fit_transform(valid_texts)
            features = vectorizer.get_feature_names_out()

            for list_pos, doc_idx in enumerate(valid_idx):
                doc = documents[doc_idx]
                row = matrix[list_pos].toarray()[0]
                top_idx = np.argsort(row)[::-1][: self.max_keywords]
                doc.keywords = [features[i] for i in top_idx if row[i] > 0]
                doc.keyword_scores = {
                    features[i]: float(row[i]) for i in top_idx if row[i] > 0
                }

        # Merge predefined keywords from metadata (BibTeX / Markdown frontmatter)
        for doc in documents:
            predefined = [
                k.lower()
                for k in doc.raw_metadata.get("predefined_keywords", [])
                if k
            ]
            for kw in reversed(predefined):
                if kw not in doc.keywords:
                    doc.keywords.insert(0, kw)

        # Corpus-level frequency: how many docs mention each keyword
        freq: Dict[str, int] = {}
        for doc in documents:
            for kw in doc.keywords:
                freq[kw] = freq.get(kw, 0) + 1
        freq = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))

        return documents, freq

    # ------------------------------------------------------------------
    def suggest_clusters(
        self,
        documents: List[Document],
        global_freq: Dict[str, int],
        top_n: int = 8,
    ) -> List[dict]:
        """
        Lightweight cluster seeds: for each top keyword, find its most
        frequent co-occurring keywords. Used to pre-fill clusters_template.yaml.
        """
        top_seeds = list(global_freq.keys())[:top_n]
        clusters = []
        for seed in top_seeds:
            co: Dict[str, int] = {}
            for doc in documents:
                if seed in doc.keywords:
                    for kw in doc.keywords:
                        if kw != seed:
                            co[kw] = co.get(kw, 0) + 1
            top_co = sorted(co.items(), key=lambda x: x[1], reverse=True)[:5]
            clusters.append(
                {
                    "seed": seed,
                    "co_keywords": [k for k, _ in top_co],
                    "doc_count": global_freq[seed],
                }
            )
        return clusters

    # ------------------------------------------------------------------
    def _stopwords(self) -> List[str]:
        from nltk.corpus import stopwords

        words = (
            set(stopwords.words("english"))
            | set(stopwords.words("french"))
            | _EXTRA_STOP
        )
        return sorted(words)

    def _preprocess(self, text: str) -> str:
        text = text.lower()
        # Keep letters (including accented), spaces, hyphens
        text = re.sub(r"[^a-záàâäéèêëíìîïóòôöúùûüñ\s\-]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _ensure_nltk() -> None:
        import nltk

        for resource, name in [
            ("corpora/stopwords", "stopwords"),
            ("tokenizers/punkt", "punkt"),
        ]:
            try:
                nltk.data.find(resource)
            except LookupError:
                nltk.download(name, quiet=True)
