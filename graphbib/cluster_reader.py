"""
Parse and validate clusters_template.yaml produced by `graphbib scan`
and edited by the user before running `graphbib build`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


class ClusterConfig:
    """Validated, normalised view of clusters_template.yaml."""

    def __init__(self, path: str):
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path} must be a YAML mapping, got {type(raw)}")

        self.predefined: List[Dict[str, Any]] = self._parse_predefined(
            raw.get("predefined_clusters", [])
        )
        self.reject_keywords: Set[str] = self._parse_reject(
            raw.get("reject_keywords", [])
        )
        self.synonyms: Dict[str, List[str]] = self._parse_synonyms(
            raw.get("synonyms", {})
        )
        self.discovery: Dict[str, Any] = {
            "enabled": True,
            "algorithm": "hdbscan",
            "min_cluster_size": 3,
            "embedding": "tfidf",
            **{k: v for k, v in (raw.get("discovery") or {}).items()},
        }

    # ------------------------------------------------------------------
    def _parse_predefined(self, raw: list) -> List[Dict[str, Any]]:
        clusters = []
        for i, item in enumerate(raw or []):
            if not isinstance(item, dict):
                continue
            seeds = [str(k).lower().strip() for k in item.get("seed_keywords", []) if k]
            if not seeds:
                continue
            clusters.append(
                {
                    "name": str(item.get("name", f"Cluster_{i + 1}")),
                    "seed_keywords": seeds,
                    "color": str(item.get("color", "#6366f1")),
                    "force_include": bool(item.get("force_include", False)),
                }
            )
        return clusters

    def _parse_reject(self, raw) -> Set[str]:
        out: Set[str] = set()
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, list):
                    out.update(str(x).lower().strip() for x in item if x)
                elif item and not isinstance(item, (list, dict)):
                    out.add(str(item).lower().strip())
        return out - {""}

    def _parse_synonyms(self, raw) -> Dict[str, List[str]]:
        if not isinstance(raw, dict):
            return {}
        return {
            str(canonical).lower(): [str(a).lower() for a in aliases]
            for canonical, aliases in raw.items()
            if aliases
        }

    def summary(self) -> str:
        lines = [
            f"  {len(self.predefined)} cluster(s) prédéfini(s)",
            f"  {len(self.reject_keywords)} keyword(s) à rejeter",
            f"  {len(self.synonyms)} groupe(s) de synonymes",
            f"  Découverte automatique : {'oui' if self.discovery['enabled'] else 'non'}"
            + (f" (min {self.discovery['min_cluster_size']} docs)" if self.discovery["enabled"] else ""),
        ]
        return "\n".join(lines)
