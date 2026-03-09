from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

from transformers import pipeline


INTENTS = ["QUERY", "ASSERT", "CONTRADICT", "CLARIFY", "UNKNOWN"]
KNOWN_TERMS = {"arachne", "clips", "nars", "ilp", "bert", "watchdog", "rulebase"}


@dataclass
class ParseResult:
    intent: str
    entities: List[str]
    triples: List[Dict[str, str]]


class BertParser:
    def __init__(self) -> None:
        self.ner = None
        try:
            self.ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
        except Exception as exc:
            print(f"[WARN] BERT NER unavailable, using regex parser fallback: {exc}")

    def parse(self, text: str) -> ParseResult:
        intent = self._intent(text)
        entities = self._extract_entities(text)
        triples = self._extract_triples(text, entities)
        return ParseResult(intent=intent, entities=entities, triples=triples)

    def _extract_entities(self, text: str) -> List[str]:
        if self.ner is not None:
            try:
                return [e["word"] for e in self.ner(text)]
            except Exception as exc:
                print(f"[WARN] BERT inference failed, using regex entities: {exc}")
        caps = re.findall(r"\b[A-Z][A-Za-z0-9_\-]*\b", text)
        domain = [w for w in re.findall(r"\b[a-zA-Z][A-Za-z0-9_\-]*\b", text) if w.lower() in KNOWN_TERMS]
        return list(dict.fromkeys(caps + domain))

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
