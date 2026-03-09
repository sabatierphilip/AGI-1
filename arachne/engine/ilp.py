from __future__ import annotations

import threading
import time
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass
class InductionEvent:
    signature: str
    support: int
    confidence: float
    accepted: bool


class ILPEngine:
    def __init__(self, fetch_facts: Callable[[], List[Dict[str, str]]], add_rule: Callable[[str, str, float], bool], on_event: Callable[[InductionEvent], None]) -> None:
        self.fetch_facts = fetch_facts
        self.add_rule = add_rule
        self.on_event = on_event
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.patterns: Counter[str] = Counter()

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
                if "relation" in txt:
                    signature = self._normalize_signature(txt)
                    self.patterns[signature] += 1
            for signature, support in list(self.patterns.items()):
                if support >= 3:
                    conf = min(0.9, 0.4 + support * 0.08)
                    rule_name = f"induced-{abs(hash(signature)) % 100000}"
                    rule_text = (
                        f"(defrule {rule_name}\n"
                        f"  (relation (subject ?s) (predicate \"{signature}\") (object ?o) (confidence ?c))\n"
                        f"  =>\n"
                        f"  (assert (relation (subject ?o) (predicate \"related-back\") (object ?s) (confidence 0.62))))"
                    )
                    accepted = self.add_rule(rule_text, rule_name, conf)
                    self.on_event(InductionEvent(rule_name, support, conf, accepted))
                    self.patterns[signature] = 0
            time.sleep(5)

    def _normalize_signature(self, fact_text: str) -> str:
        if 'predicate "' in fact_text:
            return fact_text.split('predicate "', 1)[1].split('"', 1)[0]
        return "relation"
