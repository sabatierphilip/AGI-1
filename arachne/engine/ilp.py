from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Set, Tuple


@dataclass
class InductionEvent:
    signature: str
    support: int
    confidence: float
    accepted: bool


class ILPEngine:
    def __init__(
        self,
        fetch_facts: Callable[[], List[Dict[str, str]]],
        add_rule: Callable[[str, str, float], bool],
        on_event: Callable[[InductionEvent], None],
        fetch_rules: Callable[[], List[Dict[str, str]]] | None = None,
    ) -> None:
        self.fetch_facts = fetch_facts
        self.fetch_rules = fetch_rules
        self.add_rule = add_rule
        self.on_event = on_event
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.patterns: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)
        self._batch_buffer: list[tuple[str, str, float, int, bool]] = []
        self._batch_lock = threading.Lock()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            facts = self.fetch_facts()
            for f in facts:
                txt = f.get("text", "")
                if not txt.startswith("(relation"):
                    continue
                pred = self._slot(txt, "predicate")
                subj = self._slot(txt, "subject")
                obj = self._slot(txt, "object")
                if pred and subj and obj:
                    self.patterns[pred].add((subj, obj))

            batch_events: list[InductionEvent] = []
            for predicate, pairs in list(self.patterns.items()):
                support = len(pairs)
                if support >= 3:
                    self._attempt_induction(predicate, pairs, support, batch_events)
                    self.patterns[predicate] = set()

            if batch_events:
                self._fire_batch(batch_events)
            time.sleep(4)

    def _attempt_induction(
        self,
        predicate: str,
        pairs: Set[Tuple[str, str]],
        support: int,
        batch_events: list[InductionEvent],
    ) -> None:
        conf = min(0.92, 0.55 + support * 0.08)
        candidates: list[tuple[str, str]] = []

        if predicate == "causes":
            sig = f"causes-transitive:{support}"
            name = f"induced-causes-trans-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"causes\") (object ?b) (confidence ?c1))\n"
                f"  (relation (subject ?b) (predicate \"causes\") (object ?c) (confidence ?c2))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"causes\") (object ?c) (confidence 0.65))))"
            )
            candidates.append((name, rule))

        elif predicate in ("requires", "HasPrerequisite"):
            sig = f"requires-enables:{support}"
            name = f"induced-requires-enables-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"{predicate}\") (object ?b) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?b) (predicate \"enables\") (object ?a) (confidence 0.68))))"
            )
            candidates.append((name, rule))

        elif predicate == "enables":
            sig = f"enables-supports:{support}"
            name = f"induced-enables-supports-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"enables\") (object ?b) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"supports\") (object ?b) (confidence 0.60))))"
            )
            candidates.append((name, rule))

        elif predicate == "prevents":
            sig = f"prevents-blocks:{support}"
            name = f"induced-prevents-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"prevents\") (object ?b) (confidence ?c))\n"
                f"  (relation (subject ?x) (predicate \"requires\") (object ?b) (confidence ?c2))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"blocks\") (object ?x) (confidence 0.62))))"
            )
            candidates.append((name, rule))

        elif predicate in ("is-a", "IsA", "instance-of", "InstanceOf"):
            objects = sorted({o for _, o in pairs})
            for obj in objects[:3]:
                safe_obj = obj.replace('"', "").replace("\\", "")
                sig = f"isa-member:{safe_obj}:{support}"
                name = f"induced-isa-{self._hash(sig)}"
                rule = (
                    f"(defrule {name}\n"
                    f"  (relation (subject ?x) (predicate \"{predicate}\") (object \"{safe_obj}\") (confidence ?c))\n"
                    f"  =>\n"
                    f"  (assert (conclusion (text \"{safe_obj}-membership\") (trace-id \"{name}\"))))"
                )
                candidates.append((name, rule))

        elif predicate in ("part-of", "PartOf"):
            sig = f"partof-contains:{support}"
            name = f"induced-partof-contains-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"{predicate}\") (object ?b) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?b) (predicate \"contains\") (object ?a) (confidence 0.72))))"
            )
            candidates.append((name, rule))

        elif predicate in ("has-a", "HasA"):
            sig = f"hasa-partof:{support}"
            name = f"induced-hasa-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"{predicate}\") (object ?y) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?y) (predicate \"part-of\") (object ?x) (confidence 0.70))))"
            )
            candidates.append((name, rule))

        elif predicate == "before":
            sig = f"before-transitive:{support}"
            name = f"induced-before-trans-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"before\") (object ?b) (confidence ?c1))\n"
                f"  (relation (subject ?b) (predicate \"before\") (object ?c) (confidence ?c2))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"before\") (object ?c) (confidence 0.63))))"
            )
            candidates.append((name, rule))

        elif predicate == "after":
            sig = f"after-implies-before:{support}"
            name = f"induced-after-before-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"after\") (object ?y) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?y) (predicate \"before\") (object ?x) (confidence 0.75))))"
            )
            candidates.append((name, rule))

        elif predicate in ("sequence", "during"):
            sig = f"sequence-order:{support}"
            name = f"induced-sequence-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"{predicate}\") (object ?b) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"before\") (object ?b) (confidence 0.60))))"
            )
            candidates.append((name, rule))

        elif predicate in ("believes", "confirms"):
            sig = f"belief-confidence:{support}"
            name = f"induced-belief-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?agent) (predicate \"{predicate}\") (object ?claim) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (rule-health (rule-name ?claim) (confidence ?c) (support 1) (contradict 0))))"
            )
            candidates.append((name, rule))

        elif predicate == "doubts":
            sig = f"doubt-lowers:{support}"
            name = f"induced-doubt-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  ?rh <- (rule-health (rule-name ?r) (confidence ?c) (support ?s) (contradict ?k))\n"
                f"  (relation (subject ?agent) (predicate \"doubts\") (object ?r) (confidence ?cv))\n"
                f"  =>\n"
                f"  (modify ?rh (confidence (- ?c 0.08)) (contradict (+ ?k 1))))"
            )
            candidates.append((name, rule))

        elif predicate in ("RelatedTo", "related-to", "SimilarTo", "Synonym"):
            sig = f"related-symmetric:{predicate}:{support}"
            name = f"induced-related-sym-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?a) (predicate \"{predicate}\") (object ?b) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?b) (predicate \"{predicate}\") (object ?a) (confidence (* ?c 0.9)))))"
            )
            candidates.append((name, rule))

        elif predicate in ("CapableOf", "capable-of"):
            sig = f"capable-conclusion:{support}"
            name = f"induced-capable-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"{predicate}\") (object ?action) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (conclusion (text \"capability-known\") (trace-id \"{name}\"))))"
            )
            candidates.append((name, rule))

        elif predicate in ("UsedFor", "used-for"):
            sig = f"usedfor-purpose:{support}"
            name = f"induced-usedfor-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?tool) (predicate \"{predicate}\") (object ?purpose) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?purpose) (predicate \"requires-tool\") (object ?tool) (confidence 0.62))))"
            )
            candidates.append((name, rule))

        elif predicate in ("HasProperty", "has-property", "NotHasProperty"):
            sig = f"property-observed:{predicate}:{support}"
            name = f"induced-property-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"{predicate}\") (object ?prop) (confidence ?c))\n"
                f"  (entity (name ?x) (kind ?k))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?k) (predicate \"typically-has\") (object ?prop) (confidence 0.60))))"
            )
            candidates.append((name, rule))

        elif predicate in ("MadeOf", "made-of"):
            sig = f"madeof-composition:{support}"
            name = f"induced-madeof-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?whole) (predicate \"{predicate}\") (object ?material) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?material) (predicate \"composes\") (object ?whole) (confidence 0.65))))"
            )
            candidates.append((name, rule))

        elif predicate in ("AtLocation", "LocatedNear", "at-location"):
            sig = f"location-cooccur:{support}"
            name = f"induced-location-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"{predicate}\") (object ?place) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?place) (predicate \"contains-entity\") (object ?x) (confidence 0.68))))"
            )
            candidates.append((name, rule))

        elif predicate in ("Desires", "MotivatedByGoal", "CausesDesire"):
            sig = f"desire-goal:{support}"
            name = f"induced-desire-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?agent) (predicate \"{predicate}\") (object ?goal) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?agent) (predicate \"pursues\") (object ?goal) (confidence 0.65))))"
            )
            candidates.append((name, rule))

        elif predicate in ("wikidata-match",):
            sig = f"wikidata-identity:{support}"
            name = f"induced-wikidata-id-{self._hash(sig)}"
            rule = (
                f"(defrule {name}\n"
                f"  (relation (subject ?x) (predicate \"wikidata-match\") (object ?y) (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (entity (name ?x) (kind \"wikidata-entity\"))))"
            )
            candidates.append((name, rule))

        else:
            if support >= 5:
                sig = f"generic-symmetric:{predicate}:{support}"
                name = f"induced-generic-{self._hash(sig)}"
                rule = (
                    f"(defrule {name}\n"
                    f"  (relation (subject ?a) (predicate \"{predicate}\") (object ?b) (confidence ?c))\n"
                    f"  =>\n"
                    f"  (assert (conclusion (text \"{predicate}-observed\") (trace-id \"{name}\"))))"
                )
                candidates.append((name, rule))

        for rule_name, rule_text in candidates:
            if self._rule_exists(rule_name):
                batch_events.append(InductionEvent(rule_name, support, conf, False))
                continue
            accepted = self.add_rule(rule_text, rule_name, conf)
            batch_events.append(InductionEvent(rule_name, support, conf, accepted))

    def _fire_batch(self, events: list[InductionEvent]) -> None:
        with self._batch_lock:
            for evt in events:
                self.on_event(evt)

    def _rule_exists(self, rule_name: str) -> bool:
        if not self.fetch_rules:
            return False
        return any(r.get("name") == rule_name for r in self.fetch_rules())

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]

    @staticmethod
    def _slot(text: str, slot: str) -> str:
        marker = f'({slot} "'
        if marker not in text:
            return ""
        return text.split(marker, 1)[1].split('"', 1)[0]
