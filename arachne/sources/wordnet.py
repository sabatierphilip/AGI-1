from __future__ import annotations

import nltk
from nltk.corpus import wordnet as wn

BASE_CONFIDENCE = 0.80


def ensure_wordnet() -> None:
    try:
        wn.synsets("test")
    except LookupError:
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-1.4", quiet=True)


def lexical_relations(token: str) -> list[dict]:
    ensure_wordnet()
    out = []
    for syn in wn.synsets(token)[:3]:
        for hyper in syn.hypernyms()[:2]:
            out.append(
                {
                    "subject": token,
                    "predicate": "is-a",
                    "object": hyper.lemmas()[0].name().replace("_", "-"),
                    "confidence": BASE_CONFIDENCE,
                    "source": "wordnet",
                }
            )
    return out
