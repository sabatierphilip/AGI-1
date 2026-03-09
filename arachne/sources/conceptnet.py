from __future__ import annotations

import requests

BASE_CONFIDENCE = 0.75


def enrich_concept(concept: str) -> list[dict]:
    response = requests.get(f"https://api.conceptnet.io/c/en/{concept}", timeout=10)
    response.raise_for_status()
    edges = response.json().get("edges", [])[:10]
    out = []
    for edge in edges:
        rel = edge.get("rel", {}).get("label", "related")
        start = edge.get("start", {}).get("label", concept)
        end = edge.get("end", {}).get("label", concept)
        weight = edge.get("weight", 1.0)
        conf = min(0.95, BASE_CONFIDENCE * min(1.0, weight / 2))
        out.append(
            {
                "subject": start,
                "predicate": rel.lower().replace(" ", "-"),
                "object": end,
                "confidence": conf,
                "source": "conceptnet",
            }
        )
    return out
