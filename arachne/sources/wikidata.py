from __future__ import annotations

import requests

BASE_CONFIDENCE = 0.85


def query_entity_relations(entity_label: str) -> list[dict]:
    query = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item rdfs:label \"{entity_label}\"@en .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\". }}
    }} LIMIT 5
    """
    response = requests.get(
        "https://query.wikidata.org/sparql",
        params={"format": "json", "query": query},
        headers={"Accept": "application/sparql-results+json", "User-Agent": "ARACHNE/1.0"},
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json().get("results", {}).get("bindings", [])
    return [
        {
            "subject": entity_label,
            "predicate": "wikidata-match",
            "object": row.get("itemLabel", {}).get("value", "unknown"),
            "confidence": BASE_CONFIDENCE,
            "source": "wikidata",
        }
        for row in rows
    ]
