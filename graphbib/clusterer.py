"""
Two-pass semi-supervised clustering.

Pass A — Predefined (top-down):
    For each document, compute keyword overlap with each predefined cluster's
    seed_keywords. Assign when overlap > 0 (soft: a doc can join several clusters).

Pass B — Discovery (bottom-up, optional):
    Run sklearn HDBSCAN on the TF-IDF keyword vectors of ALL documents.
    Discovered labels that correspond to new thematic groups are added as
    extra clusters on top of predefined assignments.
    Documents with no assignment at all go into a special "_Unclustered" bucket.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .cluster_reader import ClusterConfig
from .models import Document

_DISCOVERY_COLOR = "#64748b"


class Clusterer:
    def __init__(self, config: ClusterConfig):
        self.cfg = config

    # ------------------------------------------------------------------
    def run(self, documents: List[Document]) -> Tuple[List[Document], List[dict]]:
        """
        Returns (documents_with_clusters, cluster_registry).
        cluster_registry is a list of dicts describing every cluster (predefined + discovered).
        """
        # 1. Normalise keywords (synonyms + reject list)
        documents = self._normalise(documents)

        # 2. Reset any previous cluster assignments
        for doc in documents:
            doc.clusters = []

        # 3. Predefined seed-based assignment
        documents = self._assign_predefined(documents)

        # 4. HDBSCAN discovery
        discovered_registry: List[dict] = []
        if self.cfg.discovery.get("enabled", True):
            documents, discovered_registry = self._discover(documents)

        # 5. Build final cluster registry
        predefined_registry = [
            {
                "name": c["name"],
                "color": c["color"],
                "seed_keywords": c["seed_keywords"],
                "discovered": False,
            }
            for c in self.cfg.predefined
        ]
        registry = predefined_registry + discovered_registry

        return documents, registry

    # ------------------------------------------------------------------
    def _normalise(self, documents: List[Document]) -> List[Document]:
        """Apply synonym merging and reject-keyword filtering to each doc's keywords."""
        canonical_map: Dict[str, str] = {}
        for canonical, aliases in self.cfg.synonyms.items():
            for alias in aliases:
                canonical_map[alias] = canonical

        for doc in documents:
            cleaned: List[str] = []
            seen: Set[str] = set()
            for kw in doc.keywords:
                kw_norm = canonical_map.get(kw, kw)
                if kw_norm in self.cfg.reject_keywords:
                    continue
                if kw_norm not in seen:
                    cleaned.append(kw_norm)
                    seen.add(kw_norm)
            doc.keywords = cleaned
        return documents

    # ------------------------------------------------------------------
    def _assign_predefined(self, documents: List[Document]) -> List[Document]:
        for doc in documents:
            doc_kw_set = set(doc.keywords)
            for cluster in self.cfg.predefined:
                seeds = set(cluster["seed_keywords"])
                overlap = seeds & doc_kw_set
                if not overlap and cluster.get("force_include"):
                    # force_include: check if any seed appears as a substring
                    overlap = {
                        s for s in seeds
                        if any(s in kw or kw in s for kw in doc_kw_set)
                    }
                if overlap:
                    score = round(len(overlap) / max(len(seeds), 1), 3)
                    doc.clusters.append(
                        {
                            "name": cluster["name"],
                            "color": cluster["color"],
                            "score": score,
                            "matched_keywords": sorted(overlap),
                            "discovered": False,
                        }
                    )
            # Sort by score descending so primary cluster is first
            doc.clusters.sort(key=lambda c: c["score"], reverse=True)
        return documents

    # ------------------------------------------------------------------
    def _discover(
        self, documents: List[Document]
    ) -> Tuple[List[Document], List[dict]]:
        min_size = max(2, int(self.cfg.discovery.get("min_cluster_size", 3)))

        # Build keyword bag-of-words per document
        texts = [" ".join(doc.keywords) for doc in documents]
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if len(non_empty) < min_size:
            return documents, []

        indices = [i for i, _ in non_empty]
        corpus = [t for _, t in non_empty]

        vec = TfidfVectorizer(ngram_range=(1, 1), min_df=1)
        X = vec.fit_transform(corpus)
        # L2-normalise → cosine similarity becomes Euclidean distance
        X_dense = normalize(X.toarray(), norm="l2")

        labels = self._hdbscan(X_dense, min_size)

        # Map HDBSCAN labels → cluster names using top keywords
        label_to_name, label_to_kws = self._name_discovered(
            labels, indices, documents, vec.get_feature_names_out()
        )

        # Attach discovered clusters to documents
        for list_pos, doc_idx in enumerate(indices):
            lbl = labels[list_pos]
            if lbl == -1:
                continue  # noise
            name = label_to_name[lbl]
            # Only add if this discovered cluster isn't already covered by a predefined one
            existing_names = {c["name"] for c in documents[doc_idx].clusters}
            if name not in existing_names:
                documents[doc_idx].clusters.append(
                    {
                        "name": name,
                        "color": _DISCOVERY_COLOR,
                        "score": round(float(getattr(self, "_proba", {}).get(list_pos, 0.5)), 3),
                        "matched_keywords": label_to_kws.get(lbl, []),
                        "discovered": True,
                    }
                )

        # Build registry for discovered clusters
        registry = [
            {
                "name": name,
                "color": _DISCOVERY_COLOR,
                "seed_keywords": label_to_kws.get(lbl, []),
                "discovered": True,
            }
            for lbl, name in label_to_name.items()
        ]
        return documents, registry

    # ------------------------------------------------------------------
    @staticmethod
    def _hdbscan(X: np.ndarray, min_size: int) -> np.ndarray:
        try:
            from sklearn.cluster import HDBSCAN  # sklearn ≥ 1.3
            model = HDBSCAN(min_cluster_size=min_size, metric="euclidean")
            return model.fit_predict(X)
        except ImportError:
            # Fallback: simple AgglomerativeClustering if HDBSCAN unavailable
            from sklearn.cluster import AgglomerativeClustering
            n = max(2, len(X) // min_size)
            model = AgglomerativeClustering(n_clusters=n, metric="cosine", linkage="average")
            return model.fit_predict(X)

    # ------------------------------------------------------------------
    @staticmethod
    def _name_discovered(
        labels: np.ndarray,
        doc_indices: List[int],
        documents: List[Document],
        feature_names: np.ndarray,
    ) -> Tuple[Dict[int, str], Dict[int, List[str]]]:
        label_to_name: Dict[int, str] = {}
        label_to_kws: Dict[int, List[str]] = {}

        for lbl in sorted(set(labels)):
            if lbl == -1:
                continue
            # Collect keyword frequency for this cluster
            kw_freq: Dict[str, int] = {}
            for list_pos, doc_idx in enumerate(doc_indices):
                if labels[list_pos] != lbl:
                    continue
                for kw in documents[doc_idx].keywords:
                    kw_freq[kw] = kw_freq.get(kw, 0) + 1
            top = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:4]
            top_kws = [k for k, _ in top]
            label_to_kws[lbl] = top_kws
            label_to_name[lbl] = "Auto__" + "_".join(top_kws[:2]) if top_kws else f"Auto_{lbl}"

        return label_to_name, label_to_kws

    # ------------------------------------------------------------------
    @staticmethod
    def cluster_stats(documents: List[Document], registry: List[dict]) -> Dict[str, Any]:
        name_to_docs: Dict[str, List[str]] = {c["name"]: [] for c in registry}
        unclustered: List[str] = []
        for doc in documents:
            if not doc.clusters:
                unclustered.append(doc.title)
            else:
                for c in doc.clusters:
                    name_to_docs.setdefault(c["name"], []).append(doc.title)
        n_multi = sum(1 for doc in documents if len(doc.clusters) > 1)
        return {
            "per_cluster": {k: len(v) for k, v in name_to_docs.items()},
            "unclustered": len(unclustered),
            "multi_cluster": n_multi,
            "coverage_pct": round(
                100 * (len(documents) - len(unclustered)) / max(len(documents), 1), 1
            ),
        }
