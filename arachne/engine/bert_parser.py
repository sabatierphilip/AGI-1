from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from transformers import pipeline


INTENTS = ["QUERY", "ASSERT", "CONTRADICT", "CLARIFY", "UNKNOWN"]


@dataclass
class ParseResult:
    intent: str
    entities: List[str]
    triples: List[Dict[str, str]]


class BertParser:
    def __init__(self) -> None:
        self.ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

    def parse(self, text: str) -> ParseResult:
        intent = self._intent(text)
        entities = [e["word"] for e in self.ner(text)]
        triples = self._extract_triples(text, entities)
        return ParseResult(intent=intent, entities=entities, triples=triples)

    def _intent(self, text: str) -> str:
        lowered = text.lower().strip()
        if lowered.endswith("?") or lowered.startswith("what") or lowered.startswith("why"):
            return "QUERY"
        if any(t in lowered for t in ["not true", "wrong", "contradict"]):
            return "CONTRADICT"
        if any(t in lowered for t in ["clarify", "explain further", "what do you mean"]):
            return "CLARIFY"
        if any(t in lowered for t in ["is", "are", "causes", "means", "has"]):
            return "ASSERT"
        return "UNKNOWN"

    def _extract_triples(self, text: str, entities: List[str]) -> List[Dict[str, str]]:
        triples = []
        matches = re.findall(r"([A-Za-z0-9_\-]+)\s+(is-a|has-a|part-of|causes|requires|enables|prevents|before|after|during|believes|doubts|confirms)\s+([A-Za-z0-9_\-]+)", text)
        for s, p, o in matches:
            triples.append({"subject": s, "predicate": p, "object": o})
        if not triples and len(entities) >= 2:
            triples.append({"subject": entities[0], "predicate": "related-to", "object": entities[1]})
        return triples
