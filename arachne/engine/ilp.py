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
                self.patterns[pred].add((subj, obj))

            for predicate, pairs in list(self.patterns.items()):
                support = len(pairs)
                if support >= 3:
                    self._attempt_induction(predicate, pairs, support)
                self.patterns[predicate] = set()
            time.sleep(4)

    def _attempt_induction(self, predicate: str, pairs: Set[Tuple[str, str]], support: int) -> None:
        conf = min(0.92, 0.55 + support * 0.08)
        rule_name = ""
        rule_text = ""

        if predicate == "causes":
            sig = f"causes-transitive:{support}"
            rule_name = f"induced-causes-transitive-{self._hash(sig)}"
            rule_text = (
                f"(defrule {rule_name}\n"
                f"  (relation (subject ?a) (predicate \"causes\") (object ?b) (confidence ?c1))\n"
                f"  (relation (subject ?b) (predicate \"causes\") (object ?c) (confidence ?c2))\n"
                f"  =>\n"
                f"  (assert (relation (subject ?a) (predicate \"causes\") (object ?c) (confidence 0.7))))"
            )
        elif predicate == "is-a":
            sample_obj = sorted({o for _, o in pairs})[0]
            sig = f"isa-member:{sample_obj}:{support}"
            rule_name = f"induced-isa-member-{self._hash(sig)}"
            rule_text = (
                f"(defrule {rule_name}\n"
                f"  (relation (subject ?x) (predicate \"is-a\") (object \"{sample_obj}\") (confidence ?c))\n"
                f"  =>\n"
                f"  (assert (conclusion (text \"?x-is-member-of-{sample_obj}\") (trace-id \"{rule_name}\"))))"
            )
        else:
            return

        if self._rule_exists(rule_name):
            self.on_event(InductionEvent(rule_name, support, conf, False))
            return

        accepted = self.add_rule(rule_text, rule_name, conf)
        self.on_event(InductionEvent(rule_name, support, conf, accepted))

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
