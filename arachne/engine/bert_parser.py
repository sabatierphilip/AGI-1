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
        # Model 1: Named entity recognition
        try:
            self.ner = pipeline(
                "ner",
                model="dslim/bert-base-NER",
                aggregation_strategy="simple",
            )
        except Exception as exc:
            print(f"[ARACHNE] NER model load failed: {exc} — using regex fallback")
            self.ner = None

        # Model 2: Zero-shot relation classification
        # Used to classify extracted pairs into known predicate types
        try:
            self.zsl = pipeline(
                "zero-shot-classification",
                model="typeform/distilbart-mnli-12-3",
            )
            self.zsl_labels = [
                "causes",
                "requires",
                "enables",
                "prevents",
                "is a type of",
                "is part of",
                "has property",
                "is similar to",
                "is located in",
                "happens before",
                "happens after",
            ]
        except Exception as exc:
            print(f"[ARACHNE] ZSL model load failed: {exc} — skipping relation classification")
            self.zsl = None
            self.zsl_labels = []

    def parse(self, text: str) -> ParseResult:
        intent = self._intent(text)
        entities = self._extract_entities(text)
        triples = self._extract_triples(text, entities)
        return ParseResult(intent=intent, entities=entities, triples=triples)

    def _extract_entities(self, text: str) -> List[str]:
        entities = []

        # Layer 1: BERT NER for proper nouns
        if self.ner:
            try:
                for e in self.ner(text):
                    word = e.get("word", "").replace("##", "").strip()
                    if word and len(word) > 1:
                        entities.append(word)
            except Exception as exc:
                print(f"[ARACHNE] NER failed: {exc}")

        # Layer 2: Noun-like tokens from text — catches abstract concepts
        compounds = re.findall(r"\b[a-z][a-z]+-[a-z][a-z]+\b", text)
        entities.extend(compounds)

        stopwords = {
            "that",
            "this",
            "with",
            "from",
            "they",
            "have",
            "will",
            "been",
            "when",
            "then",
            "than",
            "also",
            "some",
            "more",
        }
        words = re.findall(r"\b[a-z]{5,}\b", text.lower())
        entities.extend([w for w in words if w not in stopwords])

        seen = set()
        result = []
        for e in entities:
            if e.lower() not in seen:
                seen.add(e.lower())
                result.append(e)
        return result[:10]

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

        # Layer 1: Explicit pattern matching — catches structured assertions
        predicate_patterns = [
            (
                r"([A-Za-z0-9_\-]+)\s+(is-a|has-a|part-of|causes|requires|enables|prevents|before|after|during|believes|doubts|confirms|is a|is part of|causes|requires)\s+([A-Za-z0-9_\-]+)",
                None,
            ),
        ]
        for pattern, _normalizer in predicate_patterns:
            for s, p, o in re.findall(pattern, text):
                pred = p.strip().replace(" ", "-")
                triples.append({"subject": s.strip(), "predicate": pred, "object": o.strip()})

        # Layer 2: ZSL relation classification for entity pairs
        if self.zsl and len(entities) >= 2 and not triples:
            try:
                for i in range(min(len(entities) - 1, 3)):
                    subj = entities[i]
                    obj = entities[i + 1]
                    snippet = f"{subj} and {obj}"
                    result = self.zsl(snippet, candidate_labels=self.zsl_labels)
                    best_label = result["labels"][0]
                    best_score = result["scores"][0]
                    if best_score > 0.4:
                        pred_map = {
                            "is a type of": "is-a",
                            "is part of": "part-of",
                            "has property": "has-property",
                            "is similar to": "related-to",
                            "is located in": "at-location",
                            "happens before": "before",
                            "happens after": "after",
                        }
                        pred = pred_map.get(best_label, best_label.replace(" ", "-"))
                        triples.append(
                            {
                                "subject": subj,
                                "predicate": pred,
                                "object": obj,
                            }
                        )
            except Exception as exc:
                print(f"[ARACHNE] ZSL classification failed: {exc}")

        # Layer 3: Fallback — entity co-occurrence
        if not triples and len(entities) >= 2:
            triples.append(
                {
                    "subject": entities[0],
                    "predicate": "related-to",
                    "object": entities[1],
                }
            )

        return triples
