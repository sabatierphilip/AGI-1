from __future__ import annotations

import requests

BASE_CONFIDENCE = 0.85


def query_entity_relations(entity_label: str) -> list[dict]:
    query = f'''
    SELECT ?item ?itemLabel ?propertyLabel ?valueLabel WHERE {{
      ?item rdfs:label "{entity_label}"@en .
      ?item ?property ?value .
      ?prop wikibase:directClaim ?property .
      ?prop rdfs:label ?propertyLabel .
      FILTER(LANG(?propertyLabel) = "en")
      FILTER(ISIRI(?value))
      ?value rdfs:label ?valueLabel .
      FILTER(LANG(?valueLabel) = "en")
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }} LIMIT 8
    '''
    try:
        response = requests.get(
            "https://query.wikidata.org/sparql",
            params={"format": "json", "query": query},
            headers={"Accept": "application/sparql-results+json", "User-Agent": "ARACHNE/1.0"},
            timeout=12,
        )
        response.raise_for_status()
        rows = response.json().get("results", {}).get("bindings", [])
    except Exception:
        return []

    facts = []
    for row in rows:
        facts.append(
            {
                "subject": entity_label,
                "predicate": row.get("propertyLabel", {}).get("value", "related-to"),
                "object": row.get("valueLabel", {}).get("value", "unknown"),
                "confidence": BASE_CONFIDENCE,
                "source": "wikidata",
            }
        )
    return facts
