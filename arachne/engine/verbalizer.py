from __future__ import annotations

from typing import Dict, List


class Verbalizer:
    INTENT_OPENERS = {
        "QUERY": "Based on my knowledge: ",
        "ASSERT": "Understood. I've recorded that ",
        "CONTRADICT": "I'm noting a potential conflict: ",
    }

    def __init__(self) -> None:
        self.predicate_phrases = {
            "is-a": "is a type of",
            "causes": "causes",
            "requires": "requires",
            "enables": "enables",
            "part-of": "is part of",
            "has-a": "has",
            "before": "comes before",
            "after": "comes after",
            "believes": "believes",
            "related-to": "is related to",
            "IsA": "is a",
            "RelatedTo": "is related to",
            "CapableOf": "is capable of",
            "UsedFor": "is used for",
            "HasProperty": "has the property",
            "AtLocation": "is located at",
            "Causes": "causes",
            "CausesDesire": "causes a desire for",
            "CreatedBy": "is created by",
            "DefinedAs": "is defined as",
            "DerivedFrom": "is derived from",
            "Desires": "desires",
            "DistinctFrom": "is distinct from",
            "Entails": "entails",
            "EtymologicallyDerivedFrom": "is etymologically derived from",
            "EtymologicallyRelatedTo": "is etymologically related to",
            "FormOf": "is a form of",
            "HasA": "has",
            "HasContext": "is used in the context of",
            "HasFirstSubevent": "starts with",
            "HasLastSubevent": "ends with",
            "HasPrerequisite": "has prerequisite",
            "HasSubevent": "has subevent",
            "InstanceOf": "is an instance of",
            "LocatedNear": "is located near",
            "MadeOf": "is made of",
            "MannerOf": "is a manner of",
            "MotivatedByGoal": "is motivated by",
            "NotCapableOf": "is not capable of",
            "NotDesires": "does not desire",
            "NotHasProperty": "does not have the property",
            "NotUsedFor": "is not used for",
            "ObstructedBy": "is obstructed by",
            "PartOf": "is part of",
            "ReceivesAction": "receives action",
            "SimilarTo": "is similar to",
            "SymbolOf": "is a symbol of",
            "Synonym": "is a synonym of",
        }

    def verbalize(
        self,
        conclusions: List[Dict[str, str]],
        templates: Dict[str, str],
        facts: List[Dict[str, str]] | None = None,
        intent: str = "UNKNOWN",
        original_text: str = "",
    ) -> List[Dict[str, str]]:
        debug_notes: List[str] = []
        output: List[Dict[str, str]] = []

        # Stage 1: template matching.
        for c in conclusions:
            text = c.get("text", "")
            trace_id = c.get("trace-id", "unknown")
            if text in templates:
                output.append({"message": self._with_opener(templates[text], intent), "trace": trace_id})

        # Stage 2: relation fact synthesis for query/assert/unknown intents.
        if intent in ("QUERY", "ASSERT", "UNKNOWN") and not output:
            narrative = self._build_narrative(facts or [], intent, original_text)
            if narrative:
                output.append({"message": narrative, "trace": "relation-synthesis"})

        # Stage 4: intent-aware meaningful fallbacks.
        if not output:
            fallback = {
                "QUERY": "I don't have sufficient rules to answer that yet. Keep asking to help me build knowledge.",
                "ASSERT": "I've noted that assertion and added it to my working memory.",
                "CONTRADICT": "I've recorded that contradiction. My confidence scores will be updated.",
                "UNKNOWN": "I've processed your input. No strong conclusions yet.",
            }.get(intent, "I've processed your input. No strong conclusions yet.")
            output.append({"message": fallback, "trace": "fallback"})

        # Preserve old message only as debug note.
        if any(c.get("text", "") not in templates for c in conclusions):
            debug_notes.append("I have a conclusion but no verbalization rule for it yet")
        for m in output:
            if debug_notes:
                m["debug"] = "; ".join(debug_notes)

        return output

    def _with_opener(self, text: str, intent: str) -> str:
        openers = {
            "QUERY": "Based on my knowledge: ",
            "ASSERT": "Understood. I've recorded that ",
            "CONTRADICT": "I'm noting a potential conflict: ",
        }
        return f"{openers.get(intent, '')}{text}" if intent in openers else text

    def _build_narrative(
        self, facts: List[Dict[str, str]], intent: str, original_text: str
    ) -> str:
        from collections import defaultdict

        by_subject: dict = defaultdict(list)
        for f in facts:
            txt = f.get("text", "")
            subj = self._slot(txt, "subject")
            pred = self._slot(txt, "predicate")
            obj = self._slot(txt, "object")
            if subj and pred and obj and subj != "unknown" and pred != "unknown" and obj != "unknown":
                phrase = self.predicate_phrases.get(pred, pred.replace("-", " "))
                by_subject[subj].append((phrase, obj))

        if not by_subject:
            return ""

        sentences = []
        for subj, relations in list(by_subject.items())[:3]:
            if len(relations) == 1:
                phrase, obj = relations[0]
                sentences.append(f"{subj} {phrase} {obj}")
            elif len(relations) == 2:
                p1, o1 = relations[0]
                p2, o2 = relations[1]
                sentences.append(f"{subj} {p1} {o1} and {p2} {o2}")
            else:
                parts = [f"{p} {o}" for p, o in relations[:3]]
                sentences.append(f"{subj} {parts[0]}, {parts[1]}, and {parts[2]}")

        if not sentences:
            return ""

        opener = self.INTENT_OPENERS.get(intent, "")
        return opener + ". ".join(sentences) + "."

    @staticmethod
    def _slot(text: str, slot: str) -> str:
        marker = f'({slot} "'
        if marker not in text:
            return "unknown"
        return text.split(marker, 1)[1].split('"', 1)[0]
